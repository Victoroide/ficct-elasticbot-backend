"""
One-time cleanup command to remove non-external API data from MarketSnapshot.

This command ensures that only high-quality data from the external OHLC API
remains in the database, providing a clean foundation for elasticity calculations.

Usage:
    python manage.py cleanup_market_data --dry-run   # Preview changes
    python manage.py cleanup_market_data --confirm   # Execute cleanup

IMPORTANT: This is a destructive operation. Run --dry-run first to verify.
"""
from django.core.management.base import BaseCommand
from django.db import transaction
from apps.market_data.models import MarketSnapshot


# Quality score marker for external API data
EXTERNAL_API_QUALITY_SCORE = 0.95


class Command(BaseCommand):
    help = 'Remove non-external API data from MarketSnapshot table (one-time cleanup)'

    def add_arguments(self, parser):
        parser.add_argument(
            '--confirm',
            action='store_true',
            help='REQUIRED: Confirm you want to delete non-external API data'
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Preview what would be deleted without making changes'
        )

    def handle(self, *args, **options):
        confirm = options['confirm']
        dry_run = options['dry_run']

        if not confirm and not dry_run:
            self.stdout.write(self.style.ERROR(
                '\n⚠️  This command deletes data from MarketSnapshot!'
            ))
            self.stdout.write('\nTo preview changes:')
            self.stdout.write(self.style.SUCCESS('  python manage.py cleanup_market_data --dry-run'))
            self.stdout.write('\nTo execute cleanup:')
            self.stdout.write(self.style.SUCCESS('  python manage.py cleanup_market_data --confirm'))
            return

        self.stdout.write(self.style.NOTICE('\n' + '=' * 60))
        self.stdout.write(self.style.NOTICE('MarketSnapshot Cleanup Analysis'))
        self.stdout.write(self.style.NOTICE('=' * 60))

        # Analyze current state
        total_records = MarketSnapshot.objects.count()
        self.stdout.write(f'\nTotal records: {total_records}')

        # Identify external API records
        external_records = []
        non_external_records = []

        for snap in MarketSnapshot.objects.all():
            is_external = (
                snap.raw_response
                and snap.raw_response.get('source') == 'external_ohlc_api'
            )
            if is_external:
                external_records.append(snap)
            else:
                non_external_records.append(snap)

        self.stdout.write('\n📊 Data Breakdown:')
        self.stdout.write(f'  ✓ External API records (keep): {len(external_records)}')
        self.stdout.write(f'  ✗ Other records (delete): {len(non_external_records)}')

        if non_external_records:
            self.stdout.write('\n🗑️  Records to delete:')
            for snap in non_external_records[:5]:
                source = snap.raw_response.get('source', 'unknown') if snap.raw_response else 'no raw_response'
                self.stdout.write(f'    - {snap.timestamp} (quality={snap.data_quality_score}, source={source})')
            if len(non_external_records) > 5:
                self.stdout.write(f'    ... and {len(non_external_records) - 5} more')

        if external_records:
            # Check for quality score inconsistencies
            non_standard_quality = [s for s in external_records if s.data_quality_score != EXTERNAL_API_QUALITY_SCORE]
            if non_standard_quality:
                self.stdout.write(f'\n⚠️  External records with non-standard quality score: {len(non_standard_quality)}')
                self.stdout.write(f'    Will be standardized to {EXTERNAL_API_QUALITY_SCORE}')

            # Show date range
            timestamps = [s.timestamp for s in external_records]
            self.stdout.write('\n📅 External data range:')
            self.stdout.write(f'    First: {min(timestamps)}')
            self.stdout.write(f'    Last:  {max(timestamps)}')

        if dry_run:
            self.stdout.write(self.style.WARNING('\n[DRY RUN] No changes made.'))
            return

        if not non_external_records and not non_standard_quality:
            self.stdout.write(self.style.SUCCESS('\n✅ Database already clean. No changes needed.'))
            return

        # Execute cleanup
        self.stdout.write(self.style.NOTICE('\n🔧 Executing cleanup...'))

        with transaction.atomic():
            # Delete non-external records
            if non_external_records:
                delete_ids = [s.id for s in non_external_records]
                deleted_count = MarketSnapshot.objects.filter(id__in=delete_ids).delete()[0]
                self.stdout.write(f'  Deleted {deleted_count} non-external records')

            # Standardize quality scores
            if non_standard_quality:
                update_ids = [s.id for s in non_standard_quality]
                updated_count = MarketSnapshot.objects.filter(id__in=update_ids).update(
                    data_quality_score=EXTERNAL_API_QUALITY_SCORE
                )
                self.stdout.write(f'  Standardized quality score for {updated_count} records')

        # Verify final state
        self.stdout.write(self.style.SUCCESS('\n' + '=' * 60))
        self.stdout.write(self.style.SUCCESS('Cleanup Complete - Final State'))
        self.stdout.write(self.style.SUCCESS('=' * 60))

        final_count = MarketSnapshot.objects.count()
        self.stdout.write(f'\nTotal records remaining: {final_count}')

        # Verify all records are from external API
        all_external = True
        all_correct_quality = True

        for snap in MarketSnapshot.objects.all():
            if not (snap.raw_response and snap.raw_response.get('source') == 'external_ohlc_api'):
                all_external = False
            if snap.data_quality_score != EXTERNAL_API_QUALITY_SCORE:
                all_correct_quality = False

        if all_external:
            self.stdout.write(self.style.SUCCESS('  ✓ All records from external OHLC API'))
        else:
            self.stdout.write(self.style.ERROR('  ✗ Some records not from external API!'))

        if all_correct_quality:
            self.stdout.write(self.style.SUCCESS(f'  ✓ All records have quality score {EXTERNAL_API_QUALITY_SCORE}'))
        else:
            self.stdout.write(self.style.ERROR('  ✗ Some records have incorrect quality score!'))

        # Show sample records
        self.stdout.write('\n📋 Sample records:')
        for snap in MarketSnapshot.objects.order_by('-timestamp')[:3]:
            self.stdout.write(
                f'    {snap.timestamp} | sell={snap.average_sell_price} | '
                f'quality={snap.data_quality_score} | source={snap.raw_response.get("source", "?")}'
            )
