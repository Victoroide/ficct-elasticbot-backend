"""
Tests for price change service.

Tests calculation of price changes and market premium.
"""
from decimal import Decimal
from datetime import date, datetime, timedelta
from django.test import TestCase
from django.utils import timezone

from apps.market_data.models import MarketSnapshot, MacroeconomicIndicator
from apps.market_data.services.price_change_service import PriceChangeService


class TestPriceChangeService(TestCase):
    """Test price change calculations and market premium."""

    def setUp(self):
        """Set up test data."""
        self.service = PriceChangeService()
        self.now = timezone.now()
        
        # Create test snapshots
        self.snapshot_1 = MarketSnapshot.objects.create(
            timestamp=self.now - timedelta(hours=2),
            average_sell_price=Decimal('10.00'),
            average_buy_price=Decimal('10.05'),
            total_volume=Decimal('100000'),
            spread_percentage=Decimal('0.50'),
            data_quality_score=0.8
        )
        
        self.snapshot_2 = MarketSnapshot.objects.create(
            timestamp=self.now - timedelta(hours=1),
            average_sell_price=Decimal('10.10'),
            average_buy_price=Decimal('10.15'),
            total_volume=Decimal('120000'),
            spread_percentage=Decimal('0.49'),
            data_quality_score=0.8
        )
        
        self.snapshot_3 = MarketSnapshot.objects.create(
            timestamp=self.now,
            average_sell_price=Decimal('10.05'),
            average_buy_price=Decimal('10.10'),
            total_volume=Decimal('110000'),
            spread_percentage=Decimal('0.50'),
            data_quality_score=0.8
        )
        
        # Create BCB indicator
        self.bcb_indicator = MacroeconomicIndicator.objects.create(
            date=date.today(),
            official_exchange_rate=Decimal('6.96'),
            source='BCB'
        )

    def test_price_increase_calculation(self):
        """Test price increase from previous snapshot."""
        result = self.service.calculate_price_change(self.snapshot_2)
        
        self.assertEqual(result['percentage_change'], Decimal('1.00'))  # (10.10-10.00)/10.00*100
        self.assertEqual(result['direction'], 'up')
        self.assertEqual(result['previous_price'], Decimal('10.00'))
        self.assertEqual(result['time_gap_minutes'], 60)
        self.assertFalse(result['is_first_snapshot'])
        self.assertFalse(result['time_gap_warning'])

    def test_price_decrease_calculation(self):
        """Test price decrease from previous snapshot."""
        result = self.service.calculate_price_change(self.snapshot_3)
        
        # Should compare with snapshot_2 (most recent before)
        expected_change = ((Decimal('10.05') - Decimal('10.10')) / Decimal('10.10')) * Decimal('100')
        self.assertAlmostEqual(result['percentage_change'], expected_change, places=2)
        self.assertEqual(result['direction'], 'down')
        self.assertEqual(result['previous_price'], Decimal('10.10'))
        self.assertEqual(result['time_gap_minutes'], 60)
        self.assertFalse(result['is_first_snapshot'])
        self.assertFalse(result['time_gap_warning'])

    def test_no_price_change(self):
        """Test identical prices (neutral direction)."""
        # Create snapshot with same price as previous
        same_price_snapshot = MarketSnapshot.objects.create(
            timestamp=self.now + timedelta(hours=1),
            average_sell_price=Decimal('10.05'),  # Same as snapshot_3
            average_buy_price=Decimal('10.10'),
            total_volume=Decimal('110000'),
            spread_percentage=Decimal('0.50'),
            data_quality_score=0.8
        )
        
        result = self.service.calculate_price_change(same_price_snapshot)
        self.assertEqual(result['percentage_change'], Decimal('0'))
        self.assertEqual(result['direction'], 'neutral')

    def test_first_snapshot_no_previous(self):
        """Test first snapshot (no previous data)."""
        # Delete other snapshots to simulate first data point
        MarketSnapshot.objects.exclude(id=self.snapshot_1.id).delete()
        
        result = self.service.calculate_price_change(self.snapshot_1)
        
        self.assertIsNone(result['percentage_change'])
        self.assertEqual(result['direction'], 'neutral')
        self.assertIsNone(result['previous_price'])
        self.assertTrue(result['is_first_snapshot'])
        self.assertIsNone(result['time_gap_minutes'])
        self.assertFalse(result['time_gap_warning'])

    def test_time_gap_warning(self):
        """Test time gap warning for large intervals."""
        # Clear existing snapshots to control test data
        MarketSnapshot.objects.all().delete()
        
        # Create snapshot with large time gap
        old_snapshot = MarketSnapshot.objects.create(
            timestamp=self.now - timedelta(hours=3),
            average_sell_price=Decimal('10.00'),
            average_buy_price=Decimal('10.05'),
            total_volume=Decimal('100000'),
            spread_percentage=Decimal('0.50'),
            data_quality_score=0.8
        )
        
        recent_snapshot = MarketSnapshot.objects.create(
            timestamp=self.now,
            average_sell_price=Decimal('10.10'),
            average_buy_price=Decimal('10.15'),
            total_volume=Decimal('120000'),
            spread_percentage=Decimal('0.49'),
            data_quality_score=0.8
        )
        
        result = self.service.calculate_price_change(recent_snapshot)
        self.assertEqual(result['time_gap_minutes'], 180)  # 3 hours
        self.assertTrue(result['time_gap_warning'])

    def test_market_premium_calculation(self):
        """Test market premium calculation."""
        result = self.service.calculate_market_premium(self.snapshot_3)
        
        # Premium = (10.05 - 6.96) / 6.96 * 100 = 44.40%
        expected_premium = ((Decimal('10.05') - Decimal('6.96')) / Decimal('6.96')) * Decimal('100')
        self.assertAlmostEqual(result['premium_percentage'], expected_premium, places=2)
        self.assertEqual(result['bcb_rate'], Decimal('6.96'))
        self.assertEqual(result['bcb_rate_date'], self.bcb_indicator.date)
        self.assertFalse(result['bcb_rate_stale'])

    def test_market_premium_no_bcb_data(self):
        """Test market premium when no BCB data available."""
        # Delete BCB indicator
        MacroeconomicIndicator.objects.all().delete()
        
        result = self.service.calculate_market_premium(self.snapshot_3)
        
        self.assertIsNone(result['premium_percentage'])
        self.assertIsNone(result['bcb_rate'])
        self.assertIsNone(result['bcb_rate_date'])
        self.assertFalse(result['bcb_rate_stale'])

    def test_market_premium_stale_bcb_rate(self):
        """Test market premium with stale BCB rate."""
        # Update BCB indicator to be old
        old_time = timezone.now() - timedelta(hours=50)
        MacroeconomicIndicator.objects.filter(id=self.bcb_indicator.id).update(
            updated_at=old_time
        )
        
        result = self.service.calculate_market_premium(self.snapshot_3)
        
        self.assertIsNotNone(result['premium_percentage'])
        self.assertTrue(result['bcb_rate_stale'])

    def test_enriched_snapshot_data(self):
        """Test complete enriched snapshot data."""
        result = self.service.enrich_snapshot_data(self.snapshot_3)
        
        # Check original fields
        self.assertEqual(result['id'], str(self.snapshot_3.id))
        self.assertEqual(result['average_sell_price'], 10.05)
        self.assertEqual(result['average_buy_price'], 10.10)
        self.assertEqual(result['total_volume'], 110000.0)
        self.assertEqual(result['data_quality_score'], 0.8)
        
        # Check price change fields
        self.assertIsNotNone(result['price_change_percentage'])
        self.assertIn(result['price_change_direction'], ['up', 'down', 'neutral'])
        self.assertIsNotNone(result['previous_price'])
        self.assertFalse(result['is_first_snapshot'])
        self.assertEqual(result['time_gap_minutes'], 60)
        self.assertFalse(result['time_gap_warning'])
        
        # Check market premium fields
        self.assertIsNotNone(result['market_premium_percentage'])
        self.assertEqual(result['bcb_official_rate'], 6.96)
        self.assertIsNotNone(result['bcb_rate_date'])
        self.assertFalse(result['bcb_rate_stale'])

    def test_missing_price_data(self):
        """Test handling of zero price in previous snapshot."""
        # Clear existing snapshots to control the test data
        MarketSnapshot.objects.all().delete()
        
        # Create a zero price snapshot first
        zero_price_snapshot = MarketSnapshot.objects.create(
            timestamp=self.now - timedelta(hours=1),
            average_sell_price=Decimal('0'),  # Zero price edge case
            average_buy_price=Decimal('0.05'),
            total_volume=Decimal('100000'),
            spread_percentage=Decimal('0.50'),
            data_quality_score=0.8
        )
        
        # Create current snapshot
        current_snapshot = MarketSnapshot.objects.create(
            timestamp=self.now,
            average_sell_price=Decimal('10.00'),
            average_buy_price=Decimal('10.05'),
            total_volume=Decimal('100000'),
            spread_percentage=Decimal('0.50'),
            data_quality_score=0.8
        )
        
        result = self.service.calculate_price_change(current_snapshot)
        
        # Should handle zero previous price gracefully
        self.assertIsNone(result['percentage_change'])
        self.assertEqual(result['direction'], 'neutral')
        self.assertEqual(result['previous_price'], Decimal('0'))
        self.assertFalse(result['is_first_snapshot'])

    
    def test_small_price_changes_direction(self):
        """Test direction determination for small price changes."""
        # Clear existing snapshots to control test data
        MarketSnapshot.objects.all().delete()
        
        # Create base snapshot
        base_snapshot = MarketSnapshot.objects.create(
            timestamp=self.now,
            average_sell_price=Decimal('10.00'),
            average_buy_price=Decimal('10.05'),
            total_volume=Decimal('110000'),
            spread_percentage=Decimal('0.50'),
            data_quality_score=0.8
        )
        
        # Test very small increase (should be neutral)
        small_increase = MarketSnapshot.objects.create(
            timestamp=self.now + timedelta(hours=1),
            average_sell_price=Decimal('10.0001'),  # 0.001% increase
            average_buy_price=Decimal('10.0501'),
            total_volume=Decimal('110000'),
            spread_percentage=Decimal('0.50'),
            data_quality_score=0.8
        )
        
        result = self.service.calculate_price_change(small_increase)
        self.assertEqual(result['direction'], 'neutral')
        
        # Test small but significant increase (should be up)
        small_significant = MarketSnapshot.objects.create(
            timestamp=self.now + timedelta(hours=2),
            average_sell_price=Decimal('10.002'),  # 0.02% increase
            average_buy_price=Decimal('10.052'),
            total_volume=Decimal('110000'),
            spread_percentage=Decimal('0.50'),
            data_quality_score=0.8
        )
        
        result = self.service.calculate_price_change(small_significant)
        self.assertEqual(result['direction'], 'up')
