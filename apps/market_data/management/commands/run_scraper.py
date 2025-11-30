"""
Management command to run Binance P2P scraper manually.
This provides a fallback solution when Celery is not working.
"""
from django.core.management.base import BaseCommand
from django.utils import timezone
from apps.market_data.tasks import fetch_binance_data
import logging

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Run Binance P2P scraper manually (fallback for Celery issues)'

    def add_arguments(self, parser):
        parser.add_argument(
            '--verbose',
            action='store_true',
            help='Enable verbose logging',
        )

    def handle(self, *args, **options):
        start_time = timezone.now()
        self.stdout.write(f'[{start_time}] Starting manual Binance P2P scraper...')

        if options['verbose']:
            self.stdout.write('Using direct task execution (bypassing Celery)')

        try:
            # Execute the scraper directly without Celery
            result = fetch_binance_data()

            if result.get('status') == 'success':
                self.stdout.write(
                    self.style.SUCCESS(
                        f"SUCCESS: Scraper completed successfully!\n"
                        f"  - Snapshot ID: {result.get('snapshot_id')}\n"
                        f"  - Price: {result.get('price')} BOB\n"
                        f"  - Volume: {result.get('volume')}\n"
                        f"  - Quality Score: {result.get('quality_score')}"
                    )
                )
            elif result.get('status') == 'skipped':
                reason = result.get('reason', 'unknown')
                self.stdout.write(
                    self.style.WARNING(
                        f"WARNING: Scraper skipped: {reason}\n"
                        f"  This is normal if another instance is running or "
                        f"if the last run was too recent."
                    )
                )
            else:
                self.stdout.write(
                    self.style.ERROR(
                        f"ERROR: Scraper failed with status: {result.get('status')}"
                    )
                )

        except Exception as e:
            self.stdout.write(
                self.style.ERROR(
                    f"ERROR: Scraper failed with exception: {e}"
                )
            )
            if options['verbose']:
                import traceback
                traceback.print_exc()

        execution_time = timezone.now() - start_time
        self.stdout.write(f'Execution completed in {execution_time.total_seconds():.2f} seconds')
