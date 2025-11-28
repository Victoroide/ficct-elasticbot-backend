"""
Comprehensive tests for market_data models.

Tests MarketSnapshot, DataCollectionLog, and MacroeconomicIndicator models.
"""
import pytest
from decimal import Decimal
from django.utils import timezone
from apps.market_data.models import MarketSnapshot
from apps.market_data.models.data_collection_log import DataCollectionLog
from apps.market_data.models.macroeconomic_indicator import MacroeconomicIndicator


@pytest.mark.django_db
class TestMarketSnapshot:
    """Tests for MarketSnapshot model."""

    def test_create_valid_snapshot(self):
        """Test creating a valid market snapshot."""
        snapshot = MarketSnapshot.objects.create(
            timestamp=timezone.now(),
            average_sell_price=Decimal('7.05'),
            average_buy_price=Decimal('6.98'),
            total_volume=Decimal('50000.00'),
            spread_percentage=Decimal('1.00'),
            num_active_traders=15,
            data_quality_score=Decimal('0.92')
        )

        assert snapshot.id is not None
        assert snapshot.average_sell_price == Decimal('7.05')
        assert snapshot.average_buy_price == Decimal('6.98')

    def test_snapshot_string_representation(self):
        """Test string representation of snapshot."""
        timestamp = timezone.now()
        snapshot = MarketSnapshot.objects.create(
            timestamp=timestamp,
            average_sell_price=Decimal('7.05'),
            average_buy_price=Decimal('6.98'),
            total_volume=Decimal('50000.00'),
            spread_percentage=Decimal('1.00'),
            num_active_traders=15,
            data_quality_score=Decimal('0.92')
        )

        str_repr = str(snapshot)
        assert '7.05' in str_repr

    def test_snapshot_ordering(self):
        """Test snapshots are ordered by timestamp descending."""
        now = timezone.now()
        old = MarketSnapshot.objects.create(
            timestamp=now - timezone.timedelta(hours=2),
            average_sell_price=Decimal('7.00'),
            average_buy_price=Decimal('6.95'),
            total_volume=Decimal('40000.00'),
            spread_percentage=Decimal('0.72'),
            num_active_traders=10,
            data_quality_score=Decimal('0.85')
        )
        new = MarketSnapshot.objects.create(
            timestamp=now,
            average_sell_price=Decimal('7.05'),
            average_buy_price=Decimal('6.98'),
            total_volume=Decimal('50000.00'),
            spread_percentage=Decimal('1.00'),
            num_active_traders=15,
            data_quality_score=Decimal('0.92')
        )

        snapshots = list(MarketSnapshot.objects.all())

        assert snapshots[0].id == new.id
        assert snapshots[1].id == old.id

    def test_snapshot_positive_volume(self):
        """Test volume must be positive."""
        snapshot = MarketSnapshot(
            timestamp=timezone.now(),
            average_sell_price=Decimal('7.05'),
            average_buy_price=Decimal('6.98'),
            total_volume=Decimal('50000.00'),
            spread_percentage=Decimal('1.00'),
            num_active_traders=15,
            data_quality_score=Decimal('0.92')
        )
        snapshot.full_clean()
        snapshot.save()

        assert snapshot.total_volume > 0

    def test_snapshot_decimal_precision(self):
        """Test decimal precision is preserved."""
        snapshot = MarketSnapshot.objects.create(
            timestamp=timezone.now(),
            average_sell_price=Decimal('7.0512'),
            average_buy_price=Decimal('6.9834'),
            total_volume=Decimal('50000.50'),
            spread_percentage=Decimal('0.97'),
            num_active_traders=15,
            data_quality_score=Decimal('0.9245')
        )

        snapshot.refresh_from_db()

        assert snapshot.average_sell_price == Decimal('7.0512')

    def test_snapshot_quality_score_range(self):
        """Test quality score is within valid range."""
        snapshot = MarketSnapshot.objects.create(
            timestamp=timezone.now(),
            average_sell_price=Decimal('7.05'),
            average_buy_price=Decimal('6.98'),
            total_volume=Decimal('50000.00'),
            spread_percentage=Decimal('1.00'),
            num_active_traders=15,
            data_quality_score=Decimal('0.92')
        )

        assert 0 <= snapshot.data_quality_score <= 1

    def test_snapshot_is_high_quality_property(self):
        """Test is_high_quality property."""
        high_quality = MarketSnapshot.objects.create(
            timestamp=timezone.now(),
            average_sell_price=Decimal('7.05'),
            average_buy_price=Decimal('6.98'),
            total_volume=Decimal('50000.00'),
            spread_percentage=Decimal('1.00'),
            num_active_traders=15,
            data_quality_score=Decimal('0.92')
        )

        low_quality = MarketSnapshot.objects.create(
            timestamp=timezone.now() - timezone.timedelta(hours=1),
            average_sell_price=Decimal('7.05'),
            average_buy_price=Decimal('6.98'),
            total_volume=Decimal('50000.00'),
            spread_percentage=Decimal('1.00'),
            num_active_traders=15,
            data_quality_score=Decimal('0.50')
        )

        assert high_quality.is_high_quality is True
        assert low_quality.is_high_quality is False

    def test_snapshot_raw_response_json(self):
        """Test raw_response stores JSON data."""
        raw_data = {
            'sell_ads_count': 20,
            'buy_ads_count': 15,
            'timestamp': '2025-11-18T20:00:00Z'
        }
        snapshot = MarketSnapshot.objects.create(
            timestamp=timezone.now(),
            average_sell_price=Decimal('7.05'),
            average_buy_price=Decimal('6.98'),
            total_volume=Decimal('50000.00'),
            spread_percentage=Decimal('1.00'),
            num_active_traders=15,
            data_quality_score=Decimal('0.92'),
            raw_response=raw_data
        )

        snapshot.refresh_from_db()

        assert snapshot.raw_response['sell_ads_count'] == 20


@pytest.mark.django_db
class TestDataCollectionLog:
    """Tests for DataCollectionLog model."""

    def test_create_success_log(self):
        """Test creating a success log entry."""
        log = DataCollectionLog.objects.create(
            source='Binance P2P',
            status='SUCCESS',
            records_created=1,
            execution_time_ms=250
        )

        assert log.id is not None
        assert log.status == 'SUCCESS'

    def test_create_failure_log(self):
        """Test creating a failure log entry."""
        log = DataCollectionLog.objects.create(
            source='Binance P2P',
            status='FAILED',
            records_created=0,
            execution_time_ms=5000,
            error_message='Connection timeout'
        )

        assert log.status == 'FAILED'
        assert log.error_message == 'Connection timeout'

    def test_log_ordering(self):
        """Test logs are ordered by created_at descending."""
        DataCollectionLog.objects.create(
            source='Binance P2P',
            status='SUCCESS',
            records_created=1,
            execution_time_ms=200
        )
        new = DataCollectionLog.objects.create(
            source='BCB',
            status='SUCCESS',
            records_created=1,
            execution_time_ms=150
        )

        logs = list(DataCollectionLog.objects.all())

        assert logs[0].id == new.id


@pytest.mark.django_db
class TestMacroeconomicIndicator:
    """Tests for MacroeconomicIndicator model."""

    def test_create_indicator(self):
        """Test creating a macroeconomic indicator."""
        indicator = MacroeconomicIndicator.objects.create(
            date=timezone.now().date(),
            official_exchange_rate=Decimal('6.96'),
            source='BCB'
        )

        assert indicator.id is not None
        assert indicator.official_exchange_rate == Decimal('6.96')

    def test_indicator_string_representation(self):
        """Test string representation of indicator."""
        today = timezone.now().date()
        indicator = MacroeconomicIndicator.objects.create(
            date=today,
            official_exchange_rate=Decimal('6.96'),
            source='BCB'
        )

        str_repr = str(indicator)

        assert 'BCB' in str_repr

    def test_indicator_decimal_precision(self):
        """Test decimal precision for indicator values."""
        indicator = MacroeconomicIndicator.objects.create(
            date=timezone.now().date() - timezone.timedelta(days=1),
            monthly_inflation_rate=Decimal('0.5234'),
            source='INE'
        )

        indicator.refresh_from_db()

        assert indicator.monthly_inflation_rate == Decimal('0.5234')
