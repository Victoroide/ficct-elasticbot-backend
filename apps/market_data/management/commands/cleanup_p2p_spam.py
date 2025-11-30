"""
Management command to clean up P2P scraper spam records.

BACKGROUND:
Due to a misconfigured Celery Beat or multiple workers, the P2P scraper may have
created multiple snapshots within seconds/minutes of each other. This causes:
- Database bloat
- Erratic chart behavior (clustered/jagged lines)
- Inconsistent data presentation

SOLUTION:
This command identifies and removes P2P snapshots that are too close together,
keeping only one snapshot per time window (default: 15 minutes).

Usage:
    # Preview what would be deleted
    python manage.py cleanup_p2p_spam --dry-run

    # Execute cleanup
    python manage.py cleanup_p2p_spam --confirm

    # Custom interval (keep one per 30 minutes)
    python manage.py cleanup_p2p_spam --confirm --interval 30
"""
from datetime import timedelta

from django.core.management.base import BaseCommand
from django.db import transaction

from apps.market_data.models import MarketSnapshot


# Quality threshold - only clean P2P data, not OHLC
OHLC_QUALITY_THRESHOLD = 0.95


class Command(BaseCommand):
    help = 'Clean up P2P scraper spam records (keeps one per interval)'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Preview deletions without modifying database'
        )
        parser.add_argument(
            '--confirm',
            action='store_true',
            help='Execute the cleanup'
        )
        parser.add_argument(
            '--interval',
            type=int,
            default=15,
            help='Minimum minutes between snapshots to keep (default: 15)'
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        confirm = options['confirm']
        interval_minutes = options['interval']

        if not dry_run and not confirm:
            self._show_usage()
            return

        self.stdout.write(self.style.NOTICE(f'\nCleaning P2P spam with {interval_minutes}-minute interval'))

        # Get P2P records only (quality < 0.95)
        p2p_records = MarketSnapshot.objects.filter(
            data_quality_score__lt=OHLC_QUALITY_THRESHOLD
        ).order_by('timestamp')

        total_p2p = p2p_records.count()
        self.stdout.write(f'Total P2P records: {total_p2p}')

        if total_p2p == 0:
            self.stdout.write(self.style.WARNING('No P2P records found.'))
            return

        # Find spam records (too close to previous)
        spam_ids = []
        last_kept_timestamp = None
        interval = timedelta(minutes=interval_minutes)

        for record in p2p_records.iterator():
            if last_kept_timestamp is None:
                # Keep the first record
                last_kept_timestamp = record.timestamp
            else:
                time_since_last = record.timestamp - last_kept_timestamp
                if time_since_last < interval:
                    # This record is spam (too close to last kept)
                    spam_ids.append(record.id)
                else:
                    # Keep this record
                    last_kept_timestamp = record.timestamp

        spam_count = len(spam_ids)
        keep_count = total_p2p - spam_count

        self.stdout.write(f'  Spam records to delete: {spam_count}')
        self.stdout.write(f'  Records to keep: {keep_count}')

        if spam_count == 0:
            self.stdout.write(self.style.SUCCESS('\nNo spam records found. Database is clean.'))
            return

        if dry_run:
            self._dry_run_analysis(spam_ids, interval_minutes)
            return

        self._execute_cleanup(spam_ids)

    def _show_usage(self):
        """Show usage instructions."""
        self.stdout.write(self.style.ERROR('\n' + '=' * 60))
        self.stdout.write(self.style.ERROR('Cleanup P2P Spam Command'))
        self.stdout.write(self.style.ERROR('=' * 60))
        self.stdout.write('')
        self.stdout.write('This command removes P2P scraper spam records.')
        self.stdout.write('')
        self.stdout.write('What it does:')
        self.stdout.write('  1. Identifies P2P snapshots taken too close together')
        self.stdout.write('  2. Keeps one snapshot per interval (default: 15 minutes)')
        self.stdout.write('  3. Deletes redundant intermediate records')
        self.stdout.write('')
        self.stdout.write('Usage:')
        self.stdout.write(self.style.SUCCESS('  # Preview deletions'))
        self.stdout.write('  python manage.py cleanup_p2p_spam --dry-run')
        self.stdout.write('')
        self.stdout.write(self.style.SUCCESS('  # Execute cleanup'))
        self.stdout.write('  python manage.py cleanup_p2p_spam --confirm')
        self.stdout.write('')
        self.stdout.write(self.style.SUCCESS('  # Custom interval (30 minutes)'))
        self.stdout.write('  python manage.py cleanup_p2p_spam --confirm --interval 30')
        self.stdout.write('')

    def _dry_run_analysis(self, spam_ids, interval_minutes):
        """Preview what would be deleted."""
        self.stdout.write(self.style.NOTICE('\n' + '=' * 60))
        self.stdout.write(self.style.NOTICE('DRY RUN - No database changes'))
        self.stdout.write(self.style.NOTICE('=' * 60))

        # Show sample spam records
        sample_ids = spam_ids[:10]
        samples = MarketSnapshot.objects.filter(id__in=sample_ids).order_by('timestamp')

        self.stdout.write(f'\nSample spam records (showing first 10 of {len(spam_ids)}):')
        for record in samples:
            self.stdout.write(
                f'  ID {record.id}: {record.timestamp} - '
                f'Volume: {record.total_volume:,.2f}'
            )

        self.stdout.write('')
        self.stdout.write(self.style.SUCCESS('[OK] Dry run completed. No database changes made.'))
        self.stdout.write('')
        self.stdout.write(f'Would delete {len(spam_ids)} spam records.')
        self.stdout.write(f'Keeping one record per {interval_minutes} minutes.')
        self.stdout.write('')
        self.stdout.write('To execute the cleanup, run:')
        self.stdout.write(self.style.NOTICE('  python manage.py cleanup_p2p_spam --confirm'))

    def _execute_cleanup(self, spam_ids):
        """Execute the cleanup."""
        self.stdout.write(self.style.NOTICE('\n' + '=' * 60))
        self.stdout.write(self.style.NOTICE('Executing P2P Spam Cleanup'))
        self.stdout.write(self.style.NOTICE('=' * 60))

        # Delete in batches
        batch_size = 500
        deleted_total = 0

        with transaction.atomic():
            for i in range(0, len(spam_ids), batch_size):
                batch = spam_ids[i:i + batch_size]
                deleted_count, _ = MarketSnapshot.objects.filter(id__in=batch).delete()
                deleted_total += deleted_count
                self.stdout.write(f'  Deleted batch: {deleted_count} records')

        # Summary
        self.stdout.write('')
        self.stdout.write(self.style.SUCCESS('=' * 50))
        self.stdout.write(self.style.SUCCESS('Cleanup Summary:'))
        self.stdout.write(f'  Records deleted: {deleted_total}')
        self.stdout.write(self.style.SUCCESS('=' * 50))
        self.stdout.write('')
        self.stdout.write(self.style.SUCCESS('[DONE] P2P spam cleanup completed!'))
        self.stdout.write('')

        # Show remaining stats
        remaining = MarketSnapshot.objects.filter(
            data_quality_score__lt=OHLC_QUALITY_THRESHOLD
        ).count()
        self.stdout.write(f'Remaining P2P records: {remaining}')
