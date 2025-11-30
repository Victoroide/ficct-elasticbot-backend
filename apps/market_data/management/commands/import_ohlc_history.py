"""
Management command to import historical OHLC data from external API.

█▀▀ ▄▀█ █ █▀▄   ▄▀█ █▀█ █
█▀▀ █▀█ █ █▄▀   █▀█ █▀▀ █

CRITICAL COST CONSTRAINTS:
- This API has USAGE-BASED PRICING - every request costs real money!
- NEVER schedule this in cron, Celery Beat, or any automated system.
- Run ONLY when absolutely necessary for historical data backfill.
- The --confirm flag is REQUIRED to prevent accidental execution.

API LIMITATION:
- The API returns the LAST N points only (no offset or date range).
- To build up history, run this command periodically (manually) over time.
- Each run captures the most recent candles and skips existing timestamps.

Usage:
    # Default: 1h timeframe, 200 points (~8 days)
    python manage.py import_ohlc_history --confirm

    # Custom timeframe for different granularity
    python manage.py import_ohlc_history --confirm --timeframe 30m --points 200

    # Dry run to see what would happen
    python manage.py import_ohlc_history --dry-run

Timeframe options:
    10m  →  200 points = ~33 hours
    30m  →  200 points = ~4 days
    1h   →  200 points = ~8 days (default, recommended)

Data is stored permanently and deduplicated by timestamp.
"""
import requests
from decimal import Decimal
from datetime import datetime
from dateutil import parser as dateutil_parser

from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone
from django.db import IntegrityError

from django.conf import settings
from apps.market_data.models import MarketSnapshot


# Marker for data imported from external API (distinguishes from scraped data)
EXTERNAL_API_QUALITY_SCORE = 0.95


class Command(BaseCommand):
    help = 'Import historical OHLC data from external API (COSTS MONEY - use sparingly!)'

    # API constraints
    VALID_TIMEFRAMES = ['10m', '30m', '1h']
    VALID_POINTS = [50, 100, 200]
    REQUEST_TIMEOUT = 30  # seconds

    # Coverage estimates for documentation
    COVERAGE_HOURS = {
        '10m': lambda pts: pts * 10 / 60,   # 200 pts = 33 hours
        '30m': lambda pts: pts * 30 / 60,   # 200 pts = 100 hours
        '1h': lambda pts: pts * 1,         # 200 pts = 200 hours
    }

    def add_arguments(self, parser):
        parser.add_argument(
            '--confirm',
            action='store_true',
            required=False,
            help='REQUIRED: Confirm you understand this API call costs money'
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Validate configuration without making API call'
        )
        parser.add_argument(
            '--force',
            action='store_true',
            help='Skip check for existing imported data'
        )
        parser.add_argument(
            '--timeframe',
            type=str,
            default='1h',
            choices=self.VALID_TIMEFRAMES,
            help='Candle timeframe: 10m, 30m, or 1h (default: 1h)'
        )
        parser.add_argument(
            '--points',
            type=int,
            default=200,
            choices=self.VALID_POINTS,
            help='Number of candles: 50, 100, or 200 (default: 200)'
        )

    def handle(self, *args, **options):
        confirm = options['confirm']
        dry_run = options['dry_run']
        force = options['force']

        # Store timeframe and points as instance variables for use in other methods
        self.timeframe = options['timeframe']
        self.points = options['points']

        # Calculate estimated coverage
        coverage_hours = self.COVERAGE_HOURS[self.timeframe](self.points)
        coverage_days = coverage_hours / 24

        # Step 1: Check if --confirm flag is provided
        if not confirm and not dry_run:
            self._show_cost_warning()
            return

        # Step 2: Validate environment configuration
        api_url = self._get_api_url()
        if api_url is None:
            raise CommandError(
                'External OHLC API URL not configured.\n'
                'Add EXTERNAL_OHLC_API_URL to your .env file.\n'
                'WARNING: This API has usage-based pricing!'
            )

        # Step 3: Show current database state
        existing_count = MarketSnapshot.objects.filter(
            data_quality_score=EXTERNAL_API_QUALITY_SCORE
        ).count()

        first = MarketSnapshot.objects.filter(
            data_quality_score=EXTERNAL_API_QUALITY_SCORE
        ).order_by('timestamp').first()
        last = MarketSnapshot.objects.filter(
            data_quality_score=EXTERNAL_API_QUALITY_SCORE
        ).order_by('timestamp').last()

        self.stdout.write(self.style.NOTICE('\n' + '=' * 60))
        self.stdout.write(self.style.NOTICE('Current Database State'))
        self.stdout.write(self.style.NOTICE('=' * 60))
        self.stdout.write(f'  Existing external OHLC records: {existing_count}')
        if first and last:
            self.stdout.write(f'  Current coverage: {first.timestamp.date()} to {last.timestamp.date()}')
            span_days = (last.timestamp - first.timestamp).days
            self.stdout.write(f'  Span: {span_days} days')

        self.stdout.write('')
        self.stdout.write(self.style.WARNING('Planned Import:'))
        self.stdout.write(f'  Timeframe: {self.timeframe}')
        self.stdout.write(f'  Points: {self.points}')
        self.stdout.write(f'  Estimated coverage: ~{coverage_hours:.0f} hours (~{coverage_days:.1f} days)')
        self.stdout.write('')

        if dry_run:
            self.stdout.write(self.style.SUCCESS('✓ Dry run completed. No API call made.'))
            return

        # Step 4: Final confirmation before costly API call
        if not force:
            self.stdout.write(self.style.ERROR('⚠️  This will make a PAID API call!'))
            user_input = input('Proceed with import? (yes/no): ')
            if user_input.lower() not in ('yes', 'y'):
                self.stdout.write(self.style.NOTICE('Import cancelled.'))
                return

        self.stdout.write(self.style.NOTICE(
            f'\nStarting OHLC import: timeframe={self.timeframe}, points={self.points}'
        ))
        self.stdout.write(self.style.WARNING('💰 Making paid API call...\n'))

        # Step 5: Fetch data from API (THE COSTLY OPERATION)
        data = self._fetch_ohlc_data(api_url)
        if data is None:
            raise CommandError('Failed to fetch data from API')

        # Phase 2: Parse and validate
        buy_candles = data.get('buy', [])
        sell_candles = data.get('sell', [])

        if not buy_candles or not sell_candles:
            raise CommandError('API response missing buy or sell data arrays')

        if len(buy_candles) != len(sell_candles):
            self.stdout.write(self.style.WARNING(
                f'Buy/Sell array length mismatch: {len(buy_candles)} vs {len(sell_candles)}'
            ))

        self.stdout.write(f'Received {len(buy_candles)} buy candles, {len(sell_candles)} sell candles')

        # Phase 3: Transform and import
        created_count = 0
        skipped_count = 0
        error_count = 0

        # Create a lookup dict for sell candles by date
        sell_by_date = {candle['date']: candle for candle in sell_candles if 'date' in candle}

        for buy_candle in buy_candles:
            try:
                # Validate required fields
                if 'date' not in buy_candle:
                    self.stdout.write(self.style.WARNING('Skipping candle: missing date field'))
                    error_count += 1
                    continue

                date_str = buy_candle['date']
                sell_candle = sell_by_date.get(date_str)

                if sell_candle is None:
                    self.stdout.write(self.style.WARNING(f'Skipping {date_str}: no matching sell candle'))
                    error_count += 1
                    continue

                # Transform candle to MarketSnapshot
                snapshot_data = self._transform_candle(buy_candle, sell_candle)

                if snapshot_data is None:
                    error_count += 1
                    continue

                if dry_run:
                    self.stdout.write(f'  [DRY-RUN] Would create: {snapshot_data["timestamp"]}')
                    created_count += 1
                    continue

                # Idempotent insert using get_or_create
                snapshot, created = MarketSnapshot.objects.get_or_create(
                    timestamp=snapshot_data['timestamp'],
                    defaults=snapshot_data
                )

                if created:
                    created_count += 1
                    if created_count % 20 == 0:
                        self.stdout.write(f'  Progress: {created_count} records created...')
                else:
                    skipped_count += 1

            except IntegrityError as e:
                self.stdout.write(self.style.WARNING(f'Database integrity error for {date_str}: {e}'))
                skipped_count += 1
            except Exception as e:
                self.stdout.write(self.style.ERROR(f'Error processing candle: {e}'))
                error_count += 1

        # Summary
        self.stdout.write('')
        self.stdout.write(self.style.SUCCESS('=' * 50))
        self.stdout.write(self.style.SUCCESS('Import Summary:'))
        self.stdout.write(f'  Records created: {created_count}')
        self.stdout.write(f'  Records skipped (already exist): {skipped_count}')
        self.stdout.write(f'  Errors: {error_count}')
        self.stdout.write(self.style.SUCCESS('=' * 50))

        if not dry_run and created_count > 0:
            # Verify import
            total = MarketSnapshot.objects.count()
            first = MarketSnapshot.objects.order_by('timestamp').first()
            last = MarketSnapshot.objects.order_by('timestamp').last()

            self.stdout.write('')
            self.stdout.write(self.style.SUCCESS('Database Verification:'))
            self.stdout.write(f'  Total MarketSnapshot records: {total}')
            if first and last:
                self.stdout.write(f'  Date range: {first.timestamp} to {last.timestamp}')

            self.stdout.write('')
            self.stdout.write(self.style.SUCCESS('✅ Import completed successfully!'))
            self.stdout.write('')
            self.stdout.write('You can now run elasticity calculations. Example:')
            self.stdout.write(self.style.NOTICE(
                f'  curl -X POST http://localhost:8000/api/v1/elasticity/calculate/ \\\n'
                f'    -H "Content-Type: application/json" \\\n'
                f'    -d \'{{"method":"midpoint","start_date":"{first.timestamp.date()}T00:00:00Z",'
                f'"end_date":"{last.timestamp.date()}T23:59:59Z","window_size":"daily"}}\''
            ))

    def _show_cost_warning(self):
        """Display cost warning when --confirm flag is missing."""
        self.stdout.write(self.style.ERROR('\n' + '=' * 60))
        self.stdout.write(self.style.ERROR('⚠️  COST WARNING: External API has usage-based pricing!'))
        self.stdout.write(self.style.ERROR('=' * 60))
        self.stdout.write('')
        self.stdout.write('This command makes a request to a PAID third-party API.')
        self.stdout.write('Every execution costs real money.')
        self.stdout.write('')
        self.stdout.write('Before running, ensure you:')
        self.stdout.write('  1. Actually need historical data (check database first)')
        self.stdout.write('  2. Haven\'t already imported data recently')
        self.stdout.write('  3. Have EXTERNAL_OHLC_API_URL configured in .env')
        self.stdout.write('')
        self.stdout.write('To proceed, run with --confirm flag:')
        self.stdout.write(self.style.SUCCESS('  python manage.py import_ohlc_history --confirm'))
        self.stdout.write('')
        self.stdout.write('To test configuration without API call:')
        self.stdout.write(self.style.SUCCESS('  python manage.py import_ohlc_history --dry-run'))
        self.stdout.write('')

    def _get_api_url(self) -> str | None:
        """Get API URL from settings, return None if not configured."""
        url = getattr(settings, 'EXTERNAL_OHLC_API_URL', None)
        if url and url.strip():
            return url.strip()
        return None

    def _fetch_ohlc_data(self, api_url: str) -> dict | None:
        """
        Fetch OHLC data from external API.

        Returns parsed JSON data dict or None on failure.
        """
        params = {
            'platform': 'binance',
            'base': 'USDT',
            'quote': 'BOB',
            'timeframe': self.timeframe,
            'points': self.points
        }

        headers = {
            'Accept': 'application/json',
            'Content-Type': 'application/json'
        }

        self.stdout.write(f'Fetching data from API: {api_url}')
        self.stdout.write(f'Parameters: {params}')

        try:
            response = requests.get(
                api_url,
                params=params,
                headers=headers,
                timeout=self.REQUEST_TIMEOUT
            )

            self.stdout.write(f'Response status: {response.status_code}')

            if response.status_code != 200:
                self.stdout.write(self.style.ERROR(
                    f'API returned non-200 status: {response.status_code}'
                ))
                self.stdout.write(f'Response body: {response.text[:500]}')
                return None

            data = response.json()

            if not data.get('success', False):
                self.stdout.write(self.style.ERROR(
                    f'API returned success=false: {data.get("error", "Unknown error")}'
                ))
                return None

            return data.get('data', {})

        except requests.Timeout:
            self.stdout.write(self.style.ERROR(
                f'Request timed out after {self.REQUEST_TIMEOUT} seconds'
            ))
            return None
        except requests.RequestException as e:
            self.stdout.write(self.style.ERROR(f'Network error: {e}'))
            return None
        except ValueError as e:
            self.stdout.write(self.style.ERROR(f'JSON parsing error: {e}'))
            self.stdout.write(f'Raw response: {response.text[:500]}')
            return None

    def _transform_candle(self, buy_candle: dict, sell_candle: dict) -> dict | None:
        """
        Transform buy and sell OHLC candles into MarketSnapshot fields.

        Returns dict of MarketSnapshot field values or None if invalid.
        """
        try:
            # Parse timestamp (ISO 8601 with Z suffix)
            date_str = buy_candle['date']
            timestamp = dateutil_parser.isoparse(date_str)

            # Ensure timezone-aware UTC
            if timestamp.tzinfo is None:
                timestamp = timestamp.replace(tzinfo=timezone.utc)

            # Extract prices - use close price as representative
            buy_close = buy_candle.get('close')
            sell_close = sell_candle.get('close')

            if buy_close is None or sell_close is None:
                self.stdout.write(self.style.WARNING(
                    f'Skipping {date_str}: missing close price'
                ))
                return None

            # Convert to Decimal for precision
            average_sell_price = Decimal(str(sell_close))
            average_buy_price = Decimal(str(buy_close))

            # ================================================================
            # SPREAD CALCULATION
            # ================================================================
            # Spread = (sell_price - buy_price) / midpoint * 100
            # This represents the percentage difference between what sellers
            # are asking and what buyers are offering.
            # ================================================================
            midpoint = (average_sell_price + average_buy_price) / 2
            if midpoint > 0:
                spread_percentage = ((average_sell_price - average_buy_price) / midpoint) * 100
            else:
                spread_percentage = Decimal('0')

            # ================================================================
            # VOLUME - ESTIMATED WITH HOUR-BASED VARIATION
            # ================================================================
            # The external OHLC API does NOT provide trading volume data.
            # It only returns price candles (open, high, low, close).
            #
            # To maintain chart consistency, we use an estimated volume
            # based on P2P average (~250K USDT) with hour-based variation:
            # - Peak hours (business): 1.0-1.3x multiplier
            # - Night hours: 0.1-0.4x multiplier
            #
            # DO NOT create fake volume from price range - that was a bug!
            # ================================================================
            import random

            # Hour-based multipliers (UTC hours)
            hour_multipliers = {
                0: 0.4, 1: 0.3, 2: 0.2, 3: 0.15, 4: 0.1, 5: 0.1,
                6: 0.15, 7: 0.2, 8: 0.3, 9: 0.5, 10: 0.7, 11: 0.85,
                12: 1.0, 13: 1.2, 14: 1.3, 15: 1.2, 16: 1.0, 17: 0.9,
                18: 1.1, 19: 1.2, 20: 1.1, 21: 0.9, 22: 0.7, 23: 0.5,
            }

            base_volume = Decimal('250000.00')
            hour = timestamp.hour
            hour_mult = Decimal(str(hour_multipliers.get(hour, 1.0)))
            random_mult = Decimal(str(random.uniform(0.8, 1.2)))
            total_volume = (base_volume * hour_mult * random_mult).quantize(Decimal('0.01'))

            return {
                'timestamp': timestamp,
                'average_sell_price': average_sell_price,
                'average_buy_price': average_buy_price,
                'total_volume': total_volume,
                # NO abs() - keep actual spread sign to match P2P data
                'spread_percentage': spread_percentage,
                # num_active_traders: Always 0 for external API data.
                # This field is NOT USED in elasticity calculations (by design).
                'num_active_traders': 0,
                # Quality score marker: 0.95 identifies external API data.
                # Elasticity engine filters for >= 0.95 to exclude P2P scraped data.
                'data_quality_score': EXTERNAL_API_QUALITY_SCORE,
                # raw_response: Preserves COMPLETE OHLC candle data for future use.
                # Frontend can use this for charting without additional API calls.
                # Contains: source, timeframe, and full buy/sell candles (open, high, low, close)
                'raw_response': {
                    'source': 'external_ohlc_api',
                    'timeframe': self.timeframe,
                    'buy_candle': buy_candle,
                    'sell_candle': sell_candle,
                    # Volume estimation metadata
                    'volume_estimated': True,
                    'volume_hour_multiplier': float(hour_mult),
                    'volume_note': f'Volume estimated with hour-based variation (hour {hour} UTC = {hour_mult}x)'
                }
            }

        except (KeyError, ValueError, TypeError) as e:
            self.stdout.write(self.style.WARNING(
                f'Transform error for candle: {e}'
            ))
            return None
