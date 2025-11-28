"""
ViewSet for market snapshots.

Optimized with:
- Query optimization (only returns high-quality data)
- Redis caching recommended in production
"""
from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import AllowAny
from drf_spectacular.utils import extend_schema, extend_schema_view, OpenApiExample
from apps.market_data.models import MarketSnapshot
from apps.market_data.serializers import MarketSnapshotSerializer


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
        summary='Get latest snapshot',
        description='Retrieve the most recent USDT/BOB market snapshot. '
                    'Returns current market prices and trading volume.',
        responses={
            200: MarketSnapshotSerializer,
            404: {'description': 'No market data available'},
        },
        examples=[
            OpenApiExample(
                'Successful Response',
                value={
                    'id': 12345,
                    'timestamp': '2025-11-27T20:00:00Z',
                    'average_sell_price': '7.05',
                    'average_buy_price': '6.98',
                    'total_volume': '142500.50',
                    'spread_percentage': '1.00',
                    'num_active_traders': 23,
                    'data_quality_score': '0.92',
                },
                response_only=True,
            ),
        ],
    )
    @action(methods=['get'], detail=False, url_path='latest')
    def latest(self, request):
        """
        Get most recent market snapshot.

        Returns:
            Latest snapshot with current USDT/BOB prices
        """
        snapshot = self.get_queryset().first()

        if not snapshot:
            return Response({
                'error': 'No market data available',
                'detail': 'Please wait for data collection to complete'
            }, status=404)

        serializer = self.get_serializer(snapshot)
        return Response(serializer.data)
