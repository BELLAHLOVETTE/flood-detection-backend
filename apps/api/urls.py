# apps/api/urls.py
"""
All API URL routes.
Every URL here is prefixed with /api/v1/ from config/urls.py
"""
from django.urls import path
from rest_framework_simplejwt.views import (
    TokenObtainPairView,
    TokenRefreshView,
)
from . import views

urlpatterns = [

    # ── RISK ASSESSMENT ──────────────────────────────────────────────────────
    # Get current flood risk level and probability
    path(
        'risk/current/',
        views.current_risk,
        name='current-risk'
    ),
    # Get risk history for trend chart
    path(
        'risk/history/',
        views.risk_history,
        name='risk-history'
    ),

    # ── RAINFALL ─────────────────────────────────────────────────────────────
    # Get daily rainfall readings for chart
    path(
        'rainfall/',
        views.rainfall_series,
        name='rainfall-series'
    ),

    # ── WATER LEVEL ──────────────────────────────────────────────────────────
    # Get Lake Maga water level readings
    path(
        'water-level/',
        views.water_level_series,
        name='water-level-series'
    ),

    # ── FLOOD EVENTS ─────────────────────────────────────────────────────────
    # Get list of historical flood events
    path(
        'flood-events/',
        views.flood_events,
        name='flood-events'
    ),
    # Get single flood event details
    path(
        'flood-events/<uuid:event_id>/',
        views.flood_event_detail,
        name='flood-event-detail'
    ),

    # ── MAP DATA ─────────────────────────────────────────────────────────────
    # Get current flood extent as GeoJSON for Leaflet map
    path(
        'map/flood-extent/',
        views.flood_extent_geojson,
        name='flood-extent'
    ),

    # ── ALERT SUBSCRIPTION ───────────────────────────────────────────────────
    # Subscribe to flood alerts
    path(
        'alerts/subscribe/',
        views.subscribe_alerts,
        name='subscribe-alerts'
    ),
    # Verify OTP to confirm subscription
    path(
        'alerts/verify/',
        views.verify_otp,
        name='verify-otp'
    ),
    # Unsubscribe from alerts
    path(
        'alerts/unsubscribe/',
        views.unsubscribe_alerts,
        name='unsubscribe-alerts'
    ),
    # Get history of dispatched alerts
    path(
        'alerts/history/',
        views.alert_history,
        name='alert-history'
    ),
    # Get count of active subscribers (public stat)
    path(
        'alerts/count/',
        views.subscriber_count,
        name='subscriber-count'
    ),

    # ── ADMIN ENDPOINTS (authentication required) ─────────────────────────────
    # System health check
    path(
        'admin/health/',
        views.system_health,
        name='system-health'
    ),
    # Manually dispatch an alert
    path(
        'admin/alerts/dispatch/',
        views.manual_dispatch,
        name='manual-dispatch'
    ),

    # ── AUTHENTICATION ────────────────────────────────────────────────────────
    # Login — returns access + refresh JWT tokens
    path(
        'auth/token/',
        TokenObtainPairView.as_view(),
        name='token-obtain-pair'
    ),
    # Refresh the access token
    path(
        'auth/token/refresh/',
        TokenRefreshView.as_view(),
        name='token-refresh'
    ),

    # Forecast endpoints
    path('forecast/flood-risk/',  views.flood_risk_forecast,  name='forecast-flood-risk'),

    # Auth — register
    path('auth/register/',        views.register_authority,   name='register'),

    path('admin/subscribers/', views.admin_subscribers, name='admin-subscribers'),
    path('auth/password-reset/', views.password_reset_request, name='password-reset'),
    path('auth/password-reset-confirm/', views.password_reset_confirm, name='password-reset-confirm'),
]
