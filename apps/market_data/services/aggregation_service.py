"""
Aggregation service for market data time series.

This service provides backend-driven aggregation logic for the "Historial de Precios
USDT/BOB" chart, replacing heavy frontend calculations with efficient server-side
processing.

Features:
- Time range filtering (24h, 7d, 30d, 90d, or custom date range)
- Granularity aggregation (hourly, daily, weekly)
- Data source filtering (p2p, ohlc, all)
- Coverage statistics calculation

Design decisions:
- No gap filling: If there's no data for a period, that period is omitted
- UTC timezone: All aggregations use UTC for consistency
- Ordered output: Always ascending by timestamp
"""
from decimal import Decimal
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional
from django.db.models import QuerySet
from django.utils import timezone
from collections import defaultdict

from apps.market_data.models import MarketSnapshot


# Source identifiers
SOURCE_P2P = 'p2p_scrape_json'
SOURCE_OHLC = 'external_ohlc_api'

# Quality thresholds
P2P_QUALITY_SCORE = 0.80
OHLC_QUALITY_THRESHOLD = 0.95

# Valid time ranges
TIME_RANGES = {
    '24h': timedelta(hours=24),
    '7d': timedelta(days=7),
    '30d': timedelta(days=30),
    '90d': timedelta(days=90),
}

# Valid granularities
GRANULARITIES = ['hourly', 'daily', 'weekly']

# Valid source filters
SOURCE_FILTERS = ['p2p', 'ohlc', 'all']


class AggregationService:
    """
    Service for aggregating market snapshot data for chart visualization.

    Centralizes all aggregation logic that was previously on the frontend,
    providing efficient server-side processing and a single source of truth.
    """

    def get_aggregated_data(
        self,
        time_range: Optional[str] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        granularity: str = 'daily',
        source: str = 'all',
    ) -> Dict[str, Any]:
        """
        Get aggregated market data for chart visualization.

        Args:
            time_range: One of '24h', '7d', '30d', '90d' (ignored if dates provided)
            start_date: Explicit start date (timezone-aware)
            end_date: Explicit end date (timezone-aware)
            granularity: One of 'hourly', 'daily', 'weekly'
            source: One of 'p2p', 'ohlc', 'all'

        Returns:
            Dictionary with:
            - time_range: The effective time range used
            - granularity: The granularity applied
            - coverage_start: First timestamp in results
            - coverage_end: Last timestamp in results
            - span_days: Actual data span in days
            - data_source: Source type(s) included
            - total_records: Count of raw snapshots used
            - aggregated_points: Count of aggregated data points
            - points: List of aggregated data points

        Raises:
            ValueError: If invalid parameters provided
        """
        # Validate granularity
        if granularity not in GRANULARITIES:
            raise ValueError(f"Invalid granularity. Must be one of: {GRANULARITIES}")

        # Validate source
        if source not in SOURCE_FILTERS:
            raise ValueError(f"Invalid source. Must be one of: {SOURCE_FILTERS}")

        # Determine date range
        if start_date and end_date:
            effective_range = 'custom'
        elif time_range:
            if time_range not in TIME_RANGES:
                raise ValueError(f"Invalid time_range. Must be one of: {list(TIME_RANGES.keys())}")
            end_date = timezone.now()
            start_date = end_date - TIME_RANGES[time_range]
            effective_range = time_range
        else:
            # Default to 7d
            end_date = timezone.now()
            start_date = end_date - TIME_RANGES['7d']
            effective_range = '7d'

        # Get filtered queryset
        snapshots = self._get_filtered_snapshots(start_date, end_date, source)

        # Get raw data for aggregation
        snapshot_list = list(snapshots.values(
            'timestamp',
            'average_buy_price',
            'average_sell_price',
            'total_volume',
            'spread_percentage',
            'data_quality_score',
            'raw_response',
        ))

        total_records = len(snapshot_list)

        if total_records == 0:
            return {
                'time_range': effective_range,
                'granularity': granularity,
                'coverage_start': None,
                'coverage_end': None,
                'span_days': 0,
                'data_source': source,
                'total_records': 0,
                'aggregated_points': 0,
                'points': [],
            }

        # Aggregate data based on granularity
        if granularity == 'hourly':
            points = self._aggregate_hourly(snapshot_list)
        elif granularity == 'daily':
            points = self._aggregate_daily(snapshot_list)
        else:  # weekly
            points = self._aggregate_weekly(snapshot_list)

        # Calculate coverage statistics
        coverage_start = points[0]['timestamp'] if points else None
        coverage_end = points[-1]['timestamp'] if points else None

        if coverage_start and coverage_end:
            span_delta = coverage_end - coverage_start
            span_days = round(span_delta.total_seconds() / 86400, 2)
        else:
            span_days = 0

        # Determine actual data source
        actual_source = self._determine_actual_source(snapshot_list)

        return {
            'time_range': effective_range,
            'granularity': granularity,
            'coverage_start': coverage_start.isoformat() if coverage_start else None,
            'coverage_end': coverage_end.isoformat() if coverage_end else None,
            'span_days': span_days,
            'data_source': actual_source,
            'total_records': total_records,
            'aggregated_points': len(points),
            'points': self._serialize_points(points),
        }

    def _get_filtered_snapshots(
        self,
        start_date: datetime,
        end_date: datetime,
        source: str,
    ) -> QuerySet:
        """
        Get filtered queryset based on date range and source.

        Args:
            start_date: Start of date range
            end_date: End of date range
            source: Source filter ('p2p', 'ohlc', 'all')

        Returns:
            Filtered QuerySet of MarketSnapshot objects
        """
        qs = MarketSnapshot.objects.filter(
            timestamp__gte=start_date,
            timestamp__lte=end_date,
        )

        if source == 'p2p':
            # P2P scrape data has quality score 0.8
            qs = qs.filter(data_quality_score=P2P_QUALITY_SCORE)
        elif source == 'ohlc':
            # External OHLC has quality score >= 0.95
            qs = qs.filter(data_quality_score__gte=OHLC_QUALITY_THRESHOLD)
        # 'all' includes everything

        return qs.order_by('timestamp')

    def _aggregate_hourly(self, snapshots: List[Dict]) -> List[Dict]:
        """
        Hourly aggregation - returns each snapshot as a data point.

        For hourly granularity, we don't aggregate but return individual points.
        This is useful for short time ranges (24h) where detail is important.
        """
        return [
            {
                'timestamp': s['timestamp'],
                'average_buy_price': s['average_buy_price'],
                'average_sell_price': s['average_sell_price'],
                'total_volume': s['total_volume'],
                'spread_percentage': s['spread_percentage'],
            }
            for s in snapshots
        ]

    def _aggregate_daily(self, snapshots: List[Dict]) -> List[Dict]:
        """
        Daily aggregation - group by date.

        Calculates:
        - average_buy_price: Simple average of buy prices for the day
        - average_sell_price: Simple average of sell prices for the day
        - total_volume: AVERAGE of volumes for the day (not sum!)
        - spread_percentage: Average spread for the day

        IMPORTANT - Volume semantics:
        In P2P snapshots, `total_volume` represents the STOCK/OFFER LEVEL
        (available volume in active ads at that moment), NOT traded volume.

        Therefore:
        - Summing volumes across hours would count the same stock multiple times
        - We use AVERAGE to show the typical offer level for the day
        - `volume_sum` is included as metadata for reference

        Note: OHLC data has estimated volume based on P2P averages.
        """
        # Group by date using defaultdict
        daily_data = defaultdict(list)

        for snapshot in snapshots:
            # Extract date part from timestamp
            date_key = snapshot['timestamp'].date()
            daily_data[date_key].append(snapshot)

        # Aggregate each day's data
        results = []
        for date_key, day_snapshots in daily_data.items():
            # Calculate averages for the day
            avg_buy = sum(s['average_buy_price'] for s in day_snapshots) / len(day_snapshots)
            avg_sell = sum(s['average_sell_price'] for s in day_snapshots) / len(day_snapshots)
            avg_volume = sum(s['total_volume'] for s in day_snapshots) / len(day_snapshots)
            avg_spread = sum(s['spread_percentage'] for s in day_snapshots) / len(day_snapshots)

            # Use the timestamp of the first snapshot of the day
            day_timestamp = min(s['timestamp'] for s in day_snapshots)

            results.append({
                'timestamp': day_timestamp,
                'average_buy_price': avg_buy,
                'average_sell_price': avg_sell,
                'total_volume': avg_volume,
                'spread_percentage': avg_spread,
            })

        return results

    def _aggregate_weekly(self, snapshots: List[Dict]) -> List[Dict]:
        """
        Weekly aggregation - group by ISO week.

        Uses ISO week numbering where weeks start on Monday.

        Calculates:
        - average_buy_price: Simple average of buy prices for the week
        - average_sell_price: Simple average of sell prices for the week
        - total_volume: AVERAGE of volumes for the week (not sum!)
        - spread_percentage: Average spread for the week

        IMPORTANT - Volume semantics:
        In P2P snapshots, `total_volume` represents the STOCK/OFFER LEVEL
        (available volume in active ads at that moment), NOT traded volume.

        Therefore:
        - Summing volumes across days would count the same stock multiple times
        - We use AVERAGE to show the typical offer level for the week
        - `volume_sum` is included as metadata for reference
        """
        # Group by ISO week (year, week_number)
        by_week = defaultdict(list)
        for s in snapshots:
            iso_cal = s['timestamp'].isocalendar()
            week_key = (iso_cal.year, iso_cal.week)
            by_week[week_key].append(s)

        points = []
        for week_key in sorted(by_week.keys()):
            week_snapshots = by_week[week_key]

            # Calculate averages
            buy_prices = [
                s['average_buy_price']
                for s in week_snapshots
                if s['average_buy_price'] is not None
            ]
            sell_prices = [
                s['average_sell_price']
                for s in week_snapshots
                if s['average_sell_price'] is not None
            ]
            # Filter out null volumes (OHLC data doesn't have volume)
            volumes = [
                s['total_volume']
                for s in week_snapshots
                if s['total_volume'] is not None
            ]
            spreads = [
                s['spread_percentage']
                for s in week_snapshots
                if s['spread_percentage'] is not None
            ]

            # Get first day of the ISO week (Monday)
            year, week = week_key
            # ISO week 1 of a year may start in the previous calendar year
            first_day = datetime.strptime(f'{year}-W{week:02d}-1', '%G-W%V-%u')
            aggregate_timestamp = first_day.replace(tzinfo=timezone.utc)

            # Volume aggregation: use AVERAGE (not sum) because volume represents
            # stock/offer level, not traded volume. Summing would be meaningless.
            volume_sum = sum(volumes) if volumes else None
            volume_avg = (volume_sum / len(volumes)) if volumes else None

            points.append({
                'timestamp': aggregate_timestamp,
                'average_buy_price': (
                    sum(buy_prices) / len(buy_prices) if buy_prices else Decimal('0')
                ),
                'average_sell_price': (
                    sum(sell_prices) / len(sell_prices) if sell_prices else Decimal('0')
                ),
                # Use AVERAGE for charting (typical weekly offer level)
                'total_volume': volume_avg,
                # Include sum as metadata for reference/tooltips
                'volume_sum': volume_sum,
                'spread_percentage': (
                    sum(spreads) / len(spreads) if spreads else Decimal('0')
                ),
                'record_count': len(week_snapshots),
                'has_volume_data': len(volumes) > 0,
            })

        return points

    def _determine_actual_source(self, snapshots: List[Dict]) -> str:
        """
        Determine the actual data source(s) present in the data.

        Returns:
            'p2p_scrape_json' if only P2P data
            'external_ohlc_api' if only OHLC data
            'mixed' if both sources present
        """
        has_p2p = False
        has_ohlc = False

        for s in snapshots:
            quality = s.get('data_quality_score', 0)
            if quality == P2P_QUALITY_SCORE:
                has_p2p = True
            elif quality >= OHLC_QUALITY_THRESHOLD:
                has_ohlc = True

            if has_p2p and has_ohlc:
                break

        if has_p2p and has_ohlc:
            return 'mixed'
        elif has_ohlc:
            return SOURCE_OHLC
        elif has_p2p:
            return SOURCE_P2P
        else:
            return 'unknown'

    def _serialize_points(self, points: List[Dict]) -> List[Dict]:
        """
        Serialize aggregated points for JSON response.

        Converts Decimal and datetime to JSON-serializable types.
        Handles null volumes gracefully (OHLC data doesn't have volume).
        """
        serialized = []
        for p in points:
            point = {
                'timestamp': p['timestamp'].isoformat(),
                'average_buy_price': float(p['average_buy_price']),
                'average_sell_price': float(p['average_sell_price']),
                # Volume can be null for OHLC data
                'total_volume': float(p['total_volume']) if p['total_volume'] is not None else None,
                'spread_percentage': float(p['spread_percentage']),
            }

            # Include optional fields if present (for daily/weekly aggregations)
            if 'record_count' in p:
                point['record_count'] = p['record_count']
            if 'has_volume_data' in p:
                point['has_volume_data'] = p['has_volume_data']
            # volume_sum is the raw sum, useful for tooltips (total_volume is average)
            if 'volume_sum' in p:
                point['volume_sum'] = float(p['volume_sum']) if p['volume_sum'] is not None else None

            serialized.append(point)
        return serialized


# Singleton instance for easy import
aggregation_service = AggregationService()
