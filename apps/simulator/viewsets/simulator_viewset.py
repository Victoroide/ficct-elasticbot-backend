from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import AllowAny
from drf_spectacular.utils import extend_schema, OpenApiExample
from apps.simulator.services import ScenarioEngine
from apps.simulator.serializers import ScenarioRequestSerializer


class SimulatorViewSet(viewsets.ViewSet):
    """
    API endpoints for hypothetical elasticity scenarios.

    Allows users to test what-if scenarios without affecting real data.
    """

    permission_classes = [AllowAny]

    @extend_schema(
        tags=['Scenario Simulator'],
        summary='Simulate elasticity scenario',
        description='Calculate elasticity for a hypothetical price-quantity scenario. '
                    'Useful for what-if analysis without using historical data.',
        request=ScenarioRequestSerializer,
        responses={
            200: {
                'type': 'object',
                'properties': {
                    'elasticity': {'type': 'number', 'format': 'float'},
                    'abs_value': {'type': 'number', 'format': 'float'},
                    'classification': {
                        'type': 'string',
                        'enum': ['elastic', 'inelastic', 'unitary'],
                    },
                    'percentage_change_quantity': {'type': 'number'},
                    'percentage_change_price': {'type': 'number'},
                },
            },
            400: {'description': 'Validation error'},
        },
        examples=[
            OpenApiExample(
                'USDT/BOB Scenario',
                value={
                    'price_initial': '7.00',
                    'price_final': '7.20',
                    'quantity_initial': '125000',
                    'quantity_final': '118000',
                },
                request_only=True,
            ),
            OpenApiExample(
                'Inelastic Result',
                value={
                    'elasticity': -0.9234,
                    'abs_value': 0.9234,
                    'classification': 'inelastic',
                    'percentage_change_quantity': -5.77,
                    'percentage_change_price': 2.82,
                },
                response_only=True,
            ),
        ],
    )
    @action(methods=['post'], detail=False, url_path='scenario')
    def scenario(self, request):
        """Simulate a hypothetical elasticity scenario."""
        serializer = ScenarioRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        engine = ScenarioEngine()
        result = engine.simulate_scenario(
            price_initial=serializer.validated_data['price_initial'],
            price_final=serializer.validated_data['price_final'],
            quantity_initial=serializer.validated_data['quantity_initial'],
            quantity_final=serializer.validated_data['quantity_final']
        )

        return Response(result)
