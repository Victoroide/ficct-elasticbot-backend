"""
Scenario simulation engine.
"""
from decimal import Decimal
from typing import Dict
from apps.elasticity.services import MidpointElasticityCalculator


class ScenarioEngine:
    """Calculate elasticity for hypothetical scenarios."""

    def __init__(self):
        self.calculator = MidpointElasticityCalculator()

    def simulate_scenario(
        self,
        price_initial: Decimal,
        price_final: Decimal,
        quantity_initial: Decimal,
        quantity_final: Decimal
    ) -> Dict:
        """Simulate hypothetical elasticity scenario."""
        return self.calculator.calculate(
            quantity_initial=quantity_initial,
            quantity_final=quantity_final,
            price_initial=price_initial,
            price_final=price_final
        )
