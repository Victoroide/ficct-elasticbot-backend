"""
URL configuration for market_data app.
"""
from django.urls import path, include
from rest_framework.routers import DefaultRouter
from apps.market_data.viewsets import SnapshotViewSet

router = DefaultRouter()
router.register(r'', SnapshotViewSet, basename='market-data')

urlpatterns = [
    path('', include(router.urls)),
]
