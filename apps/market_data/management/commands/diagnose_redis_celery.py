"""
Diagnostic command to verify Redis and Celery configuration.

Run in Railway shell: python manage.py diagnose_redis_celery
"""

import os
import time
from datetime import timedelta
from django.core.management.base import BaseCommand
from django.utils import timezone
from django.conf import settings


class Command(BaseCommand):
    help = 'Diagnose Redis and Celery configuration for Railway deployment'

    def add_arguments(self, parser):
        parser.add_argument(
            '--test-task',
            action='store_true',
            help='Also test running the scraper task',
        )

    def handle(self, *args, **options):
        self.stdout.write('=' * 70)
        self.stdout.write('DIAGNOSTICO REDIS & CELERY - Railway')
        self.stdout.write('=' * 70)
        self.stdout.write('')

        # 1. Check environment variables
        self._check_env_vars()

        # 2. Check Django settings
        self._check_django_settings()

        # 3. Test Redis connection
        self._test_redis_connection()

        # 4. Test Django cache
        self._test_django_cache()

        # 5. Test Celery broker connection
        self._test_celery_broker()

        # 6. Check Celery workers
        self._check_celery_workers()

        # 7. Check beat schedule
        self._check_beat_schedule()

        # 8. Check recent snapshots
        self._check_recent_snapshots()

        # 9. Optionally test the task
        if options['test_task']:
            self._test_scraper_task()

        self.stdout.write('')
        self.stdout.write('=' * 70)
        self.stdout.write('DIAGNOSTICO COMPLETO')
        self.stdout.write('=' * 70)

    def _check_env_vars(self):
        self.stdout.write('')
        self.stdout.write('1. VARIABLES DE ENTORNO')
        self.stdout.write('-' * 40)

        env_vars = [
            'REDIS_URL',
            'REDIS_HOST',
            'REDIS_PORT',
            'REDIS_USER',
            'REDIS_PASSWORD',
            'CELERY_BROKER_URL',
            'CELERY_RESULT_BACKEND',
            'DJANGO_CACHE_URL',
        ]

        for var in env_vars:
            value = os.environ.get(var, '')
            if value:
                # Mask password in display
                if 'PASSWORD' in var or ('URL' in var and '@' in value):
                    # Show masked version
                    if '@' in value:
                        parts = value.split('@')
                        masked = parts[0][:20] + '***@' + parts[-1]
                    else:
                        masked = value[:5] + '***'
                    self.stdout.write(f'  {var}: {masked}')
                else:
                    self.stdout.write(f'  {var}: {value}')
            else:
                self.stdout.write(self.style.WARNING(f'  {var}: (no definida)'))

    def _check_django_settings(self):
        self.stdout.write('')
        self.stdout.write('2. CONFIGURACION DJANGO')
        self.stdout.write('-' * 40)

        # Redis URL
        redis_url = getattr(settings, 'REDIS_URL', None)
        if redis_url:
            if '@' in redis_url:
                parts = redis_url.split('@')
                masked = parts[0][:20] + '***@' + parts[-1]
            else:
                masked = redis_url
            self.stdout.write(self.style.SUCCESS(f'  REDIS_URL: {masked}'))
        else:
            self.stdout.write(self.style.ERROR('  REDIS_URL: None (Redis NO configurado)'))

        # Celery broker
        broker = getattr(settings, 'CELERY_BROKER_URL', None)
        if broker:
            if '@' in broker:
                parts = broker.split('@')
                masked = parts[0][:20] + '***@' + parts[-1]
            else:
                masked = broker

            if broker.startswith('redis://'):
                self.stdout.write(self.style.SUCCESS(f'  CELERY_BROKER_URL: {masked}'))
            elif broker == 'django://':
                self.stdout.write(self.style.WARNING(f'  CELERY_BROKER_URL: {masked} (usando DB, no Redis)'))
            else:
                self.stdout.write(f'  CELERY_BROKER_URL: {masked}')
        else:
            self.stdout.write(self.style.ERROR('  CELERY_BROKER_URL: None'))

        # Result backend
        backend = getattr(settings, 'CELERY_RESULT_BACKEND', None)
        self.stdout.write(f'  CELERY_RESULT_BACKEND: {backend}')

        # Async mode
        async_enabled = getattr(settings, 'ELASTICITY_ASYNC_ENABLED', False)
        self.stdout.write(f'  ELASTICITY_ASYNC_ENABLED: {async_enabled}')

        # Cache backend
        cache_backend = settings.CACHES.get('default', {}).get('BACKEND', 'Unknown')
        cache_backend_short = cache_backend.split('.')[-1]
        if 'Redis' in cache_backend:
            self.stdout.write(self.style.SUCCESS(f'  Cache Backend: {cache_backend_short}'))
        else:
            self.stdout.write(self.style.WARNING(f'  Cache Backend: {cache_backend_short}'))

    def _test_redis_connection(self):
        self.stdout.write('')
        self.stdout.write('3. CONEXION DIRECTA A REDIS')
        self.stdout.write('-' * 40)

        redis_url = getattr(settings, 'REDIS_URL', None)
        if not redis_url:
            self.stdout.write(self.style.ERROR('  [SKIP] No hay REDIS_URL configurada'))
            return

        try:
            import redis
            start = time.time()
            r = redis.from_url(redis_url, socket_timeout=5, socket_connect_timeout=5)
            pong = r.ping()
            latency = (time.time() - start) * 1000

            if pong:
                self.stdout.write(self.style.SUCCESS(
                    f'  [OK] PING exitoso (latencia: {latency:.1f}ms)'
                ))

                # Test set/get
                test_key = 'diagnose:test:key'
                test_value = f'test_{timezone.now().isoformat()}'
                r.set(test_key, test_value, ex=60)
                retrieved = r.get(test_key)

                if retrieved and retrieved.decode() == test_value:
                    self.stdout.write(self.style.SUCCESS('  [OK] SET/GET funciona'))
                    r.delete(test_key)
                else:
                    self.stdout.write(self.style.ERROR('  [ERROR] SET/GET fallo'))

                # Check info
                info = r.info('clients')
                self.stdout.write(f'  Clientes conectados: {info.get("connected_clients", "?")}')

            else:
                self.stdout.write(self.style.ERROR('  [ERROR] PING fallo'))

        except Exception as e:
            self.stdout.write(self.style.ERROR(f'  [ERROR] {type(e).__name__}: {e}'))

    def _test_django_cache(self):
        self.stdout.write('')
        self.stdout.write('4. CACHE DE DJANGO')
        self.stdout.write('-' * 40)

        try:
            from django.core.cache import cache

            test_key = 'diagnose:cache:test'
            test_value = f'cached_{timezone.now().isoformat()}'

            cache.set(test_key, test_value, timeout=60)
            retrieved = cache.get(test_key)

            if retrieved == test_value:
                self.stdout.write(self.style.SUCCESS('  [OK] Cache SET/GET funciona'))
                cache.delete(test_key)
            else:
                self.stdout.write(self.style.ERROR(
                    f'  [ERROR] SET/GET fallo (esperado: {test_value}, obtenido: {retrieved})'
                ))

        except Exception as e:
            self.stdout.write(self.style.ERROR(f'  [ERROR] {type(e).__name__}: {e}'))

    def _test_celery_broker(self):
        self.stdout.write('')
        self.stdout.write('5. CONEXION A CELERY BROKER')
        self.stdout.write('-' * 40)

        try:
            from base.celery import app
            from kombu import Connection

            broker_url = app.conf.broker_url

            if broker_url == 'django://':
                self.stdout.write(self.style.WARNING(
                    '  [WARN] Usando django:// como broker (no Redis)'
                ))
                return

            start = time.time()
            with Connection(broker_url) as conn:
                conn.ensure_connection(max_retries=3, timeout=5)
                latency = (time.time() - start) * 1000
                self.stdout.write(self.style.SUCCESS(
                    f'  [OK] Conexion a broker exitosa (latencia: {latency:.1f}ms)'
                ))

        except Exception as e:
            self.stdout.write(self.style.ERROR(f'  [ERROR] {type(e).__name__}: {e}'))

    def _check_celery_workers(self):
        self.stdout.write('')
        self.stdout.write('6. WORKERS DE CELERY')
        self.stdout.write('-' * 40)

        try:
            from base.celery import app

            # Try to ping workers
            inspector = app.control.inspect(timeout=5)
            ping_result = inspector.ping()

            if ping_result:
                for worker_name, response in ping_result.items():
                    self.stdout.write(self.style.SUCCESS(f'  [OK] Worker activo: {worker_name}'))

                # Check active tasks
                active = inspector.active()
                if active:
                    for worker, tasks in active.items():
                        if tasks:
                            self.stdout.write(f'      Tareas activas: {len(tasks)}')
                        else:
                            self.stdout.write('      Sin tareas activas')
            else:
                self.stdout.write(self.style.ERROR(
                    '  [ERROR] No hay workers respondiendo'
                ))
                self.stdout.write(self.style.WARNING(
                    '  ACCION: Verificar que el proceso "worker" este corriendo en Railway'
                ))

        except Exception as e:
            self.stdout.write(self.style.ERROR(f'  [ERROR] {type(e).__name__}: {e}'))

    def _check_beat_schedule(self):
        self.stdout.write('')
        self.stdout.write('7. CELERY BEAT SCHEDULE')
        self.stdout.write('-' * 40)

        try:
            from base.celery import app

            schedule = app.conf.beat_schedule
            if schedule:
                for task_name, config in schedule.items():
                    task = config.get('task', 'unknown')
                    schedule_str = str(config.get('schedule', 'unknown'))
                    self.stdout.write(f'  - {task_name}')
                    self.stdout.write(f'    Task: {task}')
                    self.stdout.write(f'    Schedule: {schedule_str}')
            else:
                self.stdout.write(self.style.WARNING('  No hay tareas programadas'))

            # Check database scheduler
            try:
                from django_celery_beat.models import PeriodicTask
                db_tasks = PeriodicTask.objects.filter(enabled=True).count()
                self.stdout.write(f'  Tareas en DB (django-celery-beat): {db_tasks}')
            except Exception:
                pass

        except Exception as e:
            self.stdout.write(self.style.ERROR(f'  [ERROR] {e}'))

    def _check_recent_snapshots(self):
        self.stdout.write('')
        self.stdout.write('8. SNAPSHOTS RECIENTES')
        self.stdout.write('-' * 40)

        try:
            from apps.market_data.models import MarketSnapshot, DataCollectionLog

            now = timezone.now()

            # Last snapshot
            last_snap = MarketSnapshot.objects.order_by('-timestamp').first()
            if last_snap:
                age = now - last_snap.timestamp
                age_str = str(age).split('.')[0]  # Remove microseconds

                if age < timedelta(hours=1):
                    self.stdout.write(self.style.SUCCESS(
                        f'  [OK] Ultimo snapshot: hace {age_str}'
                    ))
                else:
                    self.stdout.write(self.style.ERROR(
                        f'  [WARN] Ultimo snapshot: hace {age_str}'
                    ))

                self.stdout.write(f'      Timestamp: {last_snap.timestamp}')
                self.stdout.write(f'      Precio: {last_snap.average_sell_price} BOB')
                self.stdout.write(f'      Calidad: {last_snap.data_quality_score}')
            else:
                self.stdout.write(self.style.ERROR('  [ERROR] No hay snapshots en la BD'))

            # Recent collection logs
            recent_logs = DataCollectionLog.objects.filter(
                timestamp__gte=now - timedelta(hours=24)
            ).order_by('-timestamp')[:5]

            if recent_logs:
                self.stdout.write('')
                self.stdout.write('  Ultimos logs de recoleccion (24h):')
                for log in recent_logs:
                    status_style = self.style.SUCCESS if log.status == 'SUCCESS' else self.style.ERROR
                    self.stdout.write(
                        f'    {log.timestamp.strftime("%Y-%m-%d %H:%M")} | '
                        f'{log.source} | '
                        f'{status_style(log.status)}'
                    )
                    if log.error_message:
                        self.stdout.write(f'      Error: {log.error_message[:100]}')
            else:
                self.stdout.write(self.style.WARNING(
                    '  No hay logs de recoleccion en las ultimas 24h'
                ))

        except Exception as e:
            self.stdout.write(self.style.ERROR(f'  [ERROR] {e}'))

    def _test_scraper_task(self):
        self.stdout.write('')
        self.stdout.write('9. TEST DE TAREA SCRAPER')
        self.stdout.write('-' * 40)

        try:
            from apps.market_data.tasks import fetch_binance_data

            # Test synchronous execution
            self.stdout.write('  Ejecutando tarea de forma sincrona...')
            start = time.time()
            result = fetch_binance_data()
            elapsed = time.time() - start

            self.stdout.write(f'  Tiempo de ejecucion: {elapsed:.2f}s')
            self.stdout.write(f'  Resultado: {result}')

            if result.get('status') == 'success':
                self.stdout.write(self.style.SUCCESS('  [OK] Scraper funciona correctamente'))
            elif result.get('status') == 'skipped':
                self.stdout.write(self.style.WARNING(
                    f'  [SKIP] {result.get("reason")}'
                ))
            else:
                self.stdout.write(self.style.ERROR('  [ERROR] Resultado inesperado'))

        except Exception as e:
            self.stdout.write(self.style.ERROR(f'  [ERROR] {type(e).__name__}: {e}'))
