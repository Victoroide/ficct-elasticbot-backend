"""
Comprehensive tests for simulator services.

Tests ScenarioEngine functionality.
"""
import pytest
from decimal import Decimal

from apps.simulator.services.scenario_engine import ScenarioEngine


class TestScenarioEngine:
    """Tests for ScenarioEngine class."""

    def setup_method(self):
        """Set up test fixtures."""
        self.engine = ScenarioEngine()

    def test_simulate_inelastic_scenario(self):
        """Test simulation of inelastic demand scenario."""
        result = self.engine.simulate_scenario(
            price_initial=Decimal('7.00'),
            price_final=Decimal('7.20'),
            quantity_initial=Decimal('125000'),
            quantity_final=Decimal('122000')
        )

        assert result['classification'] == 'inelastic'
        assert abs(result['elasticity']) < 1

    def test_simulate_elastic_scenario(self):
        """Test simulation of elastic demand scenario."""
        result = self.engine.simulate_scenario(
            price_initial=Decimal('7.00'),
            price_final=Decimal('7.10'),
            quantity_initial=Decimal('100000'),
            quantity_final=Decimal('85000')
        )

        assert result['classification'] == 'elastic'
        assert abs(result['elasticity']) > 1

    def test_simulate_unitary_scenario(self):
        """Test simulation of unitary elasticity scenario."""
        result = self.engine.simulate_scenario(
            price_initial=Decimal('10.00'),
            price_final=Decimal('12.00'),
            quantity_initial=Decimal('100'),
            quantity_final=Decimal('81.82')
        )

        assert abs(abs(result['elasticity']) - 1) < 0.1

    def test_scenario_returns_all_fields(self):
        """Test that result contains all expected fields."""
        result = self.engine.simulate_scenario(
            price_initial=Decimal('7.00'),
            price_final=Decimal('7.20'),
            quantity_initial=Decimal('125000'),
            quantity_final=Decimal('122000')
        )

        assert 'elasticity' in result
        assert 'abs_value' in result
        assert 'classification' in result
        assert 'percentage_change_quantity' in result
        assert 'percentage_change_price' in result

    def test_scenario_negative_elasticity(self):
        """Test that elasticity is negative for normal goods."""
        result = self.engine.simulate_scenario(
            price_initial=Decimal('7.00'),
            price_final=Decimal('7.50'),
            quantity_initial=Decimal('100000'),
            quantity_final=Decimal('95000')
        )

        assert result['elasticity'] < 0

    def test_scenario_price_increase_quantity_decrease(self):
        """Test normal demand behavior: price up, quantity down."""
        result = self.engine.simulate_scenario(
            price_initial=Decimal('7.00'),
            price_final=Decimal('7.50'),
            quantity_initial=Decimal('100000'),
            quantity_final=Decimal('90000')
        )

        assert result['percentage_change_price'] > 0
        assert result['percentage_change_quantity'] < 0

    def test_scenario_price_decrease_quantity_increase(self):
        """Test inverse relationship: price down, quantity up."""
        result = self.engine.simulate_scenario(
            price_initial=Decimal('7.50'),
            price_final=Decimal('7.00'),
            quantity_initial=Decimal('90000'),
            quantity_final=Decimal('100000')
        )

        assert result['percentage_change_price'] < 0
        assert result['percentage_change_quantity'] > 0

    def test_scenario_zero_price_change_raises_error(self):
        """Test that zero price change raises error."""
        with pytest.raises(ZeroDivisionError):
            self.engine.simulate_scenario(
                price_initial=Decimal('7.00'),
                price_final=Decimal('7.00'),
                quantity_initial=Decimal('100000'),
                quantity_final=Decimal('95000')
            )

    def test_scenario_negative_price_raises_error(self):
        """Test that negative price raises error."""
        with pytest.raises(ValueError):
            self.engine.simulate_scenario(
                price_initial=Decimal('-7.00'),
                price_final=Decimal('7.50'),
                quantity_initial=Decimal('100000'),
                quantity_final=Decimal('95000')
            )

    def test_scenario_negative_quantity_raises_error(self):
        """Test that negative quantity raises error."""
        with pytest.raises(ValueError):
            self.engine.simulate_scenario(
                price_initial=Decimal('7.00'),
                price_final=Decimal('7.50'),
                quantity_initial=Decimal('-100000'),
                quantity_final=Decimal('95000')
            )

    def test_scenario_small_price_change(self):
        """Test scenario with very small price change."""
        result = self.engine.simulate_scenario(
            price_initial=Decimal('7.00'),
            price_final=Decimal('7.01'),
            quantity_initial=Decimal('100000'),
            quantity_final=Decimal('99900')
        )

        assert 'elasticity' in result
        assert result['elasticity'] != 0

    def test_scenario_large_price_change(self):
        """Test scenario with large price change."""
        result = self.engine.simulate_scenario(
            price_initial=Decimal('7.00'),
            price_final=Decimal('10.00'),
            quantity_initial=Decimal('100000'),
            quantity_final=Decimal('60000')
        )

        assert 'elasticity' in result
        assert result['classification'] in ['elastic', 'inelastic', 'unitary']

    def test_scenario_decimal_precision(self):
        """Test that calculations maintain decimal precision."""
        result = self.engine.simulate_scenario(
            price_initial=Decimal('7.0512'),
            price_final=Decimal('7.2034'),
            quantity_initial=Decimal('125432.50'),
            quantity_final=Decimal('121098.25')
        )

        assert isinstance(result['elasticity'], float)
        assert result['elasticity'] != 0

    def test_scenario_usdt_bob_realistic(self):
        """Test realistic USDT/BOB market scenario."""
        result = self.engine.simulate_scenario(
            price_initial=Decimal('7.05'),
            price_final=Decimal('7.15'),
            quantity_initial=Decimal('142500'),
            quantity_final=Decimal('141000')
        )

        assert result['classification'] == 'inelastic'
        assert -1 < result['elasticity'] < 0
