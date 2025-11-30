"""
Midpoint elasticity calculator using the arc elasticity formula.

Reference: Mankiw, N. G. (2020). Principles of Economics (6th ed.), Chapter 5

IMPORTANT NOTES ON P2P MARKET DATA:
- total_volume represents STOCK/OFFER LEVEL (available ads), NOT traded volume
- Volume can fluctuate wildly based on advertiser activity, not price
- Price in P2P is relatively stable (rarely moves more than 2-3% per week)
- This can produce misleading elasticity coefficients

THRESHOLDS:
- Minimum price variation: 1% (smaller variations give unreliable results)
- Minimum quantity variation: 1% (prevents edge cases)
- Maximum reasonable elasticity: |10| (larger values flagged as unreliable)
- Maximum reportable elasticity: |20| (larger values cause FAILED status)
"""
from decimal import Decimal
from typing import Dict, List
import logging

logger = logging.getLogger(__name__)

# Minimum percentage price change required for reliable elasticity
# P2P markets are relatively stable; 1% minimum prevents division explosion
MIN_PRICE_VARIATION_PCT = Decimal('1.0')  # 1%

# Minimum quantity variation (prevents near-zero numerator edge cases)
MIN_QUANTITY_VARIATION_PCT = Decimal('1.0')  # 1%

# Maximum reasonable elasticity coefficient (larger = unreliable)
# Standard economics: |Ed| typically 0.1 to 5
# P2P markets with noise: |Ed| up to 10 is interpretable
# Above 10: likely noise, not real elasticity
MAX_REASONABLE_ELASTICITY = Decimal('10')

# Absolute maximum - beyond this, refuse to report a number
# If |Ed| > 20, the calculation is meaningless
MAX_REPORTABLE_ELASTICITY = Decimal('20')


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
        pct_change_quantity_abs = abs(quantity_change / quantity_midpoint) * Decimal('100') if quantity_midpoint > 0 else Decimal('0')
        
        # Log detailed input values for debugging
        logger.info(
            f"Elasticity calculation inputs: "
            f"P_initial={price_initial:.4f}, P_final={price_final:.4f}, "
            f"ΔP={price_change:.4f}, ΔP%={pct_change_price:.2f}%, "
            f"Q_initial={quantity_initial:.2f}, Q_final={quantity_final:.2f}, "
            f"ΔQ={quantity_change:.2f}, ΔQ%={pct_change_quantity_abs:.2f}%"
        )

        # VALIDATION 1: Check for zero/near-zero price change
        if price_change == 0:
            raise ValueError(
                "Price unchanged during period - elasticity is undefined. "
                "Select a longer time window or different dates."
            )

        # VALIDATION 2: Check minimum price variation
        if pct_change_price < MIN_PRICE_VARIATION_PCT:
            raise ValueError(
                f"Price variation too small: {pct_change_price:.2f}% "
                f"(minimum: {MIN_PRICE_VARIATION_PCT}%). "
                f"USDT/BOB price is very stable ({price_initial:.4f} to {price_final:.4f}). "
                f"Elasticity cannot be calculated meaningfully with such small price movement. "
                f"Try a longer time window or different dates."
            )

        # VALIDATION 3: Check minimum quantity variation
        # Exception: ΔQ = 0 exactly is valid (perfectly inelastic demand, Ed = 0)
        # Only reject near-zero but non-zero ΔQ which causes unstable ratios
        if quantity_change != 0 and pct_change_quantity_abs < MIN_QUANTITY_VARIATION_PCT and quantity_midpoint > 0:
            raise ValueError(
                f"Volume variation too small: {pct_change_quantity_abs:.2f}% "
                f"(minimum: {MIN_QUANTITY_VARIATION_PCT}%). "
                f"Volume change is near-zero but not zero - result would be unstable."
            )

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

        # VALIDATION 4: Refuse to report absurdly high elasticities
        if abs_elasticity > MAX_REPORTABLE_ELASTICITY:
            raise ValueError(
                f"Elasticity coefficient |{abs_elasticity:.2f}| is unrealistically high. "
                f"This typically means: (1) price barely changed ({pct_change_price:.2f}%) while "
                f"volume fluctuated significantly ({pct_change_quantity_abs:.2f}%), or "
                f"(2) volume changes are driven by supply/liquidity factors, not demand response to price. "
                f"The calculation cannot produce a meaningful result for this period."
            )

        # RELIABILITY CHECK: Flag moderately extreme values
        is_reliable = abs_elasticity <= MAX_REASONABLE_ELASTICITY
        reliability_note = None
        
        if not is_reliable:
            reliability_note = (
                f"Elasticity |{abs_elasticity:.2f}| exceeds typical range (|{MAX_REASONABLE_ELASTICITY}|). "
                f"Price variation: {pct_change_price:.2f}%, Volume variation: {pct_change_quantity_abs:.2f}%. "
                f"In P2P markets, high 'elasticity' often reflects liquidity shocks or advertiser activity, "
                f"not true demand response to price. Interpret with caution."
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
