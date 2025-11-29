"""
Midpoint elasticity calculator using the arc elasticity formula.

Reference: Mankiw, N. G. (2020). Principles of Economics (6th ed.), Chapter 5

IMPORTANT NOTES ON P2P MARKET DATA:
- total_volume represents STOCK/OFFER LEVEL (available ads), NOT traded volume
- Volume can fluctuate wildly based on advertiser activity, not price
- Price in P2P is relatively stable (rarely moves more than 2-3% per week)
- This can produce misleading elasticity coefficients

THRESHOLDS:
- Minimum price variation: 0.5% (smaller variations give unreliable results)
- Maximum reasonable elasticity: |50| (larger values flagged as unreliable)
"""
from decimal import Decimal
from typing import Dict, List
import logging

logger = logging.getLogger(__name__)

# Minimum percentage price change required for reliable elasticity
MIN_PRICE_VARIATION_PCT = Decimal('0.5')  # 0.5%

# Maximum reasonable elasticity coefficient (larger = unreliable)
# For typical markets: |Ed| < 5 is normal
# For P2P markets with volatile volume: |Ed| < 10 is acceptable
# Anything > 10 likely indicates volume changes driven by non-price factors
MAX_REASONABLE_ELASTICITY = Decimal('10')


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
    
    Reliability checks:
        - Price must vary by at least 0.5% for meaningful results
        - Coefficients > |50| are flagged as unreliable
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
                - is_reliable: Boolean indicating if result is trustworthy
                - reliability_note: Explanation if unreliable

        Raises:
            ValueError: If prices are negative/zero or insufficient variation
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

        # Calculate percentage changes
        pct_change_price = abs(price_change / price_midpoint) * Decimal('100')
        
        # Log detailed input values for debugging
        logger.info(
            f"Elasticity calculation inputs: "
            f"P_initial={price_initial:.4f}, P_final={price_final:.4f}, "
            f"ΔP={price_change:.4f}, ΔP%={pct_change_price:.2f}%, "
            f"Q_initial={quantity_initial:.2f}, Q_final={quantity_final:.2f}, "
            f"ΔQ={quantity_change:.2f}"
        )

        # VALIDATION: Check minimum price variation
        if pct_change_price < MIN_PRICE_VARIATION_PCT:
            raise ValueError(
                f"Insufficient price variation: {pct_change_price:.2f}% "
                f"(minimum required: {MIN_PRICE_VARIATION_PCT}%). "
                f"Price range {price_initial:.4f} to {price_final:.4f} is too narrow "
                f"for meaningful elasticity calculation."
            )

        # Check for zero price change (shouldn't happen after above check, but safety)
        if price_change == 0:
            raise ValueError("Price change cannot be zero - elasticity undefined")

        # Calculate percentage changes using midpoint method
        pct_change_quantity = (quantity_change / quantity_midpoint) * Decimal('100')
        pct_change_price_signed = (price_change / price_midpoint) * Decimal('100')

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

        # RELIABILITY CHECK: Flag extreme values
        is_reliable = abs_elasticity <= MAX_REASONABLE_ELASTICITY
        reliability_note = None
        
        if not is_reliable:
            reliability_note = (
                f"Elasticity coefficient |{abs_elasticity:.2f}| exceeds reasonable range (|{MAX_REASONABLE_ELASTICITY}|). "
                f"This may indicate: (1) price variation too small ({pct_change_price:.2f}%), "
                f"(2) volume changes driven by factors other than price, "
                f"(3) insufficient data quality. Interpret with caution."
            )
            logger.warning(f"Unreliable elasticity: {reliability_note}")

        logger.info(
            f"Midpoint elasticity calculated: {elasticity:.4f} ({classification}), "
            f"reliable={is_reliable}",
            extra={
                'elasticity': float(elasticity),
                'classification': classification,
                'is_reliable': is_reliable,
                'pct_change_price': float(pct_change_price),
                'pct_change_quantity': float(pct_change_quantity),
            }
        )

        return {
            'elasticity': float(elasticity),
            'abs_value': float(abs_elasticity),
            'classification': classification,
            'percentage_change_quantity': float(pct_change_quantity),
            'percentage_change_price': float(pct_change_price_signed),
            'quantity_change': float(quantity_change),
            'price_change': float(price_change),
            'is_reliable': is_reliable,
            'reliability_note': reliability_note,
            'metadata': {
                'price_initial': float(price_initial),
                'price_final': float(price_final),
                'quantity_initial': float(quantity_initial),
                'quantity_final': float(quantity_final),
                'price_midpoint': float(price_midpoint),
                'quantity_midpoint': float(quantity_midpoint),
            }
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
