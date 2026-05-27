# config/urls.py
from django.contrib import admin
from django.urls import path, include
from drf_spectacular.views import (
    SpectacularAPIView,
    SpectacularSwaggerView,
)

urlpatterns = [
    # Django admin panel
    path('admin/', admin.site.urls),

    # All REST API endpoints
    path('api/v1/', include('apps.api.urls')),

    # API Documentation (Swagger UI)
    path('api/schema/', SpectacularAPIView.as_view(), name='schema'),
    path('api/schema/swagger-ui/', SpectacularSwaggerView.as_view(
        url_name='schema'), name='swagger-ui'),
]