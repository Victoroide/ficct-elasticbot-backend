"""
Serializer for elasticity calculation results.
"""
from rest_framework import serializers
from apps.elasticity.models import ElasticityCalculation


class CalculationResultSerializer(serializers.ModelSerializer):
    """
    Serializes calculation results for API responses.

    Example response:
    {
        "id": "uuid",
        "status": "completed",
        "elasticity_coefficient": -0.87,
        "classification": "inelastic",
        "confidence_interval_95": {
            "lower": -1.12,
            "upper": -0.62
        },
        "r_squared": 0.84,
        "data_points_used": 432,
        "created_at": "2025-11-18T20:00:00Z"
    }
    """

    elasticity_magnitude = serializers.SerializerMethodField()
    confidence_interval_95 = serializers.SerializerMethodField()
    is_significant = serializers.SerializerMethodField()
    classification_label = serializers.SerializerMethodField()

    class Meta:
        model = ElasticityCalculation
        fields = [
            'id',
            'status',
            'method',
            'start_date',
            'end_date',
            'window_size',
            # Core results
            'elasticity_coefficient',
            'elasticity_magnitude',
            'classification',
            'classification_label',
            # Reliability (important for UI)
            'is_reliable',
            'reliability_note',
            # Statistical metrics
            'confidence_interval_95',
            'r_squared',
            'standard_error',
            'is_significant',
            # Data quality
            'data_points_used',
            'average_data_quality',
            # Errors and metadata
            'error_message',
            'created_at',
            'completed_at',
            'calculation_metadata',
        ]
        read_only_fields = fields

    def get_elasticity_magnitude(self, obj):
        """Return absolute value of elasticity."""
        if obj.elasticity_coefficient:
            return float(abs(obj.elasticity_coefficient))
        return None

    def get_confidence_interval_95(self, obj):
        """Format confidence interval as dict."""
        if obj.confidence_interval_lower and obj.confidence_interval_upper:
            return {
                'lower': float(obj.confidence_interval_lower),
                'upper': float(obj.confidence_interval_upper)
            }
        return None

    def get_is_significant(self, obj):
        """Determine statistical significance."""
        if obj.confidence_interval_lower and obj.confidence_interval_upper:
            # Significant if CI doesn't include zero
            lower = float(obj.confidence_interval_lower)
            upper = float(obj.confidence_interval_upper)
            return not (lower <= 0 <= upper)
        return None

    def get_classification_label(self, obj):
        """
        Return human-readable Spanish classification with reliability caveat.

        The sign of elasticity coefficient indicates direction:
        - Negative Ed: Normal demand (price up -> quantity down)
        - Positive Ed: Giffen/Veblen goods or data artifact
        """
        if not obj.classification:
            return None

        # Base classification labels
        labels = {
            'ELASTIC': 'Demanda Elástica',
            'INELASTIC': 'Demanda Inelástica',
            'UNITARY': 'Elasticidad Unitaria',
        }
        base_label = labels.get(obj.classification, obj.classification)

        # Add reliability warning if needed
        if not obj.is_reliable:
            return f"{base_label} (resultado no confiable)"

        return base_label


class CalculationListSerializer(serializers.ModelSerializer):
    """Lightweight serializer for listing calculations."""

    elasticity_magnitude = serializers.SerializerMethodField()

    class Meta:
        model = ElasticityCalculation
        fields = [
            'id',
            'status',
            'method',
            'elasticity_coefficient',
            'elasticity_magnitude',
            'classification',
            'data_points_used',
            'created_at',
        ]
        read_only_fields = fields

    def get_elasticity_magnitude(self, obj):
        """Return absolute value."""
        if obj.elasticity_coefficient:
            return float(abs(obj.elasticity_coefficient))
        return None
