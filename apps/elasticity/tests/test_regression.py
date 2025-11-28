"""
Unit tests for regression elasticity calculator.

Validates log-log regression implementation for constant elasticity estimation.
"""
import pytest
from decimal import Decimal
from apps.elasticity.services.regression_calculator import RegressionElasticityCalculator


class TestRegressionElasticityCalculator:
    """
    Test suite for log-log regression elasticity calculation.

    Tests cover:
    - Known datasets with expected elasticities
    - Statistical significance validation
    - Assumption checking (linearity, normality)
    - Edge cases and error handling
    """

    def setup_method(self):
        """Initialize calculator for each test."""
        self.calculator = RegressionElasticityCalculator()

    def test_perfectly_inelastic_data(self):
        """
        Scenario: Quantity constant despite price changes.
        Expected: Ed ≈ 0 (perfectly inelastic)
        """
        prices = [Decimal(str(p)) for p in [7.00, 7.05, 7.10, 7.15, 7.20,
                                            7.25, 7.30, 7.35, 7.40, 7.45]]
        quantities = [Decimal('10000')] * 10  # No change

        result = self.calculator.calculate(prices, quantities)

        assert abs(result['elasticity']) < 0.1  # Near zero
        assert result['classification'] == 'inelastic'

    def test_elastic_scenario_btc(self):
        """
        Scenario: Bitcoin-like elastic behavior.
        Price increases → Quantity decreases significantly
        Expected: |Ed| > 1 (elastic)
        """
        # Simulated BTC data: Strong negative relationship
        prices = [Decimal(str(p)) for p in [
            100, 105, 110, 115, 120, 125, 130, 135, 140, 145
        ]]
        quantities = [Decimal(str(q)) for q in [
            10000, 9200, 8500, 7900, 7400, 6900, 6500, 6100, 5800, 5500
        ]]

        result = self.calculator.calculate(prices, quantities)

        assert result['abs_value'] > 1.0
        assert result['classification'] == 'elastic'
        assert result['elasticity'] < 0  # Law of demand

    def test_unitary_elasticity(self):
        """
        Scenario: Proportional price-quantity relationship.
        Expected: Ed ≈ -1.0 (unitary elastic)
        """
        # Engineered data for unitary elasticity
        prices = [Decimal(str(p)) for p in [
            7.00, 7.10, 7.20, 7.30, 7.40, 7.50, 7.60, 7.70, 7.80, 7.90
        ]]
        # Quantity inversely proportional to price
        quantities = [Decimal(str(10000 / p)) for p in [
            7.00, 7.10, 7.20, 7.30, 7.40, 7.50, 7.60, 7.70, 7.80, 7.90
        ]]

        result = self.calculator.calculate(prices, quantities)

        assert 0.9 <= result['abs_value'] <= 1.1
        assert result['classification'] == 'unitary'

    def test_real_world_usdt_inelastic(self):
        """
        Real-world USDT/BOB behavior simulation.

        USDT acts as value refuge in Bolivia, showing inelastic demand
        despite price fluctuations.
        """
        # 2-week hourly data simulation
        import random
        random.seed(42)  # Reproducible

        base_price = 7.00
        base_volume = 120000

        prices = []
        volumes = []

        for i in range(336):  # 14 days * 24 hours
            # Price random walk with small changes
            price_change = random.gauss(0, 0.02)
            price = base_price + price_change
            prices.append(Decimal(str(price)))

            # Volume weakly responds (inelastic)
            volume_change = -price_change * 8000  # Weak response
            volume = base_volume + volume_change + random.gauss(0, 3000)
            volumes.append(Decimal(str(max(volume, 50000))))

        result = self.calculator.calculate(prices, volumes)

        assert result['abs_value'] < 1.0
        assert result['classification'] == 'inelastic'
        assert result['n_observations'] == 336

    def test_insufficient_data_raises(self):
        """Need at least 10 data points for reliable regression."""
        prices = [Decimal(str(p)) for p in [7.00, 7.10, 7.20]]
        quantities = [Decimal(str(q)) for q in [10000, 9500, 9000]]

        with pytest.raises(ValueError, match="at least 10 data points"):
            self.calculator.calculate(prices, quantities)

    def test_zero_prices_raise_error(self):
        """Cannot take log of zero or negative prices."""
        prices = [Decimal(str(p)) for p in [7.00, 0, 7.20, 7.30, 7.40] + [7.50] * 5]
        quantities = [Decimal('10000')] * 10

        with pytest.raises(ValueError, match="must be positive"):
            self.calculator.calculate(prices, quantities)

    def test_statistical_significance(self):
        """
        Test with strong relationship → should be statistically significant.
        """
        # Strong negative relationship
        prices = [Decimal(str(p)) for p in range(100, 120)]
        quantities = [Decimal(str(15000 - 50 * p)) for p in range(100, 120)]

        result = self.calculator.calculate(prices, quantities)

        assert result['is_significant']
        assert result['p_value'] < 0.05
        assert result['r_squared'] > 0.8  # Good fit

    def test_confidence_interval_excludes_zero(self):
        """
        For significant result, CI should not include zero.
        """
        prices = [Decimal(str(p)) for p in [7.0, 7.1, 7.2, 7.3, 7.4,
                                            7.5, 7.6, 7.7, 7.8, 7.9]]
        quantities = [Decimal(str(q)) for q in [12000, 11500, 11000, 10500, 10000,
                                                9500, 9000, 8500, 8000, 7500]]

        result = self.calculator.calculate(prices, quantities)

        ci = result['confidence_interval_95']

        # For negative elasticity, both bounds should be negative
        assert ci[0] < 0
        assert ci[1] < 0
        assert ci[0] < ci[1]  # Lower < Upper

    def test_time_series_format(self):
        """Test convenience method for time series input."""
        time_series = [
            (Decimal('7.00'), Decimal('12000')),
            (Decimal('7.05'), Decimal('11800')),
            (Decimal('7.10'), Decimal('11600')),
            (Decimal('7.15'), Decimal('11400')),
            (Decimal('7.20'), Decimal('11200')),
            (Decimal('7.25'), Decimal('11000')),
            (Decimal('7.30'), Decimal('10800')),
            (Decimal('7.35'), Decimal('10600')),
            (Decimal('7.40'), Decimal('10400')),
            (Decimal('7.45'), Decimal('10200')),
        ]

        result = self.calculator.calculate_with_time_series(time_series)

        assert 'elasticity' in result
        assert result['n_observations'] == 10

    def test_assumption_validation(self):
        """
        Validate regression assumptions.
        """
        # Good linear relationship in log-log space
        prices = [Decimal(str(p)) for p in [7.0, 7.2, 7.4, 7.6, 7.8,
                                            8.0, 8.2, 8.4, 8.6, 8.8]]
        quantities = [Decimal(str(12000 / p)) for p in [7.0, 7.2, 7.4, 7.6, 7.8,
                                                        8.0, 8.2, 8.4, 8.6, 8.8]]

        diagnostics = self.calculator.validate_assumptions(prices, quantities)

        assert diagnostics['linearity_adequate']
        assert abs(diagnostics['linearity_correlation']) > 0.9
        assert abs(diagnostics['residuals_mean']) < 0.1

    def test_insufficient_variance_raises(self):
        """Prices must have sufficient variation for regression."""
        prices = [Decimal('7.00')] * 10  # No variance
        quantities = [Decimal(str(q)) for q in range(10000, 11000, 100)]

        with pytest.raises(ValueError, match="Insufficient price variation"):
            self.calculator.calculate(prices, quantities)
