from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from django.http import JsonResponse
from drf_spectacular.views import (
    SpectacularAPIView,
    SpectacularSwaggerView,
    SpectacularRedocView,
)


def health_check(request):
    """Simple health check endpoint - no Redis, no DB, no auth."""
    return JsonResponse({
        'status': 'healthy',
        'service': 'elasticbot-api',
        'version': '2.0.0',
    })


def health_check_detailed(request):
    """
    Detailed health check including Redis, Cache, and Celery status.
    Use for monitoring dashboards, not for load balancer probes.
    """
    from utils.health import get_full_health_status
    
    status = get_full_health_status()
    http_status = 200 if status['healthy'] else 503
    
    return JsonResponse(status, status=http_status)


urlpatterns = [
    # Health checks
    path('health/', health_check, name='health-check'),  # Simple - for load balancer probes
    path('health/detailed/', health_check_detailed, name='health-check-detailed'),  # Full status

    path('admin/', admin.site.urls),

    # API Documentation (OpenAPI/Swagger)
    path('api/schema/', SpectacularAPIView.as_view(), name='schema'),
    path('api/docs/', SpectacularSwaggerView.as_view(url_name='schema'), name='swagger-ui'),
    path('api/redoc/', SpectacularRedocView.as_view(url_name='schema'), name='redoc'),

    # API endpoints (anonymous access - no authentication) - ALL 5 APPS
    path('api/v1/market-data/', include('apps.market_data.urls')),
    path('api/v1/elasticity/', include('apps.elasticity.urls')),
    path('api/v1/interpret/', include('apps.ai_interpretation.urls')),
    path('api/v1/simulator/', include('apps.simulator.urls')),
    path('api/v1/reports/', include('apps.reports.urls')),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)

admin.site.site_header = "ElasticBot Administration"
admin.site.site_title = "ElasticBot Admin Portal"
admin.site.index_title = "Welcome to ElasticBot Admin Portal"
