"""
Serializer for MacroeconomicIndicator model.
"""
from rest_framework import serializers
from apps.market_data.models import MacroeconomicIndicator


class MacroeconomicIndicatorSerializer(serializers.ModelSerializer):
    """
    Serializes BCB exchange rate and other macroeconomic indicators.

    Used for providing official exchange rate context to the frontend.
    """

    official_exchange_rate = serializers.DecimalField(
        max_digits=8,
        decimal_places=4,
        coerce_to_string=True
    )

    monthly_inflation_rate = serializers.DecimalField(
        max_digits=6,
        decimal_places=4,
        coerce_to_string=True,
        required=False,
        allow_null=True
    )

    accumulated_inflation = serializers.DecimalField(
        max_digits=8,
        decimal_places=4,
        coerce_to_string=True,
        required=False,
        allow_null=True
    )

    class Meta:
        model = MacroeconomicIndicator
        fields = [
            'id',
            'date',
            'official_exchange_rate',
            'monthly_inflation_rate',
            'accumulated_inflation',
            'source',
            'raw_data',
            'created_at',
        ]
        read_only_fields = ['id', 'created_at']
