"""
URL configuration for elasticity app.
"""
from django.urls import path, include
from rest_framework.routers import DefaultRouter
from apps.elasticity.viewsets import CalculationViewSet

router = DefaultRouter()
router.register(r'', CalculationViewSet, basename='elasticity')

urlpatterns = [
    path('', include(router.urls)),
]
