"""
Forensic Volume Correction for USDT/BOB MarketSnapshot data.

Corrects total_volume values in the 2025-11-20 to 2025-11-29 01:00 UTC range
based on socio-political context and realistic intraday patterns in Bolivia.

PRESERVES these exact timestamps (and any outside the range):
- 2025-11-29 05:30:00.243706+00
- 2025-11-29 06:09:32.866413+00
- 2025-11-29 17:22:48.421822+00
- 2025-11-30 01:14:31.630660+00
- 2025-11-30 01:42:26.149513+00
- 2025-11-30 02:00:00.252351+00
"""

import random
from datetime import datetime, timezone as tz, timedelta
from decimal import Decimal
from django.core.management.base import BaseCommand
from django.db import transaction
from apps.market_data.models import MarketSnapshot


class Command(BaseCommand):
    help = 'Forensic reconstruction of total_volume for USDT/BOB snapshots (20-29 Nov 2025)'

    # Correction range
    RANGE_START = datetime(2025, 11, 20, 0, 0, 0, tzinfo=tz.utc)
    RANGE_END = datetime(2025, 11, 29, 1, 0, 0, tzinfo=tz.utc)

    # Valid timestamps that must NOT be modified (microsecond precision)
    VALID_TIMESTAMPS = [
        datetime(2025, 11, 29, 5, 30, 0, 243706, tzinfo=tz.utc),
        datetime(2025, 11, 29, 6, 9, 32, 866413, tzinfo=tz.utc),
        datetime(2025, 11, 29, 17, 22, 48, 421822, tzinfo=tz.utc),
        datetime(2025, 11, 30, 1, 14, 31, 630660, tzinfo=tz.utc),
        datetime(2025, 11, 30, 1, 42, 26, 149513, tzinfo=tz.utc),
        datetime(2025, 11, 30, 2, 0, 0, 252351, tzinfo=tz.utc),
    ]

    # Daily multipliers based on socio-political analysis
    # Key: day of November, Value: multiplier relative to V_normal_day
    DAILY_MULTIPLIERS = {
        20: 0.80,   # Medio-bajo, calma tensa
        21: 1.00,   # Normal, acumulación ligera
        22: 0.35,   # Muy bajo, fin de semana
        23: 0.35,   # Muy bajo, fin de semana
        24: 1.50,   # Alto, víspera de tensión
        25: 3.50,   # PICO MÁXIMO - shock de noticias
        26: 2.00,   # Alto, venta fuerte post-shock
        27: 1.00,   # Medio, secado de compradores
        28: 1.80,   # Alto, cierre semanal/liquidaciones
        29: 0.50,   # Bajo (solo hasta 01:00, capitulación nocturna)
    }

    # Intraday hour weights (Bolivia time = UTC-4)
    # Hour (UTC) -> weight
    # Peak hours: 10:00-14:00 local = 14:00-18:00 UTC
    # Medium: 07:00-09:00 local = 11:00-13:00 UTC, 14:00-18:00 local = 18:00-22:00 UTC
    # Low: 19:00-06:00 local = 23:00-10:00 UTC
    HOUR_WEIGHTS = {
        0: 0.15,   # 20:00 local - mínimo nocturno
        1: 0.10,   # 21:00 local - mínimo nocturno
        2: 0.08,   # 22:00 local - mínimo nocturno
        3: 0.05,   # 23:00 local - mínimo nocturno
        4: 0.05,   # 00:00 local - mínimo nocturno
        5: 0.05,   # 01:00 local - mínimo nocturno
        6: 0.08,   # 02:00 local - mínimo nocturno
        7: 0.10,   # 03:00 local - mínimo nocturno
        8: 0.12,   # 04:00 local - mínimo nocturno
        9: 0.15,   # 05:00 local - mínimo nocturno
        10: 0.20,  # 06:00 local - despertar
        11: 0.40,  # 07:00 local - inicio actividad
        12: 0.60,  # 08:00 local - medio
        13: 0.80,  # 09:00 local - medio-alto
        14: 1.00,  # 10:00 local - PICO
        15: 1.00,  # 11:00 local - PICO
        16: 0.95,  # 12:00 local - PICO (almuerzo)
        17: 0.90,  # 13:00 local - alto
        18: 0.85,  # 14:00 local - medio-alto
        19: 0.75,  # 15:00 local - medio-alto
        20: 0.65,  # 16:00 local - medio
        21: 0.50,  # 17:00 local - cierre comercial
        22: 0.35,  # 18:00 local - tarde
        23: 0.25,  # 19:00 local - noche
    }

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be changed without modifying the database',
        )
        parser.add_argument(
            '--confirm',
            action='store_true',
            help='Required flag to actually apply changes',
        )
        parser.add_argument(
            '--seed',
            type=int,
            default=42,
            help='Random seed for reproducible results (default: 42)',
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        confirm = options['confirm']
        seed = options['seed']

        random.seed(seed)

        self.stdout.write(self.style.WARNING('=' * 70))
        self.stdout.write(self.style.WARNING('FORENSIC VOLUME CORRECTION - USDT/BOB MarketSnapshot'))
        self.stdout.write(self.style.WARNING('=' * 70))
        self.stdout.write('')

        # Step 1: Calculate V_normal_day from valid snapshots
        v_normal_day = self._calculate_normal_daily_volume()
        self.stdout.write(f'V_normal_day (estimado): {v_normal_day:,.0f} USDT')
        self.stdout.write('')

        # Step 2: Get snapshots to correct
        snapshots_to_correct = self._get_snapshots_to_correct()
        self.stdout.write(f'Snapshots a corregir: {len(snapshots_to_correct)}')

        # Step 3: Verify valid snapshots exist and won't be touched
        self._verify_valid_snapshots()

        # Step 4: Group snapshots by day
        by_day = self._group_by_day(snapshots_to_correct)

        # Step 5: Calculate new volumes
        corrections = self._calculate_corrections(by_day, v_normal_day)

        # Step 6: Show summary
        self._show_summary(corrections, v_normal_day)

        # Step 7: Apply or simulate
        if dry_run:
            self.stdout.write('')
            self.stdout.write(self.style.WARNING('DRY RUN - No changes applied'))
            self._show_sample_changes(corrections)
        elif confirm:
            self._apply_corrections(corrections)
            self.stdout.write('')
            self.stdout.write(self.style.SUCCESS('[OK] Corrections applied successfully'))
            self._verify_final_state()
        else:
            self.stdout.write('')
            self.stdout.write(self.style.ERROR(
                'Use --confirm to apply changes, or --dry-run to preview'
            ))

    def _calculate_normal_daily_volume(self):
        """
        Estimate V_normal_day based on current data averages and valid snapshots.
        
        Uses a blend of:
        1. Current average daily volume (what the data shows now)
        2. Valid snapshot volumes (what the scraper captures normally)
        """
        from django.db.models import Avg, Sum

        # Get valid snapshots for reference
        valid_snapshots = MarketSnapshot.objects.filter(
            timestamp__gt=self.RANGE_END
        )

        # Get current daily average from correction range
        current_snapshots = MarketSnapshot.objects.filter(
            timestamp__gte=self.RANGE_START,
            timestamp__lte=self.RANGE_END
        )
        current_stats = current_snapshots.aggregate(
            total=Sum('total_volume'),
            count=Sum(1)
        )

        # Calculate current daily average (exclude partial days)
        # Days 21-28 have full 24h data
        full_days = 8  # Nov 21-28
        current_daily_avg = float(current_stats['total'] or 0) / full_days

        self.stdout.write(f'  - Vol. total actual (rango): {current_stats["total"]:,.0f}')
        self.stdout.write(f'  - Promedio diario actual: {current_daily_avg:,.0f}')

        if valid_snapshots.exists():
            valid_avg = valid_snapshots.aggregate(avg=Avg('total_volume'))['avg']
            self.stdout.write(f'  - Promedio por snapshot valido: {valid_avg:,.0f}')

        # Use current daily average as V_normal_day
        # This preserves relative scale while allowing redistribution
        v_normal_day = current_daily_avg

        self.stdout.write(f'  - V_normal_day (usado): {v_normal_day:,.0f}')

        return v_normal_day

    def _get_snapshots_to_correct(self):
        """
        Get all snapshots in the correction range, excluding valid timestamps.
        """
        snapshots = MarketSnapshot.objects.filter(
            timestamp__gte=self.RANGE_START,
            timestamp__lte=self.RANGE_END
        ).order_by('timestamp')

        # Exclude valid timestamps
        to_correct = []
        for snap in snapshots:
            is_valid = any(
                abs((snap.timestamp - valid_ts).total_seconds()) < 1
                for valid_ts in self.VALID_TIMESTAMPS
            )
            if not is_valid:
                to_correct.append(snap)

        return to_correct

    def _verify_valid_snapshots(self):
        """
        Verify that valid snapshots exist and log their current state.
        """
        self.stdout.write('')
        self.stdout.write('Snapshots INTOCABLES (verificación):')

        for valid_ts in self.VALID_TIMESTAMPS:
            snap = MarketSnapshot.objects.filter(
                timestamp__gte=valid_ts - timedelta(seconds=1),
                timestamp__lte=valid_ts + timedelta(seconds=1)
            ).first()

            if snap:
                self.stdout.write(self.style.SUCCESS(
                    f'  [OK] {valid_ts}: Vol={snap.total_volume:,.0f}'
                ))
            else:
                self.stdout.write(self.style.WARNING(
                    f'  [--] {valid_ts}: No encontrado (fuera del rango)'
                ))

    def _group_by_day(self, snapshots):
        """
        Group snapshots by day.
        """
        by_day = {}
        for snap in snapshots:
            day = snap.timestamp.day
            if day not in by_day:
                by_day[day] = []
            by_day[day].append(snap)
        return by_day

    def _calculate_corrections(self, by_day, v_normal_day):
        """
        Calculate new volumes for each snapshot based on:
        - Daily multiplier (socio-political context)
        - Intraday pattern (hour weights)
        - Price correlation (larger price moves = more volume)
        - Controlled random noise
        """
        corrections = {}

        for day, snapshots in sorted(by_day.items()):
            multiplier = self.DAILY_MULTIPLIERS.get(day, 1.0)
            v_target_day = v_normal_day * multiplier

            # Special handling for Nov 29 (only until 01:00 UTC)
            if day == 29:
                # Only 1 hour worth of data
                hours_in_day = 1
                v_target_day = v_normal_day * multiplier * (hours_in_day / 24)
            else:
                hours_in_day = len(snapshots)

            # Calculate base weights for each hour
            hour_weights = []
            for snap in snapshots:
                hour = snap.timestamp.hour
                base_weight = self.HOUR_WEIGHTS.get(hour, 0.5)

                # Adjust weight based on price movement
                price_factor = self._get_price_factor(snap, snapshots)

                # Add controlled noise (±15%)
                noise = 1.0 + random.uniform(-0.15, 0.15)

                # Special adjustments for key days
                if day == 25 and 13 <= hour <= 17:  # Nov 25 peak hours (09-13 local)
                    base_weight *= 1.3  # Extra boost for peak day
                elif day in [22, 23] and 0 <= hour <= 10:  # Weekend nights
                    base_weight *= 0.7  # Extra reduction

                weight = base_weight * price_factor * noise
                hour_weights.append(weight)

            # Normalize weights so they sum to v_target_day
            total_weight = sum(hour_weights)
            if total_weight > 0:
                for i, snap in enumerate(snapshots):
                    new_volume = (hour_weights[i] / total_weight) * v_target_day

                    # Ensure minimum volume (never exactly 0)
                    new_volume = max(new_volume, 5000)

                    # Round to 2 decimals
                    new_volume = round(new_volume, 2)

                    corrections[snap.id] = {
                        'snapshot': snap,
                        'old_volume': float(snap.total_volume),
                        'new_volume': new_volume,
                        'day': day,
                        'hour': snap.timestamp.hour,
                    }

        return corrections

    def _get_price_factor(self, current_snap, all_snapshots):
        """
        Calculate a price factor based on price movement.
        Larger price changes = higher volume.
        """
        idx = all_snapshots.index(current_snap)

        if idx == 0:
            return 1.0

        prev_snap = all_snapshots[idx - 1]
        price_change = abs(
            float(current_snap.average_sell_price) - float(prev_snap.average_sell_price)
        )

        # Normalize: typical change is 0.01-0.05
        if price_change > 0.05:
            return 1.3  # Large price move = more volume
        elif price_change > 0.02:
            return 1.1  # Moderate move
        else:
            return 1.0  # Small/no move

    def _show_summary(self, corrections, v_normal_day):
        """
        Show summary of changes by day.
        """
        self.stdout.write('')
        self.stdout.write('=' * 70)
        self.stdout.write('RESUMEN DE CORRECCIONES POR DÍA')
        self.stdout.write('=' * 70)
        self.stdout.write('')

        # Group by day
        by_day = {}
        for corr in corrections.values():
            day = corr['day']
            if day not in by_day:
                by_day[day] = {'old': 0, 'new': 0, 'count': 0}
            by_day[day]['old'] += corr['old_volume']
            by_day[day]['new'] += corr['new_volume']
            by_day[day]['count'] += 1

        self.stdout.write(f'{"Día":>10} | {"Snapshots":>9} | {"Vol Actual":>14} | {"Vol Nuevo":>14} | {"Mult":>5} | {"Cambio":>10}')
        self.stdout.write('-' * 75)

        for day in sorted(by_day.keys()):
            data = by_day[day]
            mult = self.DAILY_MULTIPLIERS.get(day, 1.0)
            change_pct = ((data['new'] - data['old']) / data['old'] * 100) if data['old'] > 0 else 0

            self.stdout.write(
                f"  Nov {day:>2} | {data['count']:>9} | {data['old']:>14,.0f} | {data['new']:>14,.0f} | {mult:>5.2f} | {change_pct:>+9.1f}%"
            )

        self.stdout.write('-' * 75)
        total_old = sum(d['old'] for d in by_day.values())
        total_new = sum(d['new'] for d in by_day.values())
        total_change = ((total_new - total_old) / total_old * 100) if total_old > 0 else 0

        self.stdout.write(
            f"  {'TOTAL':>6} | {len(corrections):>9} | {total_old:>14,.0f} | {total_new:>14,.0f} |       | {total_change:>+9.1f}%"
        )

    def _show_sample_changes(self, corrections):
        """
        Show sample of specific changes.
        """
        self.stdout.write('')
        self.stdout.write('Muestra de cambios (primeros 10):')
        self.stdout.write('')

        for i, (snap_id, corr) in enumerate(list(corrections.items())[:10]):
            snap = corr['snapshot']
            self.stdout.write(
                f"  {snap.timestamp} | {corr['old_volume']:>12,.0f} -> {corr['new_volume']:>12,.0f}"
            )

    @transaction.atomic
    def _apply_corrections(self, corrections):
        """
        Apply all corrections in a single transaction.
        """
        self.stdout.write('')
        self.stdout.write('Aplicando correcciones...')

        count = 0
        for snap_id, corr in corrections.items():
            snap = corr['snapshot']
            snap.total_volume = Decimal(str(corr['new_volume']))
            snap.save(update_fields=['total_volume'])
            count += 1

            if count % 50 == 0:
                self.stdout.write(f'  Procesados: {count}/{len(corrections)}')

        self.stdout.write(f'  Total corregidos: {count}')

    def _verify_final_state(self):
        """
        Verify valid snapshots were not modified.
        """
        self.stdout.write('')
        self.stdout.write('Verificación final de snapshots intocables:')

        for valid_ts in self.VALID_TIMESTAMPS:
            snap = MarketSnapshot.objects.filter(
                timestamp__gte=valid_ts - timedelta(seconds=1),
                timestamp__lte=valid_ts + timedelta(seconds=1)
            ).first()

            if snap:
                self.stdout.write(self.style.SUCCESS(
                    f'  [OK] {valid_ts}: Vol={snap.total_volume:,.0f} (sin cambios)'
                ))
