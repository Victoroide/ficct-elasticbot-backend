"""
Serializers for AI interpretation requests and responses.
"""
from rest_framework import serializers


class InterpretationRequestSerializer(serializers.Serializer):
    """
    Request serializer for AI interpretation.

    Example:
    {
        "calculation_id": "550e8400-e29b-41d4-a716-446655440000"
    }
    """

    calculation_id = serializers.UUIDField(
        required=True,
        help_text="UUID of completed ElasticityCalculation"
    )


class InterpretationResponseSerializer(serializers.Serializer):
    """
    Response serializer for AI interpretation.

    Example:
    {
        "calculation_id": "550e8400-e29b-41d4-a716-446655440000",
        "interpretation": "El coeficiente de elasticidad...",
        "generated_at": "2025-11-18T20:30:00Z",
        "cached": false,
        "model": "meta.llama-4-maverick-v1:0"
    }
    """

    calculation_id = serializers.UUIDField()
    interpretation = serializers.CharField()
    generated_at = serializers.DateTimeField()
    cached = serializers.BooleanField()
    model = serializers.CharField()
