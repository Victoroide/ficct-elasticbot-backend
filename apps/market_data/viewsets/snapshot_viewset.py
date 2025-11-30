"""
ViewSet for market snapshots.

Optimized with:
- Query optimization (only returns high-quality data)
- Redis caching recommended in production
- Backend-driven aggregation for chart visualization
"""
from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import AllowAny
from drf_spectacular.utils import extend_schema, extend_schema_view, OpenApiExample, OpenApiParameter
from apps.market_data.models import MarketSnapshot, MacroeconomicIndicator
from apps.market_data.serializers import MarketSnapshotSerializer, MacroeconomicIndicatorSerializer
from apps.market_data.services import aggregation_service
from apps.market_data.services.price_change_service import PriceChangeService
from dateutil import parser as dateutil_parser


@extend_schema_view(
    list=extend_schema(
        tags=['Market Data'],
        summary='List market snapshots',
        description='Retrieve paginated list of USDT/BOB market snapshots from Binance P2P. '
                    'Only high-quality data (score >= 0.7) is returned.',
        responses={200: MarketSnapshotSerializer(many=True)},
    ),
    retrieve=extend_schema(
        tags=['Market Data'],
        summary='Get specific snapshot',
        description='Retrieve a specific market snapshot by ID.',
        responses={
            200: MarketSnapshotSerializer,
            404: {'description': 'Snapshot not found'},
        },
    ),
)
class SnapshotViewSet(viewsets.ReadOnlyModelViewSet):
    """
    API endpoints for market data snapshots.

    Anonymous read-only access.

    Endpoints:
        GET /api/v1/market-data/          - List snapshots
        GET /api/v1/market-data/{id}/     - Get specific snapshot
        GET /api/v1/market-data/latest/   - Get most recent snapshot

    Performance:
        - List cached for 15 minutes
        - Latest cached for 5 minutes
        - Only high-quality data (score >= 0.7) returned
    """

    permission_classes = [AllowAny]
    serializer_class = MarketSnapshotSerializer
    queryset = MarketSnapshot.objects.all()

    def get_queryset(self):
        """Return snapshots ordered by timestamp."""
        return MarketSnapshot.objects.filter(
            data_quality_score__gte=0.7  # Only high-quality data
        ).order_by('-timestamp').only(
            'id', 'timestamp', 'average_sell_price', 'average_buy_price',
            'total_volume', 'spread_percentage', 'num_active_traders',
            'data_quality_score'
        )

    @extend_schema(
        tags=['Market Data'],
        summary='Get latest snapshot with price changes',
        description='Retrieve the most recent USDT/BOB market snapshot enriched with '
                    'price change percentage vs previous snapshot and market premium '
                    'vs BCB official exchange rate. Returns current market prices, '
                    'trading volume, and calculated percentage changes for UI display.',
        responses={
            200: {
                'type': 'object',
                'properties': {
                    'id': {'type': 'string', 'format': 'uuid'},
                    'timestamp': {'type': 'string', 'format': 'date-time'},
                    'average_sell_price': {'type': 'number'},
                    'average_buy_price': {'type': 'number'},
                    'total_volume': {'type': 'number'},
                    'spread_percentage': {'type': 'number'},
                    'data_quality_score': {'type': 'number'},
                    'price_change_percentage': {'type': 'number', 'nullable': True},
                    'price_change_direction': {'type': 'string', 'enum': ['up', 'down', 'neutral']},
                    'previous_price': {'type': 'number', 'nullable': True},
                    'is_first_snapshot': {'type': 'boolean'},
                    'time_gap_minutes': {'type': 'integer', 'nullable': True},
                    'time_gap_warning': {'type': 'boolean'},
                    'market_premium_percentage': {'type': 'number', 'nullable': True},
                    'bcb_official_rate': {'type': 'number', 'nullable': True},
                    'bcb_rate_date': {'type': 'string', 'format': 'date', 'nullable': True},
                    'bcb_rate_updated_at': {'type': 'string', 'format': 'date-time', 'nullable': True},
                    'bcb_rate_stale': {'type': 'boolean'},
                },
            },
            404: {'description': 'No market data available'},
        },
        examples=[
            OpenApiExample(
                'Successful Response with Price Changes',
                value={
                    'id': '12345678-1234-1234-1234-123456789012',
                    'timestamp': '2025-11-30T01:02:00+00:00',
                    'average_sell_price': 10.09,
                    'average_buy_price': 10.14,
                    'total_volume': 175600.0,
                    'spread_percentage': 0.46,
                    'data_quality_score': 0.80,
                    
                    'price_change_percentage': 0.00,
                    'price_change_direction': 'neutral',
                    'previous_price': 10.09,
                    'is_first_snapshot': False,
                    'time_gap_minutes': 32,
                    'time_gap_warning': False,
                    
                    'market_premium_percentage': 45.01,
                    'bcb_official_rate': 6.96,
                    'bcb_rate_date': '2025-11-29',
                    'bcb_rate_updated_at': '2025-11-29T08:00:00+00:00',
                    'bcb_rate_stale': False,
                },
                response_only=True,
            ),
        ],
    )
    @action(methods=['get'], detail=False, url_path='latest')
    def latest(self, request):
        """
        Get most recent market snapshot with price changes and market premium.

        Returns:
            Latest snapshot enriched with:
            - Price change percentage vs previous snapshot
            - Market premium percentage vs BCB official rate
            - Direction indicators for UI display
            - Previous snapshot reference
            - BCB rate information and staleness flags
        """
        snapshot = self.get_queryset().first()

        if not snapshot:
            return Response({
                'error': 'No market data available',
                'detail': 'Please wait for data collection to complete'
            }, status=404)

        # Use price change service to enrich the data
        service = PriceChangeService()
        enriched_data = service.enrich_snapshot_data(snapshot)
        
        return Response(enriched_data)

    @extend_schema(
        tags=['Market Data'],
        summary='Get latest BCB indicator',
        description='Retrieve the most recent macroeconomic indicator with official '
                    'BCB exchange rate. Returns the latest record with non-null '
                    'official_exchange_rate.',
        responses={
            200: MacroeconomicIndicatorSerializer,
            404: {'description': 'No indicators available'},
        },
        examples=[
            OpenApiExample(
                'Successful Response',
                value={
                    'id': 1,
                    'date': '2025-11-27',
                    'official_exchange_rate': '6.96',
                    'monthly_inflation_rate': None,
                    'accumulated_inflation': None,
                    'source': 'BCB',
                    'raw_data': {
                        'venta': '6.96',
                        'compra': '6.86',
                        'url': 'https://www.bcb.gob.bo/',
                        'scraped_at': '2025-11-27T08:00:00Z'
                    },
                    'created_at': '2025-11-27T08:00:00Z',
                },
                response_only=True,
            ),
        ],
    )
    @action(methods=['get'], detail=False, url_path='indicators/latest')
    def indicators_latest(self, request):
        """
        Get most recent macroeconomic indicator with BCB exchange rate.

        Returns:
            Latest indicator with official BCB exchange rate data
        """
        indicator = MacroeconomicIndicator.objects.filter(
            official_exchange_rate__isnull=False
        ).order_by('-date').first()

        if not indicator:
            return Response({
                'error': 'No indicators available',
                'detail': 'BCB exchange rate data not yet collected. '
                         'Please ensure the data collection task has run.'
            }, status=404)

        serializer = MacroeconomicIndicatorSerializer(indicator)
        return Response(serializer.data)

    @extend_schema(
        tags=['Market Data'],
        summary='Get OHLC data coverage',
        description='Returns the date range and statistics for high-quality external OHLC data. '
                    'Use this to determine valid date ranges for elasticity calculations.',
        responses={
            200: {
                'type': 'object',
                'properties': {
                    'coverage_start': {'type': 'string', 'format': 'date-time'},
                    'coverage_end': {'type': 'string', 'format': 'date-time'},
                    'total_records': {'type': 'integer'},
                    'span_days': {'type': 'number'},
                    'span_hours': {'type': 'number'},
                    'data_source': {'type': 'string'},
                    'quality_threshold': {'type': 'number'},
                    'timeframes': {'type': 'array', 'items': {'type': 'string'}},
                },
            },
            404: {'description': 'No OHLC data available'},
        },
        examples=[
            OpenApiExample(
                'Successful Response',
                value={
                    'coverage_start': '2025-11-20T18:00:00Z',
                    'coverage_end': '2025-11-29T01:00:00Z',
                    'total_records': 200,
                    'span_days': 8.29,
                    'span_hours': 199,
                    'data_source': 'external_ohlc_api',
                    'quality_threshold': 0.95,
                    'timeframes': ['1h'],
                },
                response_only=True,
            ),
        ],
    )
    @action(methods=['get'], detail=False, url_path='coverage')
    def coverage(self, request):
        """
        Get OHLC data coverage information.

        Returns date range, record count, and metadata for high-quality
        external OHLC data. Useful for frontend to set valid date picker bounds.
        
        Only includes data with:
        - data_quality_score >= 0.95 (external API marker)
        - raw_response.source = 'external_ohlc_api'
        """
        # Quality threshold for external OHLC data
        QUALITY_THRESHOLD = 0.95
        
        # Query external OHLC data only
        external_data = MarketSnapshot.objects.filter(
            data_quality_score__gte=QUALITY_THRESHOLD
        )
        
        total_records = external_data.count()
        
        if total_records == 0:
            return Response({
                'error': 'No OHLC data available',
                'detail': 'External OHLC data has not been imported. '
                         'Run: python manage.py import_ohlc_history --confirm'
            }, status=404)
        
        first = external_data.order_by('timestamp').first()
        last = external_data.order_by('timestamp').last()
        
        # Calculate span
        span = last.timestamp - first.timestamp
        span_hours = span.total_seconds() / 3600
        span_days = span_hours / 24
        
        # Get unique timeframes from raw_response
        timeframes = set()
        for snap in external_data.only('raw_response')[:100]:  # Sample first 100
            if snap.raw_response and 'timeframe' in snap.raw_response:
                timeframes.add(snap.raw_response['timeframe'])
        
        return Response({
            'coverage_start': first.timestamp.isoformat(),
            'coverage_end': last.timestamp.isoformat(),
            'total_records': total_records,
            'span_days': round(span_days, 2),
            'span_hours': round(span_hours, 0),
            'data_source': 'external_ohlc_api',
            'quality_threshold': QUALITY_THRESHOLD,
            'timeframes': sorted(list(timeframes)) if timeframes else ['1h'],
        })

    @extend_schema(
        tags=['Market Data'],
        summary='Get aggregated market data for charts',
        description=(
            'Returns pre-aggregated market data for chart visualization. '
            'This endpoint replaces heavy frontend aggregation with efficient '
            'server-side processing.\n\n'
            '**Data sources:**\n'
            '- `p2p`: Historical P2P scrape data (quality=0.8)\n'
            '- `ohlc`: External OHLC API data (quality>=0.95)\n'
            '- `all`: Both sources combined\n\n'
            '**Granularities:**\n'
            '- `hourly`: Individual data points (best for 24h range)\n'
            '- `daily`: Averaged by day (best for 7d-30d range)\n'
            '- `weekly`: Averaged by ISO week (best for 90d+ range)\n\n'
            '**Note:** This endpoint is optimized for the "Historial de Precios" '
            'chart. The frontend should render the returned `points` array directly '
            'without additional aggregation.'
        ),
        parameters=[
            OpenApiParameter(
                name='time_range',
                description='Preset time range. Ignored if start_date/end_date provided.',
                required=False,
                type=str,
                enum=['24h', '7d', '30d', '90d'],
            ),
            OpenApiParameter(
                name='start_date',
                description='Custom start date (ISO 8601). Use with end_date.',
                required=False,
                type=str,
            ),
            OpenApiParameter(
                name='end_date',
                description='Custom end date (ISO 8601). Use with start_date.',
                required=False,
                type=str,
            ),
            OpenApiParameter(
                name='granularity',
                description='Aggregation granularity.',
                required=False,
                type=str,
                enum=['hourly', 'daily', 'weekly'],
                default='daily',
            ),
            OpenApiParameter(
                name='source',
                description='Data source filter.',
                required=False,
                type=str,
                enum=['p2p', 'ohlc', 'all'],
                default='all',
            ),
        ],
        responses={
            200: {
                'type': 'object',
                'properties': {
                    'time_range': {'type': 'string', 'example': '7d'},
                    'granularity': {'type': 'string', 'example': 'daily'},
                    'coverage_start': {'type': 'string', 'format': 'date-time'},
                    'coverage_end': {'type': 'string', 'format': 'date-time'},
                    'span_days': {'type': 'number', 'example': 6.5},
                    'data_source': {'type': 'string', 'example': 'p2p_scrape_json'},
                    'total_records': {'type': 'integer', 'example': 200},
                    'aggregated_points': {'type': 'integer', 'example': 7},
                    'points': {
                        'type': 'array',
                        'items': {
                            'type': 'object',
                            'properties': {
                                'timestamp': {'type': 'string', 'format': 'date-time'},
                                'average_buy_price': {'type': 'number'},
                                'average_sell_price': {'type': 'number'},
                                'total_volume': {'type': 'number'},
                                'spread_percentage': {'type': 'number'},
                                'record_count': {'type': 'integer'},
                            },
                        },
                    },
                },
            },
            400: {'description': 'Invalid parameters'},
        },
        examples=[
            OpenApiExample(
                'Daily aggregation for 7 days',
                value={
                    'time_range': '7d',
                    'granularity': 'daily',
                    'coverage_start': '2025-11-22T00:00:00+00:00',
                    'coverage_end': '2025-11-28T00:00:00+00:00',
                    'span_days': 6.0,
                    'data_source': 'p2p_scrape_json',
                    'total_records': 168,
                    'aggregated_points': 7,
                    'points': [
                        {
                            'timestamp': '2025-11-22T00:00:00+00:00',
                            'average_buy_price': 6.92,
                            'average_sell_price': 7.05,
                            'total_volume': 0.0,
                            'spread_percentage': 1.86,
                            'record_count': 24,
                        },
                    ],
                },
                response_only=True,
            ),
        ],
    )
    @action(methods=['get'], detail=False, url_path='aggregated')
    def aggregated(self, request):
        """
        Get aggregated market data for chart visualization.

        This endpoint provides backend-driven aggregation, replacing the heavy
        frontend logic with efficient server-side processing.

        The frontend should:
        1. Call this endpoint with the desired time_range and granularity
        2. Render the returned points array directly
        3. Display coverage information from the response metadata

        The frontend should NOT:
        - Perform additional aggregation or averaging
        - Calculate spreads or volumes
        - Fill in missing data points
        """
        # Parse parameters
        time_range = request.query_params.get('time_range')
        start_date_str = request.query_params.get('start_date')
        end_date_str = request.query_params.get('end_date')
        granularity = request.query_params.get('granularity', 'daily')
        source = request.query_params.get('source', 'all')

        # Parse custom dates if provided
        start_date = None
        end_date = None
        
        if start_date_str:
            try:
                start_date = dateutil_parser.isoparse(start_date_str)
            except (ValueError, TypeError):
                return Response(
                    {'error': 'Invalid start_date format. Use ISO 8601.'},
                    status=400
                )

        if end_date_str:
            try:
                end_date = dateutil_parser.isoparse(end_date_str)
            except (ValueError, TypeError):
                return Response(
                    {'error': 'Invalid end_date format. Use ISO 8601.'},
                    status=400
                )

        # If one date provided, require both
        if (start_date and not end_date) or (end_date and not start_date):
            return Response(
                {'error': 'Both start_date and end_date are required for custom range.'},
                status=400
            )

        try:
            result = aggregation_service.get_aggregated_data(
                time_range=time_range,
                start_date=start_date,
                end_date=end_date,
                granularity=granularity,
                source=source,
            )
            return Response(result)

        except ValueError as e:
            return Response({'error': str(e)}, status=400)
        except Exception as e:
            return Response(
                {'error': f'Aggregation failed: {str(e)}'},
                status=500
            )
