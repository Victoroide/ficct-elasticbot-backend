"""
ViewSet for elasticity calculations.

Anonymous API with IP-based rate limiting.

Supports two execution modes controlled by ELASTICITY_ASYNC_ENABLED setting:
- Async mode (True): Uses Celery/Redis for background processing
- Sync mode (False): Executes calculation directly in the request

Sync mode is the fallback when Redis is unavailable or for guaranteed execution.
"""
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import AllowAny
from django.utils import timezone
from django.conf import settings
from drf_spectacular.utils import (
    extend_schema,
    extend_schema_view,
    OpenApiExample,
)
from apps.elasticity.models import ElasticityCalculation
from apps.elasticity.serializers import (
    CalculationRequestSerializer,
    CalculationResultSerializer,
)
from apps.elasticity.tasks import calculate_elasticity_async
from apps.elasticity.services.calculation_executor import execute_calculation
from utils.decorators import get_client_ip
import logging

logger = logging.getLogger(__name__)

# Check if async mode is enabled (requires Redis/Celery)
ASYNC_ENABLED = getattr(settings, 'ELASTICITY_ASYNC_ENABLED', False)


@extend_schema_view(
    list=extend_schema(
        tags=['Elasticity Analysis'],
        summary='List all calculations',
        description='Retrieve paginated list of all elasticity calculations.',
        responses={200: CalculationResultSerializer(many=True)},
    ),
    retrieve=extend_schema(
        tags=['Elasticity Analysis'],
        summary='Get calculation result',
        description='Retrieve a specific elasticity calculation by ID. '
                    'Use this endpoint to poll for async calculation results.',
        responses={
            200: CalculationResultSerializer,
            404: {'description': 'Calculation not found'},
        },
    ),
)
class CalculationViewSet(viewsets.ReadOnlyModelViewSet):
    """
    API endpoints for elasticity calculations.

    Anonymous access - no authentication required.
    Rate limiting via custom decorators.

    Endpoints:
        GET /api/v1/elasticity/          - List recent calculations
        GET /api/v1/elasticity/{id}/     - Get specific calculation
        POST /api/v1/elasticity/calculate/ - Create new calculation (async)
        GET /api/v1/elasticity/recent/   - Get calculations from last 24h by IP
    """

    permission_classes = [AllowAny]
    queryset = ElasticityCalculation.objects.all()

    def get_serializer_class(self):
        """Use appropriate serializer based on action."""
        return CalculationResultSerializer

    def get_queryset(self):
        """Return all calculations ordered by creation date."""
        return ElasticityCalculation.objects.order_by('-created_at')

    @extend_schema(
        tags=['Elasticity Analysis'],
        summary='Create new calculation',
        description='Submit a new elasticity calculation request. '
                    'Processing is async - poll GET /elasticity/{id}/ for results. '
                    'Rate limit: 10 requests/hour per IP.',
        request=CalculationRequestSerializer,
        responses={
            202: CalculationResultSerializer,
            400: {'description': 'Validation error'},
            429: {'description': 'Rate limit exceeded'},
        },
        examples=[
            OpenApiExample(
                'Midpoint Calculation',
                value={
                    'method': 'midpoint',
                    'start_date': '2025-11-01T00:00:00Z',
                    'end_date': '2025-11-27T23:59:59Z',
                    'window_size': 'daily',
                },
                request_only=True,
            ),
            OpenApiExample(
                'Regression Calculation',
                value={
                    'method': 'regression',
                    'start_date': '2025-11-01T00:00:00Z',
                    'end_date': '2025-11-27T23:59:59Z',
                    'window_size': 'hourly',
                },
                request_only=True,
            ),
        ],
    )
    @action(
        methods=['post'],
        detail=False,
        url_path='calculate'
    )
    def calculate(self, request):
        """
        Create new elasticity calculation.

        Execution mode depends on ELASTICITY_ASYNC_ENABLED setting:
        - Async (True): Returns 202, processes in background via Celery
        - Sync (False): Executes immediately, returns result or error

        Request body:
        {
            "method": "midpoint" | "regression",
            "start_date": "2025-11-01T00:00:00Z",
            "end_date": "2025-11-18T23:59:59Z",
            "window_size": "hourly" | "daily" | "weekly"
        }

        Rate limit: 10 requests per hour per IP.
        """
        # Validate request
        serializer = CalculationRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        # Get client IP for tracking
        client_ip = get_client_ip(request)

        # Create calculation record
        calculation = ElasticityCalculation.objects.create(
            client_ip=client_ip,
            method=serializer.validated_data['method'].upper(),
            start_date=serializer.validated_data['start_date'],
            end_date=serializer.validated_data['end_date'],
            window_size=serializer.validated_data['window_size'].upper(),
            status='PENDING'
        )

        logger.info(
            f"Created calculation {calculation.id} for IP {client_ip}",
            extra={
                'calculation_id': str(calculation.id),
                'client_ip': client_ip,
                'method': calculation.method,
                'async_enabled': ASYNC_ENABLED
            }
        )

        # Execute based on mode
        if ASYNC_ENABLED:
            # Async mode: try to queue task, fall back to sync on Redis error
            return self._execute_async(calculation)
        else:
            # Sync mode: execute directly in this request
            return self._execute_sync(calculation)

    def _execute_sync(self, calculation):
        """
        Execute calculation synchronously (blocking).

        This mode is used when:
        - ELASTICITY_ASYNC_ENABLED=False
        - Redis/Celery is unavailable (fallback from async)

        Trade-off: Request takes 5-15 seconds but always completes.
        """
        logger.info(
            f"Executing calculation {calculation.id} in SYNC mode",
            extra={'calculation_id': str(calculation.id)}
        )

        try:
            # Execute calculation directly
            result = execute_calculation(str(calculation.id))

            # Refresh from DB to get updated fields
            calculation.refresh_from_db()

            # Return appropriate response based on result
            result_serializer = CalculationResultSerializer(calculation)

            if result.get('status') == 'COMPLETED':
                return Response(
                    result_serializer.data,
                    status=status.HTTP_200_OK
                )
            else:
                # Calculation failed (insufficient data, etc.)
                return Response(
                    result_serializer.data,
                    status=status.HTTP_200_OK  # Still 200, status in body shows FAILED
                )

        except Exception as exc:
            logger.error(
                f"Sync calculation {calculation.id} failed: {exc}",
                exc_info=True,
                extra={'calculation_id': str(calculation.id)}
            )

            # Mark as failed
            calculation.status = 'FAILED'
            calculation.error_message = f"Calculation error: {str(exc)}"
            calculation.completed_at = timezone.now()
            calculation.save(update_fields=['status', 'error_message', 'completed_at', 'updated_at'])

            result_serializer = CalculationResultSerializer(calculation)
            return Response(
                result_serializer.data,
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    def _execute_async(self, calculation):
        """
        Execute calculation asynchronously via Celery.

        Falls back to sync mode if Redis is unavailable.
        """
        try:
            # Try to queue the Celery task
            calculate_elasticity_async.delay(str(calculation.id))

            logger.info(
                f"Queued calculation {calculation.id} to Celery",
                extra={'calculation_id': str(calculation.id)}
            )

            # Return 202 Accepted - client should poll for results
            result_serializer = CalculationResultSerializer(calculation)
            return Response(
                result_serializer.data,
                status=status.HTTP_202_ACCEPTED
            )

        except Exception as exc:
            # Redis/Celery error - fall back to sync mode
            logger.warning(
                f"Failed to queue task for {calculation.id}, falling back to sync: {exc}",
                extra={
                    'calculation_id': str(calculation.id),
                    'exception_type': type(exc).__name__
                }
            )

            # Execute synchronously as fallback
            return self._execute_sync(calculation)

    @extend_schema(
        tags=['Elasticity Analysis'],
        summary='Get recent calculations by IP',
        description='Retrieve calculations from the last 24 hours for the client IP. '
                    'Allows anonymous users to track their calculation history.',
        responses={200: CalculationResultSerializer(many=True)},
    )
    @action(
        methods=['get'],
        detail=False,
        url_path='recent'
    )
    def recent(self, request):
        """
        Get calculations from last 24h for client's IP.

        Allows anonymous users to see their recent calculations
        without authentication.

        Returns:
            List of calculations from last 24 hours
        """
        client_ip = get_client_ip(request)

        # Get calculations from last 24 hours for this IP
        cutoff_time = timezone.now() - timezone.timedelta(hours=24)
        calculations = ElasticityCalculation.objects.filter(
            client_ip=client_ip,
            created_at__gte=cutoff_time
        ).order_by('-created_at')

        serializer = CalculationResultSerializer(calculations, many=True)

        return Response({
            'count': calculations.count(),
            'results': serializer.data
        })

    @extend_schema(
        tags=['Elasticity Analysis'],
        summary='Get calculation status',
        description='Lightweight endpoint for polling calculation status. '
                    'Use this for efficient status checks during async processing.',
        responses={
            200: {
                'type': 'object',
                'properties': {
                    'id': {'type': 'string', 'format': 'uuid'},
                    'status': {'type': 'string', 'enum': ['PENDING', 'PROCESSING', 'COMPLETED', 'FAILED']},
                    'is_complete': {'type': 'boolean'},
                    'has_error': {'type': 'boolean'},
                    'created_at': {'type': 'string', 'format': 'date-time'},
                    'completed_at': {'type': 'string', 'format': 'date-time', 'nullable': True},
                },
            },
            404: {'description': 'Calculation not found'},
        },
    )
    @action(
        methods=['get'],
        detail=True,
        url_path='status'
    )
    def calculation_status(self, request, pk=None):
        """
        Get calculation status (lightweight endpoint for polling).

        Returns only status and basic info for efficient polling.
        """
        calculation = self.get_object()

        return Response({
            'id': str(calculation.id),
            'status': calculation.status,
            'is_complete': calculation.is_complete,
            'has_error': calculation.has_error,
            'created_at': calculation.created_at,
            'completed_at': calculation.completed_at,
        })
