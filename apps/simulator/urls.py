from django.urls import path, include
from rest_framework.routers import DefaultRouter
from apps.simulator.viewsets import SimulatorViewSet

router = DefaultRouter()
router.register(r'', SimulatorViewSet, basename='simulator')

urlpatterns = [path('', include(router.urls))]
