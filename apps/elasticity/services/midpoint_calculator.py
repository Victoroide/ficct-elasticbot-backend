"""
Midpoint elasticity calculator using the arc elasticity formula.

Reference: Mankiw, N. G. (2020). Principles of Economics (6th ed.), Chapter 5
"""
from decimal import Decimal
from typing import Dict, List
import logging

logger = logging.getLogger(__name__)


class MidpointElasticityCalculator:
    """
    Calculates price elasticity of demand using the midpoint (arc) formula.

    Formula:
        Ed = [(Q₂ - Q₁) / ((Q₂ + Q₁)/2)] / [(P₂ - P₁) / ((P₂ + P₁)/2)]

    This method provides elasticity between two points and is preferred when
    measuring elasticity over a range rather than at a single point.

    Classification:
        |Ed| > 1: Elastic (quantity changes proportionally more than price)
        |Ed| < 1: Inelastic (quantity changes proportionally less than price)
        |Ed| ≈ 1: Unitary elastic (proportional changes)
    """

    def calculate(
        self,
        quantity_initial: Decimal,
        quantity_final: Decimal,
        price_initial: Decimal,
        price_final: Decimal
    ) -> Dict:
        """
        Calculate elasticity between two price-quantity points.

        Args:
            quantity_initial: Initial quantity demanded (Q₁)
            quantity_final: Final quantity demanded (Q₂)
            price_initial: Initial price (P₁)
            price_final: Final price (P₂)

        Returns:
            Dictionary with:
                - elasticity: Elasticity coefficient
                - abs_value: Absolute value of elasticity
                - classification: 'elastic', 'inelastic', or 'unitary'
                - percentage_change_quantity: % change in quantity
                - percentage_change_price: % change in price

        Raises:
            ValueError: If prices are negative or zero
            ZeroDivisionError: If price change is zero (undefined elasticity)
        """
        # Input validation
        if price_initial <= 0 or price_final <= 0:
            raise ValueError("Prices must be positive")

        if quantity_initial < 0 or quantity_final < 0:
            raise ValueError("Quantities must be non-negative")

        # Calculate midpoints
        quantity_midpoint = (quantity_initial + quantity_final) / Decimal('2')
        price_midpoint = (price_initial + price_final) / Decimal('2')

        # Calculate changes
        quantity_change = quantity_final - quantity_initial
        price_change = price_final - price_initial

        # Check for zero price change
        if price_change == 0:
            raise ZeroDivisionError("Price change cannot be zero - elasticity undefined")

        # Calculate percentage changes using midpoint method
        pct_change_quantity = (quantity_change / quantity_midpoint) * Decimal('100')
        pct_change_price = (price_change / price_midpoint) * Decimal('100')

        # Calculate elasticity coefficient
        elasticity = (quantity_change / quantity_midpoint) / (price_change / price_midpoint)

        # Get absolute value for classification
        abs_elasticity = abs(elasticity)

        # Classify elasticity
        if abs_elasticity > Decimal('1.05'):
            classification = 'elastic'
        elif abs_elasticity < Decimal('0.95'):
            classification = 'inelastic'
        else:
            classification = 'unitary'

        logger.info(
            f"Midpoint elasticity calculated: {elasticity:.4f}",
            extra={
                'elasticity': float(elasticity),
                'classification': classification
            }
        )

        return {
            'elasticity': float(elasticity),
            'abs_value': float(abs_elasticity),
            'classification': classification,
            'percentage_change_quantity': float(pct_change_quantity),
            'percentage_change_price': float(pct_change_price),
            'quantity_change': float(quantity_change),
            'price_change': float(price_change),
        }

    def calculate_from_series(
        self,
        prices: List[Decimal],
        quantities: List[Decimal]
    ) -> Dict:
        """
        Calculate elasticity from time series data using first and last points.

        Args:
            prices: List of price observations
            quantities: List of quantity observations

        Returns:
            Dictionary with elasticity results plus:
                - data_points_used: Number of observations
                - initial_point: (P₁, Q₁)
                - final_point: (P₂, Q₂)
        """
        if len(prices) != len(quantities):
            raise ValueError("Prices and quantities must have same length")

        if len(prices) < 2:
            raise ValueError("Need at least 2 data points for elasticity calculation")

        # Use first and last points for midpoint calculation
        result = self.calculate(
            quantity_initial=quantities[0],
            quantity_final=quantities[-1],
            price_initial=prices[0],
            price_final=prices[-1]
        )

        # Add metadata
        result['data_points_used'] = len(prices)
        result['initial_point'] = {'price': float(prices[0]), 'quantity': float(quantities[0])}
        result['final_point'] = {'price': float(prices[-1]), 'quantity': float(quantities[-1])}

        return result
