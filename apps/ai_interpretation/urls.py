"""
URL configuration for AI interpretation app.
"""
from django.urls import path, include
from rest_framework.routers import DefaultRouter
from apps.ai_interpretation.viewsets import InterpretationViewSet

router = DefaultRouter()
router.register(r'', InterpretationViewSet, basename='interpret')

urlpatterns = [
    path('', include(router.urls)),
]
