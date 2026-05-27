# apps/alerts/admin.py
from django.contrib import admin
from .models import AlertSubscriber, FloodAlert, AlertDelivery


@admin.register(AlertSubscriber)
class AlertSubscriberAdmin(admin.ModelAdmin):
    list_display  = ['phone_last4', 'email', 'preferred_channel',
                     'language', 'is_verified', 'is_active', 'created_at']
    list_filter   = ['preferred_channel', 'language',
                     'is_verified', 'is_active']
    search_fields = ['email', 'phone_last4']
    readonly_fields = ['created_at', 'phone_number_hash', 'otp_secret']


@admin.register(FloodAlert)
class FloodAlertAdmin(admin.ModelAdmin):
    list_display  = ['triggered_at', 'risk_level', 'alert_type',
                     'total_recipients', 'sms_sent', 'email_sent']
    list_filter   = ['risk_level', 'alert_type', 'is_all_clear']
    ordering      = ['-triggered_at']
    readonly_fields = ['triggered_at']


@admin.register(AlertDelivery)
class AlertDeliveryAdmin(admin.ModelAdmin):
    list_display  = ['alert', 'subscriber', 'channel', 'status', 'sent_at']
    list_filter   = ['channel', 'status']
    readonly_fields = ['sent_at']