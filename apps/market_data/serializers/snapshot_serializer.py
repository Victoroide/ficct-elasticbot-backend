"""
Serializer for market snapshots.
"""
from rest_framework import serializers
from apps.market_data.models import MarketSnapshot


class MarketSnapshotSerializer(serializers.ModelSerializer):
    """
    Serializes market snapshot data for API responses.
    """

    is_high_quality = serializers.BooleanField(read_only=True)

    class Meta:
        model = MarketSnapshot
        fields = [
            'id',
            'timestamp',
            'average_sell_price',
            'average_buy_price',
            'total_volume',
            'spread_percentage',
            'num_active_traders',
            'data_quality_score',
            'is_high_quality',
            'created_at',
        ]
        read_only_fields = fields
