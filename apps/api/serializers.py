# apps/api/serializers.py
"""
Serializers convert Django model instances into JSON
and validate incoming data from the frontend.
"""
from rest_framework import serializers
from apps.predictions.models import (
    RiskAssessment,
    RainfallReading,
    WaterLevelReading,
    SatelliteObservation,
    MLModel,
)
from apps.floods.models import FloodEvent
from apps.alerts.models import AlertSubscriber, FloodAlert


# ── RISK ASSESSMENT ──────────────────────────────────────────────────────────

class RiskAssessmentSerializer(serializers.ModelSerializer):
    """
    Serializes the current flood risk assessment.
    Adds computed fields: risk_color and is_escalation.
    """
    risk_color    = serializers.SerializerMethodField()
    is_escalation = serializers.SerializerMethodField()

    class Meta:
        model  = RiskAssessment
        fields = [
            'id',
            'assessed_at',
            'probability',
            'risk_level',
            'previous_risk_level',
            'model_version',
            'risk_color',
            'is_escalation',
            'is_manual_override',
        ]

    def get_risk_color(self, obj):
        return obj.get_risk_color()

    def get_is_escalation(self, obj):
        return obj.is_escalation


# ── RAINFALL ─────────────────────────────────────────────────────────────────

class RainfallReadingSerializer(serializers.ModelSerializer):
    """
    Serializes daily rainfall readings for the chart
    on the frontend dashboard.
    """
    class Meta:
        model  = RainfallReading
        fields = [
            'date',
            'rainfall_mm',
            'cumulative_7d',
            'cumulative_30d',
            'source',
        ]


# ── WATER LEVEL ───────────────────────────────────────────────────────────────

class WaterLevelSerializer(serializers.ModelSerializer):
    """
    Serializes Lake Maga water level readings.
    Adds fill_percentage — how full the lake is vs baseline.
    """
    fill_percentage = serializers.SerializerMethodField()

    class Meta:
        model  = WaterLevelReading
        fields = [
            'date',
            'water_area_km2',
            'baseline_area_km2',
            'change_percent',
            'fill_percentage',
            'source',
        ]

    def get_fill_percentage(self, obj):
        return obj.get_fill_percentage()


# ── FLOOD EVENTS ─────────────────────────────────────────────────────────────

class FloodEventSerializer(serializers.ModelSerializer):
    """
    Serializes historical flood events for the
    timeline page on the frontend.
    """
    duration_days  = serializers.SerializerMethodField()
    severity_fr    = serializers.SerializerMethodField()

    class Meta:
        model  = FloodEvent
        fields = [
            'id',
            'event_date',
            'end_date',
            'severity',
            'severity_fr',
            'affected_area_km2',
            'affected_population',
            'description',
            'source',
            'is_confirmed',
            'duration_days',
        ]

    def get_duration_days(self, obj):
        return obj.get_duration_days()

    def get_severity_fr(self, obj):
        return obj.get_severity_display_fr()


# ── ALERT SUBSCRIPTION ────────────────────────────────────────────────────────

class AlertSubscribeSerializer(serializers.Serializer):
    """
    Validates the data when a user subscribes to alerts.
    They must provide at least a phone OR an email.
    """
    phone    = serializers.CharField(
                   max_length=20,
                   required=False,
                   allow_blank=True
               )
    email    = serializers.EmailField(
                   required=False,
                   allow_blank=True
               )
    channel  = serializers.ChoiceField(
                   choices=['sms', 'email', 'both'],
                   default='sms'
               )
    language = serializers.ChoiceField(
                   choices=['fr', 'en'],
                   default='fr'
               )

    def validate(self, data):
        """
        Make sure they gave us at least one contact method.
        """
        phone = data.get('phone', '').strip()
        email = data.get('email', '').strip()

        if not phone and not email:
            raise serializers.ValidationError(
                'Veuillez fournir un numéro de téléphone ou une adresse email. '
                '(Please provide a phone number or email address.)'
            )

        # If channel is SMS but no phone provided
        if data.get('channel') == 'sms' and not phone:
            raise serializers.ValidationError(
                'Un numéro de téléphone est requis pour les alertes SMS. '
                '(A phone number is required for SMS alerts.)'
            )

        # If channel is email but no email provided
        if data.get('channel') == 'email' and not email:
            raise serializers.ValidationError(
                'Une adresse email est requise pour les alertes email. '
                '(An email address is required for email alerts.)'
            )

        return data


class AlertVerifySerializer(serializers.Serializer):
    """
    Validates the OTP verification request.
    """
    sub_id = serializers.UUIDField()
    otp    = serializers.CharField(min_length=6, max_length=6)


# ── FLOOD ALERT (for displaying sent alerts) ──────────────────────────────────

class FloodAlertSerializer(serializers.ModelSerializer):
    """
    Serializes sent flood alerts for display
    on the alerts history page.
    """
    delivery_rate = serializers.SerializerMethodField()

    class Meta:
        model  = FloodAlert
        fields = [
            'id',
            'triggered_at',
            'risk_level',
            'alert_type',
            'title',
            'message_fr',
            'message_en',
            'total_recipients',
            'sms_sent',
            'email_sent',
            'is_all_clear',
            'delivery_rate',
        ]

    def get_delivery_rate(self, obj):
        return obj.get_delivery_rate()


# ── SATELLITE OBSERVATION ─────────────────────────────────────────────────────

class SatelliteObservationSerializer(serializers.ModelSerializer):
    """
    Serializes satellite observation records.
    Used by the admin dashboard to show system health.
    """
    flood_area_km2 = serializers.SerializerMethodField()

    class Meta:
        model  = SatelliteObservation
        fields = [
            'id',
            'acquisition_date',
            'satellite',
            'status',
            'flood_area_km2',
            'error_message',
            'created_at',
        ]

    def get_flood_area_km2(self, obj):
        return obj.get_flood_area_km2()


# ── MANUAL ALERT DISPATCH (admin only) ────────────────────────────────────────

class ManualAlertSerializer(serializers.Serializer):
    """
    Validates the data when an authority manually
    triggers an alert from the admin dashboard.
    """
    risk_level  = serializers.ChoiceField(
                      choices=['low', 'medium', 'high', 'critical']
                  )
    message_fr  = serializers.CharField(max_length=500)
    message_en  = serializers.CharField(max_length=500, required=False, allow_blank=True)

    class AdminSubscriberSerializer(serializers.ModelSerializer):
        masked_email = serializers.SerializerMethodField()
        phone_display = serializers.SerializerMethodField()

        class Meta:
            from apps.alerts.models import AlertSubscriber
            model = AlertSubscriber
            fields = [
                'id', 'masked_email', 'phone_display', 'preferred_channel',
                'language', 'is_verified', 'is_active', 'subscription_area',
                'last_alert_sent', 'created_at',
            ]

        def get_masked_email(self, obj):
            if not obj.email:
                return None
            local, _, domain = obj.email.partition('@')
            if len(local) <= 2:
                masked = local[0] + '*'
            else:
                masked = local[0] + '*' * (len(local) - 2) + local[-1]
            return f"{masked}@{domain}"

        def get_phone_display(self, obj):
            return f"•••• {obj.phone_last4}" if obj.phone_last4 else None