"""
Management command to import historical P2P scrape data from p2p_scrapes.json.

This command imports legacy P2P data captured by Lambda scrapers and stores it
in MarketSnapshot with appropriate quality markers to distinguish it from
high-quality external OHLC API data.

IMPORTANT DATA SEPARATION:
- P2P scrape data: data_quality_score=0.8, source='p2p_scrape_json'
- External OHLC data: data_quality_score=0.95, source='external_ohlc_api'

Elasticity calculations ONLY use external OHLC data (quality >= 0.95).
P2P scrape data is for visualization, historical context, and exploratory analysis.

Usage:
    # Preview what would be imported (no database changes)
    python manage.py import_p2p_scrapes --dry-run

    # Execute the import
    python manage.py import_p2p_scrapes --confirm

    # Overwrite existing P2P records (never touches OHLC data)
    python manage.py import_p2p_scrapes --confirm --overwrite
"""
import json
import os
from decimal import Decimal, InvalidOperation
from datetime import datetime
from dateutil import parser as dateutil_parser

from django.core.management.base import BaseCommand, CommandError
from django.conf import settings

from apps.market_data.models import MarketSnapshot


# Quality score marker for P2P scrape data (lower than OHLC's 0.95)
P2P_SCRAPE_QUALITY_SCORE = 0.80

# Source identifier for raw_response
P2P_SCRAPE_SOURCE = 'p2p_scrape_json'

# Quality threshold for external OHLC data (do not modify these records)
EXTERNAL_OHLC_QUALITY_THRESHOLD = 0.95


class Command(BaseCommand):
    help = 'Import historical P2P scrape data from p2p_scrapes.json'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Preview import without making database changes'
        )
        parser.add_argument(
            '--confirm',
            action='store_true',
            help='Execute the actual import'
        )
        parser.add_argument(
            '--overwrite',
            action='store_true',
            default=False,
            help='Overwrite existing P2P scrape records (never modifies OHLC data)'
        )
        parser.add_argument(
            '--file',
            type=str,
            default='p2p_scrapes.json',
            help='Path to JSON file (default: p2p_scrapes.json in project root)'
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        confirm = options['confirm']
        overwrite = options['overwrite']
        file_path = options['file']

        # Validate flags
        if not dry_run and not confirm:
            self._show_usage()
            return

        # Resolve file path
        if not os.path.isabs(file_path):
            file_path = os.path.join(settings.BASE_DIR, file_path)

        if not os.path.exists(file_path):
            raise CommandError(f'File not found: {file_path}')

        self.stdout.write(self.style.NOTICE(f'\nLoading data from: {file_path}'))

        # Load and parse JSON
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
        except json.JSONDecodeError as e:
            raise CommandError(f'Invalid JSON: {e}')

        total_records = len(data)
        self.stdout.write(f'Total JSON records: {total_records}')

        # Filter for Binance (platform_id=1) and USDT/BOB (pair_id=1)
        filtered_records = [
            r for r in data
            if r.get('platform_id') == 1 and r.get('pair_id') == 1
        ]
        filtered_count = len(filtered_records)
        
        self.stdout.write(f'Filtered records (Binance + USDT/BOB): {filtered_count}')

        if filtered_count == 0:
            self.stdout.write(self.style.WARNING('No valid records to import.'))
            return

        # Analyze time range
        timestamps = []
        for r in filtered_records:
            try:
                ts = dateutil_parser.parse(r['scrape_time'])
                timestamps.append(ts)
            except (KeyError, ValueError):
                pass

        if timestamps:
            timestamps.sort()
            self.stdout.write(self.style.SUCCESS(
                f'\nTime range to import:'
            ))
            self.stdout.write(f'  Start: {timestamps[0]}')
            self.stdout.write(f'  End:   {timestamps[-1]}')
            span_days = (timestamps[-1] - timestamps[0]).days
            self.stdout.write(f'  Span:  {span_days} days')

        # Check existing snapshots
        existing_p2p = MarketSnapshot.objects.filter(
            data_quality_score=P2P_SCRAPE_QUALITY_SCORE
        ).count()
        
        existing_ohlc = MarketSnapshot.objects.filter(
            data_quality_score__gte=EXTERNAL_OHLC_QUALITY_THRESHOLD
        ).count()

        self.stdout.write(self.style.NOTICE('\nCurrent database state:'))
        self.stdout.write(f'  Existing P2P scrape records: {existing_p2p}')
        self.stdout.write(f'  Existing OHLC records: {existing_ohlc}')

        if dry_run:
            self._dry_run_analysis(filtered_records)
            return

        # Execute import
        self._execute_import(filtered_records, overwrite)

    def _show_usage(self):
        """Show usage instructions."""
        self.stdout.write(self.style.ERROR('\n' + '=' * 60))
        self.stdout.write(self.style.ERROR('P2P Scrape Import Command'))
        self.stdout.write(self.style.ERROR('=' * 60))
        self.stdout.write('')
        self.stdout.write('This command imports historical P2P data from p2p_scrapes.json')
        self.stdout.write('into MarketSnapshot with quality score 0.8 (distinct from OHLC 0.95).')
        self.stdout.write('')
        self.stdout.write('Usage:')
        self.stdout.write(self.style.SUCCESS('  # Preview import (no changes)'))
        self.stdout.write('  python manage.py import_p2p_scrapes --dry-run')
        self.stdout.write('')
        self.stdout.write(self.style.SUCCESS('  # Execute import'))
        self.stdout.write('  python manage.py import_p2p_scrapes --confirm')
        self.stdout.write('')
        self.stdout.write(self.style.SUCCESS('  # Overwrite existing P2P records'))
        self.stdout.write('  python manage.py import_p2p_scrapes --confirm --overwrite')
        self.stdout.write('')

    def _dry_run_analysis(self, records):
        """Analyze what would be imported without making changes."""
        self.stdout.write(self.style.NOTICE('\n' + '=' * 60))
        self.stdout.write(self.style.NOTICE('DRY RUN - No database changes'))
        self.stdout.write(self.style.NOTICE('=' * 60))

        would_create = 0
        would_update = 0
        would_skip_ohlc = 0
        would_skip_existing = 0
        parse_errors = 0

        for record in records:
            snapshot_data = self._transform_record(record)
            if snapshot_data is None:
                parse_errors += 1
                continue

            timestamp = snapshot_data['timestamp']

            # Check for existing OHLC record
            ohlc_exists = MarketSnapshot.objects.filter(
                timestamp=timestamp,
                data_quality_score__gte=EXTERNAL_OHLC_QUALITY_THRESHOLD
            ).exists()

            if ohlc_exists:
                would_skip_ohlc += 1
                continue

            # Check for existing P2P record
            p2p_exists = MarketSnapshot.objects.filter(
                timestamp=timestamp,
                data_quality_score=P2P_SCRAPE_QUALITY_SCORE
            ).exists()

            if p2p_exists:
                would_skip_existing += 1
            else:
                would_create += 1

        self.stdout.write(self.style.SUCCESS('\nProjected results:'))
        self.stdout.write(f'  Records to create: {would_create}')
        self.stdout.write(f'  Records to skip (existing P2P): {would_skip_existing}')
        self.stdout.write(f'  Records to skip (OHLC exists): {would_skip_ohlc}')
        self.stdout.write(f'  Parse errors: {parse_errors}')
        self.stdout.write('')
        self.stdout.write(self.style.SUCCESS('✓ Dry run completed. No database changes made.'))
        self.stdout.write('')
        self.stdout.write('To execute the import, run:')
        self.stdout.write(self.style.NOTICE('  python manage.py import_p2p_scrapes --confirm'))

    def _execute_import(self, records, overwrite):
        """Execute the actual import."""
        self.stdout.write(self.style.NOTICE('\n' + '=' * 60))
        self.stdout.write(self.style.NOTICE('Executing P2P Scrape Import'))
        self.stdout.write(self.style.NOTICE('=' * 60))

        created_count = 0
        updated_count = 0
        skipped_ohlc = 0
        skipped_existing = 0
        error_count = 0

        total = len(records)
        batch_size = 500

        for idx, record in enumerate(records):
            try:
                snapshot_data = self._transform_record(record)
                if snapshot_data is None:
                    error_count += 1
                    continue

                timestamp = snapshot_data['timestamp']

                # CRITICAL: Never modify OHLC records
                ohlc_exists = MarketSnapshot.objects.filter(
                    timestamp=timestamp,
                    data_quality_score__gte=EXTERNAL_OHLC_QUALITY_THRESHOLD
                ).exists()

                if ohlc_exists:
                    skipped_ohlc += 1
                    continue

                # Check for existing P2P record
                existing_p2p = MarketSnapshot.objects.filter(
                    timestamp=timestamp,
                    data_quality_score=P2P_SCRAPE_QUALITY_SCORE
                ).first()

                if existing_p2p:
                    if overwrite:
                        # Update existing P2P record
                        for key, value in snapshot_data.items():
                            setattr(existing_p2p, key, value)
                        existing_p2p.save()
                        updated_count += 1
                    else:
                        skipped_existing += 1
                else:
                    # Create new record
                    MarketSnapshot.objects.create(**snapshot_data)
                    created_count += 1

                # Progress indicator
                if (idx + 1) % batch_size == 0:
                    self.stdout.write(
                        f'  Progress: {idx + 1}/{total} '
                        f'(created: {created_count}, updated: {updated_count})'
                    )

            except Exception as e:
                self.stdout.write(self.style.WARNING(f'Error processing record {idx}: {e}'))
                error_count += 1

        # Summary
        self.stdout.write('')
        self.stdout.write(self.style.SUCCESS('=' * 50))
        self.stdout.write(self.style.SUCCESS('Import Summary:'))
        self.stdout.write(f'  Records created: {created_count}')
        self.stdout.write(f'  Records updated: {updated_count}')
        self.stdout.write(f'  Skipped (existing P2P, no overwrite): {skipped_existing}')
        self.stdout.write(f'  Skipped (OHLC exists - protected): {skipped_ohlc}')
        self.stdout.write(f'  Errors: {error_count}')
        self.stdout.write(self.style.SUCCESS('=' * 50))

        # Verify final state
        p2p_count = MarketSnapshot.objects.filter(
            data_quality_score=P2P_SCRAPE_QUALITY_SCORE
        ).count()

        first_p2p = MarketSnapshot.objects.filter(
            data_quality_score=P2P_SCRAPE_QUALITY_SCORE
        ).order_by('timestamp').first()

        last_p2p = MarketSnapshot.objects.filter(
            data_quality_score=P2P_SCRAPE_QUALITY_SCORE
        ).order_by('timestamp').last()

        self.stdout.write('')
        self.stdout.write(self.style.SUCCESS('Final P2P scrape data state:'))
        self.stdout.write(f'  Total P2P records: {p2p_count}')
        if first_p2p and last_p2p:
            self.stdout.write(f'  Date range: {first_p2p.timestamp.date()} to {last_p2p.timestamp.date()}')
            span = (last_p2p.timestamp - first_p2p.timestamp).days
            self.stdout.write(f'  Span: {span} days')

        self.stdout.write('')
        self.stdout.write(self.style.SUCCESS('✅ Import completed successfully!'))

    def _transform_record(self, record):
        """
        Transform a P2P scrape JSON record into MarketSnapshot fields.

        Mapping:
        - timestamp ← scrape_time (datetime aware, UTC)
        - average_buy_price ← buy_average_price (Decimal)
        - average_sell_price ← sell_average_price (Decimal)
        - total_volume ← 0 (no volume data in P2P scrapes)
        - spread_percentage ← calculated from prices
        - num_active_traders ← 0 (not available)
        - data_quality_score ← 0.8 (P2P scrape marker)
        - raw_response ← structured metadata with original record

        Returns:
            dict of MarketSnapshot field values or None if invalid
        """
        try:
            # Parse timestamp
            scrape_time = record.get('scrape_time')
            if not scrape_time:
                return None

            timestamp = dateutil_parser.parse(scrape_time)

            # Parse prices
            buy_str = record.get('buy_average_price')
            sell_str = record.get('sell_average_price')

            if not buy_str or not sell_str:
                return None

            average_buy_price = Decimal(buy_str)
            average_sell_price = Decimal(sell_str)

            # Validate price range (5-15 BOB as per model validators)
            if not (Decimal('5.00') <= average_buy_price <= Decimal('15.00')):
                return None
            if not (Decimal('5.00') <= average_sell_price <= Decimal('15.00')):
                return None

            # Calculate spread percentage
            # spread = (sell - buy) / midpoint * 100
            midpoint = (average_sell_price + average_buy_price) / 2
            if midpoint > 0:
                spread_percentage = abs(
                    (average_sell_price - average_buy_price) / midpoint * 100
                )
            else:
                spread_percentage = Decimal('0')

            # Build raw_response with full provenance
            raw_response = {
                'source': P2P_SCRAPE_SOURCE,
                'platform_id': record.get('platform_id'),
                'pair_id': record.get('pair_id'),
                'page': record.get('page'),
                'metadata': record.get('metadata', {}),
                'original': {
                    'id': record.get('id'),
                    'scrape_time': scrape_time,
                    'buy_average_price': buy_str,
                    'sell_average_price': sell_str,
                }
            }

            return {
                'timestamp': timestamp,
                'average_buy_price': average_buy_price,
                'average_sell_price': average_sell_price,
                # No volume data in P2P scrapes - clearly documented
                'total_volume': Decimal('0.00'),
                'spread_percentage': spread_percentage,
                # No trader count available
                'num_active_traders': 0,
                # Quality score 0.8 distinguishes from OHLC (0.95)
                # This ensures elasticity calculations exclude P2P data
                'data_quality_score': P2P_SCRAPE_QUALITY_SCORE,
                'raw_response': raw_response,
            }

        except (InvalidOperation, ValueError, TypeError) as e:
            self.stdout.write(self.style.WARNING(
                f'Transform error: {e}'
            ))
            return None
