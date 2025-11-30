"""
Service for calculating price changes and market premium.

Computes percentage changes between snapshots and market premium vs BCB rate.
"""
from decimal import Decimal, InvalidOperation
from datetime import timedelta
from django.utils import timezone
import logging

from apps.market_data.models import MarketSnapshot, MacroeconomicIndicator

logger = logging.getLogger(__name__)


class PriceChangeService:
    """
    Calculates price changes and market premium for market data API.

    Provides:
    - Price change percentage vs previous snapshot
    - Market premium percentage (P2P vs BCB official rate)
    - Direction indicators for UI display
    """

    def calculate_price_change(self, current_snapshot):
        """
        Calculate price change percentage vs previous snapshot.

        Args:
            current_snapshot: MarketSnapshot instance

        Returns:
            dict: {
                'percentage_change': Decimal or None,
                'direction': str ('up' | 'down' | 'neutral'),
                'previous_price': Decimal or None,
                'time_gap_minutes': int or None,
                'is_first_snapshot': bool,
                'time_gap_warning': bool,
            }
        """
        # Get previous snapshot (exclude current, order by timestamp)
        previous = MarketSnapshot.objects.filter(
            data_quality_score__gte=0.7  # Same quality filter as main API
        ).exclude(
            id=current_snapshot.id
        ).filter(
            timestamp__lt=current_snapshot.timestamp
        ).order_by('-timestamp').first()

        # If no previous snapshot, this is the first data point
        if not previous:
            return {
                'percentage_change': None,
                'direction': 'neutral',
                'previous_price': None,
                'time_gap_minutes': None,
                'is_first_snapshot': True,
                'time_gap_warning': False,
            }

        # Use average_sell_price as the representative price
        current_price = current_snapshot.average_sell_price
        previous_price = previous.average_sell_price

        # Validate prices
        if current_price is None or previous_price is None:
            logger.warning(
                f"Missing price data for change calculation: "
                f"current={current_price}, previous={previous_price}"
            )
            return {
                'percentage_change': None,
                'direction': 'neutral',
                'previous_price': previous_price,
                'time_gap_minutes': self._calculate_time_gap(current_snapshot, previous),
                'is_first_snapshot': False,
                'time_gap_warning': False,
            }

        # Prevent division by zero
        if previous_price == 0:
            logger.warning("Previous price is zero, cannot calculate percentage change")
            return {
                'percentage_change': None,
                'direction': 'neutral',
                'previous_price': previous_price,
                'time_gap_minutes': self._calculate_time_gap(current_snapshot, previous),
                'is_first_snapshot': False,
                'time_gap_warning': False,
            }

        # Calculate percentage change
        try:
            price_diff = current_price - previous_price
            percentage_change = (price_diff / previous_price) * Decimal('100')

            # Determine direction
            if percentage_change > Decimal('0.01'):  # > 0.01%
                direction = 'up'
            elif percentage_change < Decimal('-0.01'):  # < -0.01%
                direction = 'down'
            else:
                direction = 'neutral'

        except (InvalidOperation, ZeroDivisionError) as e:
            logger.error(f"Error calculating price change: {e}")
            return {
                'percentage_change': None,
                'direction': 'neutral',
                'previous_price': previous_price,
                'time_gap_minutes': self._calculate_time_gap(current_snapshot, previous),
                'is_first_snapshot': False,
                'time_gap_warning': False,
            }

        # Calculate time gap and check for warnings
        time_gap_minutes = self._calculate_time_gap(current_snapshot, previous)
        time_gap_warning = time_gap_minutes > 120  # > 2 hours

        if time_gap_warning:
            logger.warning(
                f"Large time gap between snapshots: {time_gap_minutes} minutes. "
                "Price change comparison may not be meaningful."
            )

        return {
            'percentage_change': percentage_change,
            'direction': direction,
            'previous_price': previous_price,
            'time_gap_minutes': time_gap_minutes,
            'is_first_snapshot': False,
            'time_gap_warning': time_gap_warning,
        }

    def calculate_market_premium(self, current_snapshot):
        """
        Calculate market premium percentage (P2P vs BCB official rate).

        Args:
            current_snapshot: MarketSnapshot instance

        Returns:
            dict: {
                'premium_percentage': Decimal or None,
                'bcb_rate': Decimal or None,
                'bcb_rate_date': date or None,
                'bcb_rate_updated_at': datetime or None,
                'bcb_rate_stale': bool,
            }
        """
        # Get latest BCB official exchange rate
        latest_indicator = MacroeconomicIndicator.objects.filter(
            official_exchange_rate__isnull=False
        ).order_by('-date').first()

        if not latest_indicator or not latest_indicator.official_exchange_rate:
            logger.warning("No BCB official exchange rate available for premium calculation")
            return {
                'premium_percentage': None,
                'bcb_rate': None,
                'bcb_rate_date': None,
                'bcb_rate_updated_at': None,
                'bcb_rate_stale': False,
            }

        # Get current P2P price
        p2p_price = current_snapshot.average_sell_price
        bcb_rate = latest_indicator.official_exchange_rate

        if p2p_price is None or bcb_rate == 0:
            logger.warning(
                f"Missing rate data for premium calculation: "
                f"P2P={p2p_price}, BCB={bcb_rate}"
            )
            return {
                'premium_percentage': None,
                'bcb_rate': bcb_rate,
                'bcb_rate_date': latest_indicator.date,
                'bcb_rate_updated_at': latest_indicator.updated_at,
                'bcb_rate_stale': False,
            }

        # Calculate premium percentage
        try:
            premium_diff = p2p_price - bcb_rate
            premium_percentage = (premium_diff / bcb_rate) * Decimal('100')

        except (InvalidOperation, ZeroDivisionError) as e:
            logger.error(f"Error calculating market premium: {e}")
            return {
                'premium_percentage': None,
                'bcb_rate': bcb_rate,
                'bcb_rate_date': latest_indicator.date,
                'bcb_rate_updated_at': latest_indicator.updated_at,
                'bcb_rate_stale': False,
            }

        # Check if BCB rate is stale (older than 48 hours)
        bcb_rate_stale = self._is_bcb_rate_stale(latest_indicator)

        if bcb_rate_stale:
            logger.warning(
                f"BCB rate is stale (from {latest_indicator.date}). "
                "Premium calculation may not reflect current official rate."
            )

        return {
            'premium_percentage': premium_percentage,
            'bcb_rate': bcb_rate,
            'bcb_rate_date': latest_indicator.date,
            'bcb_rate_updated_at': latest_indicator.updated_at,
            'bcb_rate_stale': bcb_rate_stale,
        }

    def _calculate_time_gap(self, current, previous):
        """Calculate time gap in minutes between snapshots."""
        if not current.timestamp or not previous.timestamp:
            return None

        time_diff = current.timestamp - previous.timestamp
        return int(time_diff.total_seconds() / 60)

    def _is_bcb_rate_stale(self, indicator):
        """Check if BCB rate is older than 48 hours."""
        if not indicator.updated_at:
            return True

        now = timezone.now()
        time_diff = now - indicator.updated_at
        return time_diff > timedelta(hours=48)

    def enrich_snapshot_data(self, snapshot):
        """
        Enrich snapshot data with price change and market premium.

        Args:
            snapshot: MarketSnapshot instance

        Returns:
            dict: Enriched data ready for API response
        """
        # Calculate price change
        price_change = self.calculate_price_change(snapshot)

        # Calculate market premium
        market_premium = self.calculate_market_premium(snapshot)

        # Build enriched response
        return {
            # Original snapshot fields
            'id': str(snapshot.id),
            'timestamp': snapshot.timestamp.isoformat(),
            'average_sell_price': float(snapshot.average_sell_price) if snapshot.average_sell_price else None,
            'average_buy_price': float(snapshot.average_buy_price) if snapshot.average_buy_price else None,
            'total_volume': float(snapshot.total_volume) if snapshot.total_volume else None,
            'spread_percentage': float(snapshot.spread_percentage) if snapshot.spread_percentage else None,
            'data_quality_score': snapshot.data_quality_score,

            # Price change fields
            'price_change_percentage': float(price_change['percentage_change']) if price_change['percentage_change'] is not None else None,
            'price_change_direction': price_change['direction'],
            'previous_price': float(price_change['previous_price']) if price_change['previous_price'] is not None else None,
            'is_first_snapshot': price_change['is_first_snapshot'],
            'time_gap_minutes': price_change['time_gap_minutes'],
            'time_gap_warning': price_change['time_gap_warning'],

            # Market premium fields
            'market_premium_percentage': float(market_premium['premium_percentage']) if market_premium['premium_percentage'] is not None else None,
            'bcb_official_rate': float(market_premium['bcb_rate']) if market_premium['bcb_rate'] is not None else None,
            'bcb_rate_date': market_premium['bcb_rate_date'].isoformat() if market_premium['bcb_rate_date'] else None,
            'bcb_rate_updated_at': market_premium['bcb_rate_updated_at'].isoformat() if market_premium['bcb_rate_updated_at'] else None,
            'bcb_rate_stale': market_premium['bcb_rate_stale'],
        }
