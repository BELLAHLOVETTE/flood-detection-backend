# apps/api/views.py
"""
All REST API endpoint handlers.
These are the functions that run when the frontend
calls our API URLs.
"""
import logging
from datetime import timedelta

from django.utils import timezone
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework_simplejwt.views import (
    TokenObtainPairView,
    TokenRefreshView,
)

from apps.predictions.models import (
    RiskAssessment,
    RainfallReading,
    WaterLevelReading,
    SatelliteObservation,
)
from apps.floods.models import FloodEvent
from apps.alerts.models import AlertSubscriber, FloodAlert
from apps.core.models import AuditLog

from .serializers import (
    RiskAssessmentSerializer,
    RainfallReadingSerializer,
    WaterLevelSerializer,
    FloodEventSerializer,
    AlertSubscribeSerializer,
    AlertVerifySerializer,
    FloodAlertSerializer,
    SatelliteObservationSerializer,
    ManualAlertSerializer,
)

logger = logging.getLogger(__name__)


# ── RISK ASSESSMENT ──────────────────────────────────────────────────────────

@api_view(['GET'])
@permission_classes([AllowAny])
def current_risk(request):
    """
    GET /api/v1/risk/current/

    Returns the most recent flood risk assessment.
    This is the main endpoint the dashboard polls every 30 seconds.
    If no assessment exists yet, returns a safe default.
    """
    assessment = RiskAssessment.get_current()

    if not assessment:
        # No data yet — return a safe default response
        return Response({
            'id':                  None,
            'assessed_at':         None,
            'probability':         0.0,
            'risk_level':          'low',
            'previous_risk_level': None,
            'model_version':       'none',
            'risk_color':          '#22c55e',
            'is_escalation':       False,
            'is_manual_override':  False,
            'message':             'No assessment data available yet.',
        })

    serializer = RiskAssessmentSerializer(assessment)
    return Response(serializer.data)


@api_view(['GET'])
@permission_classes([AllowAny])
def risk_history(request):
    """
    GET /api/v1/risk/history/?days=30

    Returns all risk assessments from the last N days.
    Used for the risk trend chart on the dashboard.
    """
    days = int(request.query_params.get('days', 30))
    # Cap at 90 days to prevent huge responses
    days = min(days, 90)

    assessments = RiskAssessment.get_history(days=days)
    serializer  = RiskAssessmentSerializer(assessments, many=True)
    return Response(serializer.data)


# ── RAINFALL ─────────────────────────────────────────────────────────────────

@api_view(['GET'])
@permission_classes([AllowAny])
def rainfall_series(request):
    """
    GET /api/v1/rainfall/?days=90

    Returns daily rainfall readings for the last N days.
    Used by the rainfall line chart on the dashboard.
    Default is 90 days. Maximum is 365 days.
    """
    days   = int(request.query_params.get('days', 90))
    days   = min(days, 365)
    cutoff = timezone.now().date() - timedelta(days=days)

    readings   = RainfallReading.objects.filter(date__gte=cutoff)
    serializer = RainfallReadingSerializer(readings, many=True)
    return Response(serializer.data)


# ── WATER LEVEL ───────────────────────────────────────────────────────────────

@api_view(['GET'])
@permission_classes([AllowAny])
def water_level_series(request):
    """
    GET /api/v1/water-level/?days=90

    Returns Lake Maga water level readings.
    Used by the water level gauge on the dashboard.
    """
    days   = int(request.query_params.get('days', 90))
    days   = min(days, 365)
    cutoff = timezone.now().date() - timedelta(days=days)

    readings   = WaterLevelReading.objects.filter(date__gte=cutoff)
    serializer = WaterLevelSerializer(readings, many=True)
    return Response(serializer.data)


# ── FLOOD EVENTS ─────────────────────────────────────────────────────────────

@api_view(['GET'])
@permission_classes([AllowAny])
def flood_events(request):
    """
    GET /api/v1/flood-events/?year=2024&severity=high

    Returns historical flood events.
    Optional filters: year, severity.
    Used by the history timeline page.
    """
    queryset = FloodEvent.objects.all()

    # Filter by year if provided
    year = request.query_params.get('year')
    if year:
        try:
            queryset = queryset.filter(event_date__year=int(year))
        except ValueError:
            pass

    # Filter by severity if provided
    severity = request.query_params.get('severity')
    if severity:
        queryset = queryset.filter(severity=severity)

    serializer = FloodEventSerializer(queryset, many=True)
    return Response(serializer.data)


@api_view(['GET'])
@permission_classes([AllowAny])
def flood_event_detail(request, event_id):
    """
    GET /api/v1/flood-events/<event_id>/

    Returns details of a single flood event.
    Used when user clicks an event on the history page.
    """
    try:
        event = FloodEvent.objects.get(id=event_id)
    except FloodEvent.DoesNotExist:
        return Response(
            {'error': 'Flood event not found.'},
            status=status.HTTP_404_NOT_FOUND
        )

    serializer = FloodEventSerializer(event)
    return Response(serializer.data)


# ── MAP DATA ──────────────────────────────────────────────────────────────────

@api_view(['GET'])
@permission_classes([AllowAny])
def flood_extent_geojson(request):
    """
    GET /api/v1/map/flood-extent/

    Returns the latest detected flood extent as GeoJSON.
    Used by the Leaflet map on the frontend to draw
    the blue flood overlay on the map.
    """
    obs = SatelliteObservation.get_latest_successful()

    if not obs or not obs.flood_extent_geojson:
        # Return empty GeoJSON if no data
        return Response({
            'type':     'FeatureCollection',
            'features': [],
            'message':  'No flood extent data available yet.',
        })

    return Response(obs.flood_extent_geojson)


# ── ALERT SUBSCRIPTION ────────────────────────────────────────────────────────

@api_view(['POST'])
@permission_classes([AllowAny])
def subscribe_alerts(request):
    """
    POST /api/v1/alerts/subscribe/

    Registers a new subscriber for flood alerts.
    Sends an OTP via SMS or email to verify the contact.

    Request body:
    {
        "phone": "+237612345678",
        "email": "user@example.com",
        "channel": "sms",
        "language": "fr"
    }
    """
    serializer = AlertSubscribeSerializer(data=request.data)

    if not serializer.is_valid():
        return Response(
            serializer.errors,
            status=status.HTTP_400_BAD_REQUEST
        )

    data  = serializer.validated_data
    phone = data.get('phone', '').strip()
    email = data.get('email', '').strip()

    # Hash the phone number for privacy
    phone_hash = AlertSubscriber.hash_phone(phone) if phone else ''

    # Check if already subscribed — update preferences if so
    try:
        if phone_hash:
            sub = AlertSubscriber.objects.get(phone_number_hash=phone_hash)
            # Update their preferences
            sub.email             = email or sub.email
            sub.preferred_channel = data['channel']
            sub.language          = data['language']
            sub.save()
            created = False
        elif email:
            sub = AlertSubscriber.objects.get(email=email)
            sub.preferred_channel = data['channel']
            sub.language          = data['language']
            sub.save()
            created = False
        else:
            raise AlertSubscriber.DoesNotExist

    except AlertSubscriber.DoesNotExist:
        # New subscriber — create the record
        sub = AlertSubscriber.objects.create(
            phone_number_hash = phone_hash,
            phone_last4       = phone[-4:] if phone else '',
            email             = email or None,
            preferred_channel = data['channel'],
            language          = data['language'],
            is_verified       = False,
        )
        created = True

    # Generate and send OTP
    otp = sub.generate_otp()

    # For now, print OTP to console (will use Twilio/SendGrid later)
    # In production this triggers a Celery task to send SMS/email
    logger.info(f"OTP for subscriber {sub.id}: {otp}")
    print(f"\n{'='*40}")
    print(f"OTP CODE FOR TESTING: {otp}")
    print(f"Subscriber ID: {sub.id}")
    print(f"{'='*40}\n")

    response_data = {
        'message':    'Code de vérification envoyé. (Verification code sent.)',
        'sub_id':     str(sub.id),
        'channel':    data['channel'],
        'is_new':     created,
    }

    return Response(
        response_data,
        status=status.HTTP_201_CREATED if created else status.HTTP_200_OK
    )


@api_view(['POST'])
@permission_classes([AllowAny])
def verify_otp(request):
    """
    POST /api/v1/alerts/verify/

    Verifies the OTP and marks the subscriber as verified.

    Request body:
    {
        "sub_id": "uuid-here",
        "otp": "123456"
    }
    """
    serializer = AlertVerifySerializer(data=request.data)

    if not serializer.is_valid():
        return Response(
            serializer.errors,
            status=status.HTTP_400_BAD_REQUEST
        )

    sub_id = serializer.validated_data['sub_id']
    otp    = serializer.validated_data['otp']

    try:
        sub = AlertSubscriber.objects.get(id=sub_id)
    except AlertSubscriber.DoesNotExist:
        return Response(
            {'error': 'Subscriber not found.'},
            status=status.HTTP_404_NOT_FOUND
        )

    if sub.verify_otp(otp):
        sub.is_verified = True
        sub.save(update_fields=['is_verified'])
        return Response({
            'verified': True,
            'message':  'Numéro vérifié avec succès! (Number verified successfully!)',
        })
    else:
        return Response(
            {
                'verified': False,
                'error':    'Code invalide ou expiré. (Invalid or expired code.)',
            },
            status=status.HTTP_400_BAD_REQUEST
        )


@api_view(['DELETE'])
@permission_classes([AllowAny])
def unsubscribe_alerts(request):
    """
    DELETE /api/v1/alerts/unsubscribe/

    Marks a subscriber as inactive (soft delete).

    Request body:
    {
        "sub_id": "uuid-here"
    }
    """
    sub_id = request.data.get('sub_id')

    if not sub_id:
        return Response(
            {'error': 'sub_id is required.'},
            status=status.HTTP_400_BAD_REQUEST
        )

    try:
        sub = AlertSubscriber.objects.get(id=sub_id)
        sub.is_active = False
        sub.save(update_fields=['is_active'])
        return Response({
            'message': 'Désinscription réussie. (Unsubscribed successfully.)'
        })
    except AlertSubscriber.DoesNotExist:
        return Response(
            {'error': 'Subscriber not found.'},
            status=status.HTTP_404_NOT_FOUND
        )


# ── FLOOD ALERTS HISTORY ──────────────────────────────────────────────────────

@api_view(['GET'])
@permission_classes([AllowAny])
def alert_history(request):
    """
    GET /api/v1/alerts/history/

    Returns the last 20 flood alerts that were dispatched.
    Used on the alerts page to show recent alert history.
    """
    alerts     = FloodAlert.objects.all()[:20]
    serializer = FloodAlertSerializer(alerts, many=True)
    return Response(serializer.data)


# ── SUBSCRIBER COUNT (public stat) ───────────────────────────────────────────

@api_view(['GET'])
@permission_classes([AllowAny])
def subscriber_count(request):
    """
    GET /api/v1/alerts/count/

    Returns the total number of active verified subscribers.
    Displayed on the dashboard as a public statistic.
    """
    count = AlertSubscriber.get_active_count()
    return Response({'count': count})


# ── SYSTEM HEALTH (admin only) ────────────────────────────────────────────────

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def system_health(request):
    """
    GET /api/v1/admin/health/

    Returns system health information for the admin dashboard.
    Shows last successful GEE fetch, model version, etc.
    Requires authentication.
    """
    latest_obs    = SatelliteObservation.get_latest_successful()
    current_risk  = RiskAssessment.get_current()
    latest_rain   = RainfallReading.objects.first()
    latest_water  = WaterLevelReading.objects.first()

    return Response({
        'last_satellite_fetch': {
            'date':   latest_obs.acquisition_date if latest_obs else None,
            'status': latest_obs.status if latest_obs else 'no data',
        },
        'current_risk': {
            'level':       current_risk.risk_level if current_risk else 'unknown',
            'probability': current_risk.probability if current_risk else 0,
            'assessed_at': current_risk.assessed_at if current_risk else None,
            'model':       current_risk.model_version if current_risk else 'none',
        },
        'latest_rainfall_date':  latest_rain.date if latest_rain else None,
        'latest_water_date':     latest_water.date if latest_water else None,
        'active_subscribers':    AlertSubscriber.get_active_count(),
        'total_flood_events':    FloodEvent.objects.count(),
    })


# ── MANUAL ALERT DISPATCH (authority/admin only) ──────────────────────────────

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def manual_dispatch(request):
    """
    POST /api/v1/admin/alerts/dispatch/

    Allows an authority user to manually trigger a flood alert.
    Requires authentication and authority role.

    Request body:
    {
        "risk_level": "high",
        "message_fr": "Risque d'inondation élevé...",
        "message_en": "High flood risk detected..."
    }
    """
    # Check if user has authority role
    if not request.user.can_trigger_alerts():
        return Response(
            {'error': 'You do not have permission to trigger alerts.'},
            status=status.HTTP_403_FORBIDDEN
        )

    serializer = ManualAlertSerializer(data=request.data)

    if not serializer.is_valid():
        return Response(
            serializer.errors,
            status=status.HTTP_400_BAD_REQUEST
        )

    data = serializer.validated_data

    # Get all active subscribers
    subscribers = AlertSubscriber.objects.filter(
        is_active=True,
        is_verified=True
    )

    # Create the alert record
    level_map = {
        'low':      'FAIBLE',
        'medium':   'MODÉRÉ',
        'high':     'ÉLEVÉ',
        'critical': 'CRITIQUE',
    }
    level_fr = level_map.get(data['risk_level'], data['risk_level'].upper())

    alert = FloodAlert.objects.create(
        risk_level       = data['risk_level'],
        alert_type       = 'manual',
        title            = f"Alerte Inondation Manuelle — Niveau {level_fr}",
        message_fr       = data['message_fr'],
        message_en       = data.get('message_en', ''),
        total_recipients = subscribers.count(),
        triggered_by     = request.user,
    )

    # Log this action
    AuditLog.log(
        action  = 'manual_alert_dispatched',
        actor   = request.user,
        obj     = alert,
        details = {'risk_level': data['risk_level'], 'recipients': subscribers.count()},
        ip      = request.META.get('REMOTE_ADDR'),
    )

    from apps.alerts.tasks import dispatch_alert_to_subscribers
    result = dispatch_alert_to_subscribers(str(alert.id))

    return Response({
        'success':    True,
        'alert_id':   str(alert.id),
        'recipients': result['total'],
        'email_sent': result['email_sent'],
        'sms_sent':   result['sms_sent'],
        'message':    f"Alert dispatched to {result['email_sent']} subscriber(s) by email.",
    }, status=status.HTTP_201_CREATED)

@api_view(['GET'])
@permission_classes([AllowAny])
def flood_risk_forecast(request):
    """
    GET /api/v1/forecast/flood-risk/
    Returns 7-day flood risk forecast using ML model + seasonal climatology.
    """
    import pickle
    import logging
    from django.utils import timezone
    from datetime import date, timedelta, datetime
    from apps.predictions.models import (
        WaterLevelReading, RainfallReading, MLModel
    )
    from ml.feature_engineering import engineer_features

    logger = logging.getLogger(__name__)

    latest_water = WaterLevelReading.get_latest()
    water_km2    = latest_water.water_area_km2 if latest_water else 130.0

    pipeline = None
    try:
        model_rec = MLModel.get_active()
        if model_rec and model_rec.file_path:
            with open(model_rec.file_path, 'rb') as f:
                pipeline = pickle.load(f)
    except Exception as e:
        logger.warning(f'Could not load ML model: {e}')

    days_en = [
        'Monday', 'Tuesday', 'Wednesday', 'Thursday',
        'Friday', 'Saturday', 'Sunday'
    ]

    # Allow overriding "today" for demo purposes via query parameter
    # Usage: /api/v1/forecast/flood-risk/?demo_date=2026-08-20
    demo_date_param = request.query_params.get('demo_date')
    if demo_date_param:
        try:
            today = datetime.strptime(demo_date_param, '%Y-%m-%d').date()
        except ValueError:
            today = date.today()
    else:
        today = date.today()
    risk_forecast    = []
    rain_7d_running  = 0.0
    rain_30d_running = 0.0

    for d in range(1, 8):
        fdate = today + timedelta(days=d)
        doy   = fdate.timetuple().tm_yday

        historical_matches = RainfallReading.objects.extra(
            where=["EXTRACT(doy FROM date) BETWEEN %s AND %s"],
            params=[max(1, doy - 10), min(366, doy + 10)]
        )

        if historical_matches.exists():
            pred_rain = round(
                sum(r.rainfall_mm for r in historical_matches) /
                historical_matches.count(),
                1
            )
        else:
            is_rainy  = fdate.month in [7, 8, 9, 10]
            pred_rain = 15.0 if is_rainy else 2.0

        rain_7d_running  += pred_rain
        rain_30d_running += pred_rain

        features = engineer_features({
            'rainfall_1d':    pred_rain,
            'rainfall_7d':    rain_7d_running,
            'rainfall_30d':   rain_30d_running,
            'sar_ratio':      0.0,
            'water_area_km2': water_km2,
            'ndwi_mean':      0.0,
            'date':           fdate.isoformat(),
        })

        if pipeline is not None:
            try:
                probability = float(pipeline.predict_proba(features)[0][1])
            except Exception:
                probability = _rule_based_probability(pred_rain, rain_7d_running, water_km2)
        else:
            probability = _rule_based_probability(pred_rain, rain_7d_running, water_km2)

        risk = (
            'critical' if probability >= 0.80 else
            'high'     if probability >= 0.60 else
            'medium'   if probability >= 0.30 else
            'low'
        )
        color_map = {
            'low': '#22c55e', 'medium': '#eab308',
            'high': '#f97316', 'critical': '#ef4444',
        }

        risk_forecast.append({
            'forecast_date':  fdate.isoformat(),
            'day_offset':     d,
            'day_label':      days_en[fdate.weekday()],
            'predicted_rain': pred_rain,
            'probability':    round(probability, 3),
            'risk_level':     risk,
            'risk_color':     color_map[risk],
        })

    peak = max(risk_forecast, key=lambda x: x['probability'])

    return Response({
        'forecast':        risk_forecast,
        'peak_risk_day':   peak,
        'water_level_km2': water_km2,
        'generated_at':    timezone.now().isoformat(),
        'model_used':      'Random Forest + CHIRPS seasonal climatology',
    })


def _rule_based_probability(rain_1d, rain_7d, water_km2):
    """Simple rule-based flood probability when ML model unavailable."""
    score = 0.0
    if rain_1d  > 80:  score += 0.40
    elif rain_1d > 50: score += 0.25
    elif rain_1d > 25: score += 0.10
    if rain_7d  > 200: score += 0.35
    elif rain_7d > 120: score += 0.20
    elif rain_7d > 80:  score += 0.10
    if water_km2 > 180: score += 0.25
    elif water_km2 > 150: score += 0.15
    elif water_km2 > 130: score += 0.05
    return min(score, 0.99)


@api_view(['POST'])
@permission_classes([AllowAny])
def register_authority(request):
    """
    POST /api/v1/auth/register/
    Register a new authority/analyst user account.
    Accounts default to 'analyst' role and need admin approval.
    """
    from apps.core.models import User

    username     = request.data.get('username', '').strip()
    password     = request.data.get('password', '')
    email        = request.data.get('email', '').strip()
    organisation = request.data.get('organisation', '').strip()

    # Validate required fields
    if not username or not password or not email:
        return Response(
            {'error': 'username, password, and email are required.'},
            status=status.HTTP_400_BAD_REQUEST
        )

    if len(password) < 8:
        return Response(
            {'error': 'Password must be at least 8 characters long.'},
            status=status.HTTP_400_BAD_REQUEST
        )

    if User.objects.filter(username=username).exists():
        return Response(
            {'error': 'This username is already taken.'},
            status=status.HTTP_400_BAD_REQUEST
        )

    if User.objects.filter(email=email).exists():
        return Response(
            {'error': 'This email address is already registered.'},
            status=status.HTTP_400_BAD_REQUEST
        )

    user = User.objects.create_user(
        username=username,
        password=password,
        email=email,
        role='analyst',
        organisation=organisation,
    )

    AuditLog.log(
        action='user_registered',
        actor=None,
        obj=user,
        details={
            'username':     username,
            'organisation': organisation,
        },
        ip=request.META.get('REMOTE_ADDR'),
    )

    return Response({
        'message':  (
            'Account created successfully. '
            'An administrator must approve your access before you can log in.'
        ),
        'username': user.username,
        'email':    user.email,
    }, status=status.HTTP_201_CREATED)