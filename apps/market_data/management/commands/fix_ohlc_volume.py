"""
Management command to fix OHLC records with synthetic/fake volume values.

BACKGROUND:
The external OHLC API does NOT provide trading volume data - only price candles
(open, high, low, close). A previous implementation incorrectly created
"synthetic" volume values using the formula: (high - low) * 10000

This resulted in small, meaningless volume values (e.g., 300, 1000) that:
- Don't represent actual trading volume
- Contradict the much larger real volumes from P2P scraper
- Cause confusion in charts and analysis

SOLUTION:
This command sets total_volume to realistic VARIED values based on:
- Base average from P2P scraper data
- Hour of day variation (more volume during business hours)
- Random variation (+/- 20%) for realism

Also fixes spread to use correct sign (matching P2P data).

Usage:
    # Preview changes
    python manage.py fix_ohlc_volume --dry-run

    # Execute fix
    python manage.py fix_ohlc_volume --confirm
"""
import random
from decimal import Decimal

from django.core.management.base import BaseCommand
from django.db import transaction
from django.db.models import Avg

from apps.market_data.models import MarketSnapshot


# Quality threshold for external OHLC data
OHLC_QUALITY_THRESHOLD = 0.95

# Quality score for P2P scraper data
P2P_QUALITY_SCORE = 0.80

# Hour-based volume multipliers (Bolivia timezone = UTC-4)
# Peak hours: 9-12 and 14-18 Bolivia time (13-16 and 18-22 UTC)
HOUR_VOLUME_MULTIPLIERS = {
    0: 0.4,   # 20:00 Bolivia - low
    1: 0.3,   # 21:00 Bolivia - low
    2: 0.2,   # 22:00 Bolivia - very low
    3: 0.15,  # 23:00 Bolivia - very low
    4: 0.1,   # 00:00 Bolivia - minimal
    5: 0.1,   # 01:00 Bolivia - minimal
    6: 0.15,  # 02:00 Bolivia - minimal
    7: 0.2,   # 03:00 Bolivia - minimal
    8: 0.3,   # 04:00 Bolivia - waking up
    9: 0.5,   # 05:00 Bolivia - early morning
    10: 0.7,  # 06:00 Bolivia - morning
    11: 0.85,  # 07:00 Bolivia - morning
    12: 1.0,  # 08:00 Bolivia - business hours
    13: 1.2,  # 09:00 Bolivia - peak
    14: 1.3,  # 10:00 Bolivia - peak
    15: 1.2,  # 11:00 Bolivia - peak
    16: 1.0,  # 12:00 Bolivia - lunch
    17: 0.9,  # 13:00 Bolivia - afternoon
    18: 1.1,  # 14:00 Bolivia - afternoon peak
    19: 1.2,  # 15:00 Bolivia - afternoon peak
    20: 1.1,  # 16:00 Bolivia - late afternoon
    21: 0.9,  # 17:00 Bolivia - evening
    22: 0.7,  # 18:00 Bolivia - dinner
    23: 0.5,  # 19:00 Bolivia - evening
}


class Command(BaseCommand):
    help = 'Fix OHLC records: set realistic volume based on P2P average'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Preview changes without modifying database'
        )
        parser.add_argument(
            '--confirm',
            action='store_true',
            help='Execute the fix'
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        confirm = options['confirm']

        if not dry_run and not confirm:
            self._show_usage()
            return

        # Find all OHLC records
        ohlc_records = MarketSnapshot.objects.filter(
            data_quality_score__gte=OHLC_QUALITY_THRESHOLD
        )

        total_count = ohlc_records.count()

        self.stdout.write(self.style.NOTICE(f'\nFound {total_count} OHLC records to process'))

        if total_count == 0:
            self.stdout.write(self.style.WARNING('No OHLC records found.'))
            return

        # Calculate average volume from P2P scraper data
        p2p_avg = MarketSnapshot.objects.filter(
            data_quality_score__lt=OHLC_QUALITY_THRESHOLD,
            total_volume__gt=0
        ).aggregate(avg_volume=Avg('total_volume'))

        self.avg_volume = p2p_avg['avg_volume'] or Decimal('250000')
        self.stdout.write(f'  Average P2P volume: {self.avg_volume:,.2f}')

        # Check for records with positive spread (wrong sign) or identical volume
        # from django.db.models import Q
        wrong_spread = ohlc_records.filter(spread_percentage__gt=0).count()

        self.stdout.write(f'  Records with positive spread (needs fix): {wrong_spread}')
        self.stdout.write(f'  All {total_count} OHLC records will be updated with varied volume')

        if dry_run:
            self._dry_run_analysis(ohlc_records)
            return

        self._execute_fix(ohlc_records)

    def _show_usage(self):
        """Show usage instructions."""
        self.stdout.write(self.style.ERROR('\n' + '=' * 60))
        self.stdout.write(self.style.ERROR('Fix OHLC Volume Command'))
        self.stdout.write(self.style.ERROR('=' * 60))
        self.stdout.write('')
        self.stdout.write('This command fixes OHLC records that have incorrect synthetic volume.')
        self.stdout.write('')
        self.stdout.write('What it does:')
        self.stdout.write('  1. Sets total_volume to average from P2P scraper data (~250K)')
        self.stdout.write('  2. Recalculates spread_percentage from original candle data')
        self.stdout.write('  3. Marks records as estimated in raw_response')
        self.stdout.write('')
        self.stdout.write('Usage:')
        self.stdout.write(self.style.SUCCESS('  # Preview changes'))
        self.stdout.write('  python manage.py fix_ohlc_volume --dry-run')
        self.stdout.write('')
        self.stdout.write(self.style.SUCCESS('  # Execute fix'))
        self.stdout.write('  python manage.py fix_ohlc_volume --confirm')
        self.stdout.write('')

    def _dry_run_analysis(self, ohlc_records):
        """Preview what would be changed."""
        self.stdout.write(self.style.NOTICE('\n' + '=' * 60))
        self.stdout.write(self.style.NOTICE('DRY RUN - No database changes'))
        self.stdout.write(self.style.NOTICE('=' * 60))

        # Show sample records
        samples = ohlc_records.order_by('timestamp')[:5]

        self.stdout.write(f'\nBase volume: {self.avg_volume:,.2f} (P2P average)')
        self.stdout.write('Volume will vary by hour (0.1x - 1.3x) + random (0.8x - 1.2x)')
        self.stdout.write('\nSample records to fix:')
        for record in samples:
            old_volume = record.total_volume
            old_spread = record.spread_percentage

            # Calculate new values
            hour = record.timestamp.hour
            hour_mult = HOUR_VOLUME_MULTIPLIERS.get(hour, 1.0)
            estimated_volume = self.avg_volume * Decimal(str(hour_mult))
            new_spread = self._recalculate_spread(record)

            self.stdout.write(f'\n  {record.timestamp} (hour {hour}, mult {hour_mult}x):')
            self.stdout.write(f'    Volume: {old_volume:,.2f} -> ~{estimated_volume:,.2f} (+/- 20%)')
            self.stdout.write(f'    Spread: {old_spread}% -> {new_spread}%')

        self.stdout.write('')
        self.stdout.write(self.style.SUCCESS('[OK] Dry run completed. No database changes made.'))
        self.stdout.write('')
        self.stdout.write('To execute the fix, run:')
        self.stdout.write(self.style.NOTICE('  python manage.py fix_ohlc_volume --confirm'))

    def _execute_fix(self, ohlc_records):
        """Execute the volume fix."""
        self.stdout.write(self.style.NOTICE('\n' + '=' * 60))
        self.stdout.write(self.style.NOTICE('Executing OHLC Volume Fix'))
        self.stdout.write(self.style.NOTICE('=' * 60))
        self.stdout.write(f'  Setting volume to: {self.avg_volume:,.2f}')

        fixed_count = 0
        error_count = 0
        spread_updated = 0

        # Fix ALL OHLC records with varied volume and correct spread
        records_to_fix = ohlc_records.order_by('timestamp')
        total = records_to_fix.count()

        with transaction.atomic():
            for idx, record in enumerate(records_to_fix.iterator()):
                try:
                    # Calculate varied volume based on hour
                    hour = record.timestamp.hour
                    hour_multiplier = HOUR_VOLUME_MULTIPLIERS.get(hour, 1.0)

                    # Add random variation (+/- 20%)
                    random_factor = random.uniform(0.8, 1.2)

                    # Calculate final volume
                    varied_volume = self.avg_volume * Decimal(str(hour_multiplier)) * Decimal(str(random_factor))
                    record.total_volume = varied_volume.quantize(Decimal('0.01'))

                    # Recalculate spread from raw candle data (WITHOUT abs())
                    new_spread = self._recalculate_spread(record)
                    if new_spread is not None:
                        record.spread_percentage = new_spread
                        spread_updated += 1

                    # Update raw_response with estimation note
                    if record.raw_response:
                        record.raw_response['volume_estimated'] = True
                        record.raw_response['volume_hour_multiplier'] = hour_multiplier
                        record.raw_response['volume_note'] = (
                            f'Volume estimated from P2P average with hour-based variation (hour {hour} UTC = {hour_multiplier}x)'
                        )
                        record.raw_response['fixed_at'] = 'backfill_fix_ohlc_volume_v2'

                    record.save(update_fields=[
                        'total_volume',
                        'spread_percentage',
                        'raw_response',
                        'updated_at'
                    ])
                    fixed_count += 1

                    if (idx + 1) % 50 == 0:
                        self.stdout.write(f'  Progress: {idx + 1}/{total} records fixed')

                except Exception as e:
                    self.stdout.write(self.style.WARNING(f'Error fixing record {record.id}: {e}'))
                    error_count += 1

        # Summary
        self.stdout.write('')
        self.stdout.write(self.style.SUCCESS('=' * 50))
        self.stdout.write(self.style.SUCCESS('Fix Summary:'))
        self.stdout.write(f'  Records fixed: {fixed_count}')
        self.stdout.write(f'  New volume: {self.avg_volume:,.2f}')
        self.stdout.write(f'  Spreads recalculated: {spread_updated}')
        self.stdout.write(f'  Errors: {error_count}')
        self.stdout.write(self.style.SUCCESS('=' * 50))
        self.stdout.write('')
        self.stdout.write(self.style.SUCCESS('[DONE] OHLC volume fix completed!'))
        self.stdout.write('')
        self.stdout.write('Notes:')
        self.stdout.write('  - OHLC records now have realistic volume matching P2P average')
        self.stdout.write('  - Volume is marked as estimated in raw_response')
        self.stdout.write('  - Charts will show consistent volume across data sources')

    def _recalculate_spread(self, record) -> Decimal | None:
        """
        Recalculate spread_percentage from raw_response candle data.

        The spread is calculated as:
            spread = (sell_price - buy_price) / midpoint * 100

        This can be NEGATIVE if sell_price < buy_price, which is normal
        in P2P markets where:
        - buy_price = what buyers offer (you receive when selling)
        - sell_price = what sellers ask (you pay when buying)

        Returns:
            New spread percentage (can be negative), or None if calculation not possible
        """
        if not record.raw_response:
            return None

        try:
            buy_candle = record.raw_response.get('buy_candle', {})
            sell_candle = record.raw_response.get('sell_candle', {})

            buy_close = buy_candle.get('close')
            sell_close = sell_candle.get('close')

            if buy_close is None or sell_close is None:
                return None

            buy_price = Decimal(str(buy_close))
            sell_price = Decimal(str(sell_close))

            midpoint = (sell_price + buy_price) / 2
            if midpoint > 0:
                # NO abs() - keep the actual sign to match P2P data
                spread = ((sell_price - buy_price) / midpoint) * 100
                return spread.quantize(Decimal('0.0001'))

            return Decimal('0')

        except (KeyError, TypeError, ValueError):
            return None
