"""
ViewSet for AI-powered economic interpretations.

Rate limited to 5 requests/hour per IP due to AWS costs.
"""
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import AllowAny
from django.utils import timezone
from drf_spectacular.utils import extend_schema, OpenApiExample
from apps.elasticity.models import ElasticityCalculation
from apps.ai_interpretation.services import BedrockClient, InterpretationCache
from apps.ai_interpretation.serializers import (
    InterpretationRequestSerializer
)
import logging

logger = logging.getLogger(__name__)


class InterpretationViewSet(viewsets.ViewSet):
    """
    API endpoints for AI interpretations.

    Endpoints:
        POST /api/v1/interpret/generate/ - Generate interpretation for calculation

    Rate limit: 5 requests/hour per IP (expensive AWS Bedrock calls)
    """

    permission_classes = [AllowAny]

    @extend_schema(
        tags=['AI Interpretation'],
        summary='Generate AI interpretation',
        description='Generate an AI-powered economic interpretation for a completed '
                    'elasticity calculation using AWS Bedrock (Llama 4). '
                    'Rate limit: 5 requests/hour per IP due to AWS costs.',
        request=InterpretationRequestSerializer,
        responses={
            200: {
                'type': 'object',
                'properties': {
                    'calculation_id': {'type': 'string', 'format': 'uuid'},
                    'interpretation': {'type': 'string'},
                    'generated_at': {'type': 'string', 'format': 'date-time'},
                    'cached': {'type': 'boolean'},
                    'model': {'type': 'string'},
                },
            },
            400: {'description': 'Calculation not complete or invalid request'},
            404: {'description': 'Calculation not found'},
            429: {'description': 'Rate limit exceeded (5/hour)'},
            500: {'description': 'AI generation failed'},
        },
        examples=[
            OpenApiExample(
                'Request Example',
                value={'calculation_id': '550e8400-e29b-41d4-a716-446655440000'},
                request_only=True,
            ),
            OpenApiExample(
                'Successful Response',
                value={
                    'calculation_id': '550e8400-e29b-41d4-a716-446655440000',
                    'interpretation': 'El coeficiente de elasticidad calculado es -0.87, '
                                      'lo cual indica una demanda inelastica...',
                    'generated_at': '2025-11-27T20:30:00Z',
                    'cached': False,
                    'model': 'meta.llama-4-maverick-v1:0',
                },
                response_only=True,
            ),
        ],
    )
    @action(
        methods=['post'],
        detail=False,
        url_path='generate'
    )
    def generate(self, request):
        """
        Generate AI interpretation for elasticity calculation.

        Request body:
        {
            "calculation_id": "550e8400-e29b-41d4-a716-446655440000"
        }

        Returns:
        {
            "calculation_id": "...",
            "interpretation": "250-300 word Spanish interpretation",
            "generated_at": "2025-11-18T20:30:00Z",
            "cached": false
        }

        Rate limit: 5 requests/hour per IP
        """
        # Validate request
        serializer = InterpretationRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        calculation_id = serializer.validated_data['calculation_id']

        # Fetch calculation
        try:
            calculation = ElasticityCalculation.objects.get(id=calculation_id)
        except ElasticityCalculation.DoesNotExist:
            return Response(
                {'error': 'Calculation not found'},
                status=status.HTTP_404_NOT_FOUND
            )

        # Verify calculation is complete
        if not calculation.is_complete:
            return Response(
                {
                    'error': 'Calculation not complete',
                    'detail': f'Current status: {calculation.status}'
                },
                status=status.HTTP_400_BAD_REQUEST
            )

        # Check cache first
        context = {
            'method': calculation.method,
            'data_points': calculation.data_points_used,
            'start_date': calculation.start_date.isoformat(),
            'end_date': calculation.end_date.isoformat(),
            'data_quality': calculation.average_data_quality
        }

        cached_interpretation = InterpretationCache.get(
            float(calculation.elasticity_coefficient),
            calculation.classification,
            context
        )

        if cached_interpretation:
            logger.info(f"Returning cached interpretation for {calculation_id}")
            response_data = {
                'calculation_id': str(calculation.id),
                'interpretation': cached_interpretation,
                'generated_at': timezone.now(),
                'cached': True,
                'model': 'cached'
            }
            return Response(response_data)

        # Generate new interpretation
        bedrock_client = BedrockClient()

        try:
            interpretation = bedrock_client.generate_interpretation(
                elasticity_coefficient=float(calculation.elasticity_coefficient),
                classification=calculation.classification.lower(),
                data_context=context
            )

            # Cache for 24 hours
            InterpretationCache.set(
                float(calculation.elasticity_coefficient),
                calculation.classification,
                context,
                interpretation
            )

            response_data = {
                'calculation_id': str(calculation.id),
                'interpretation': interpretation,
                'generated_at': timezone.now(),
                'cached': False,
                'model': BedrockClient.MODEL_ID if not bedrock_client.mock_mode else 'mock'
            }

            logger.info(f"Generated new interpretation for {calculation_id}")

            return Response(response_data)

        except Exception as e:
            logger.error(f"Failed to generate interpretation: {e}", exc_info=True)
            return Response(
                {
                    'error': 'Interpretation generation failed',
                    'detail': str(e)
                },
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
