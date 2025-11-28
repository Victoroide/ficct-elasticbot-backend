from rest_framework import serializers


class ScenarioRequestSerializer(serializers.Serializer):
    price_initial = serializers.DecimalField(max_digits=8, decimal_places=4)
    price_final = serializers.DecimalField(max_digits=8, decimal_places=4)
    quantity_initial = serializers.DecimalField(max_digits=12, decimal_places=2)
    quantity_final = serializers.DecimalField(max_digits=12, decimal_places=2)
