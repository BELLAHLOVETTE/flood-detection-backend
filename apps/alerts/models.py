# apps/alerts/models.py
import hashlib
import uuid
import pyotp
from django.db import models
from django.contrib.auth import get_user_model
from apps.predictions.models import RiskAssessment, RISK_LEVELS

User = get_user_model()


class AlertSubscriber(models.Model):
    """
    Anyone who signs up to receive flood alert SMS or emails.
    Phone numbers are stored as a one-way hash for privacy.
    Only the last 4 digits are stored in plain text.
    """

    CHANNEL_CHOICES = [
        ('sms',   'SMS Only'),
        ('email', 'Email Only'),
        ('both',  'SMS and Email'),
    ]
    LANGUAGE_CHOICES = [
        ('fr', 'Français'),
        ('en', 'English'),
    ]

    id                = models.UUIDField(
                            primary_key=True,
                            default=uuid.uuid4,
                            editable=False
                        )
    phone_number_hash = models.CharField(
                            max_length=64,
                            blank=True,
                            db_index=True
                        )
    phone_last4       = models.CharField(max_length=4, blank=True)
    email             = models.EmailField(null=True, blank=True)
    preferred_channel = models.CharField(
                            max_length=10,
                            choices=CHANNEL_CHOICES,
                            default='sms'
                        )
    language          = models.CharField(
                            max_length=2,
                            choices=LANGUAGE_CHOICES,
                            default='fr'
                        )
    is_verified       = models.BooleanField(default=False)
    otp_secret        = models.CharField(max_length=32, blank=True)
    subscription_area = models.CharField(max_length=100, default='Maga')
    is_active         = models.BooleanField(default=True)
    last_alert_sent   = models.DateTimeField(null=True, blank=True)
    created_at        = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        if self.email:
            return f"Subscriber: {self.email}"
        return f"Subscriber: ****{self.phone_last4}"

    @staticmethod
    def hash_phone(phone: str) -> str:
        """
        One-way hash of phone number for privacy.
        We can check if a number is already subscribed
        without storing the actual number.
        """
        return hashlib.sha256(phone.strip().encode()).hexdigest()

    def generate_otp(self) -> str:
        """Generate a 6-digit OTP. Expires after 5 minutes."""
        if not self.otp_secret:
            self.otp_secret = pyotp.random_base32()
            self.save(update_fields=['otp_secret'])
        totp = pyotp.TOTP(self.otp_secret, interval=300)
        return totp.now()

    def verify_otp(self, token: str) -> bool:
        """Check if the OTP the user entered is correct."""
        if not self.otp_secret:
            return False
        totp = pyotp.TOTP(self.otp_secret, interval=300)
        return totp.verify(token, valid_window=1)

    def mask_phone(self) -> str:
        return f"**** **** {self.phone_last4}"

    @classmethod
    def get_active_count(cls) -> int:
        return cls.objects.filter(
            is_active=True,
            is_verified=True
        ).count()


class FloodAlert(models.Model):
    """
    Records every alert that was dispatched — both automated
    ones triggered by the ML model and manual ones triggered
    by an authority user through the admin dashboard.
    """

    ALERT_TYPE_CHOICES = [
        ('automated', 'Automated by ML Model'),
        ('manual',    'Manual by Authority'),
    ]

    id               = models.UUIDField(
                           primary_key=True,
                           default=uuid.uuid4,
                           editable=False
                       )
    triggered_at     = models.DateTimeField(auto_now_add=True, db_index=True)
    risk_level       = models.CharField(max_length=10, choices=RISK_LEVELS)
    alert_type       = models.CharField(
                           max_length=12,
                           choices=ALERT_TYPE_CHOICES,
                           default='automated'
                       )
    title            = models.CharField(max_length=200)
    message_fr       = models.TextField()
    message_en       = models.TextField(blank=True)
    total_recipients = models.IntegerField(default=0)
    sms_sent         = models.IntegerField(default=0)
    email_sent       = models.IntegerField(default=0)
    push_sent        = models.IntegerField(default=0)
    triggered_by     = models.ForeignKey(
                           User,
                           null=True,
                           blank=True,
                           on_delete=models.SET_NULL,
                           related_name='triggered_alerts'
                       )
    risk_assessment  = models.ForeignKey(
                           RiskAssessment,
                           null=True,
                           blank=True,
                           on_delete=models.SET_NULL,
                           related_name='alerts'
                       )
    is_all_clear     = models.BooleanField(default=False)

    class Meta:
        ordering = ['-triggered_at']

    def __str__(self):
        return f"Alert [{self.risk_level.upper()}] — {self.triggered_at.date()}"

    def get_delivery_rate(self) -> float:
        if self.total_recipients == 0:
            return 0.0
        delivered = self.sms_sent + self.email_sent
        total_possible = self.total_recipients * 2
        return round(delivered / total_possible * 100, 1)

    def build_sms_text(self, lang: str = 'fr') -> str:
        """Build the SMS message text."""
        if lang == 'fr':
            level_map = {
                'low':      'FAIBLE',
                'medium':   'MODÉRÉ',
                'high':     'ÉLEVÉ',
                'critical': 'CRITIQUE'
            }
            level = level_map.get(self.risk_level, self.risk_level.upper())
            return (
                f"[FLOOD-WATCH] ALERTE INONDATION — Niveau {level}\n"
                f"{self.message_fr}\n"
                f"Zone: Maga, Far North Cameroun\n"
                f"Info: floodwatch.cm"
            )
        return self.message_en

    @classmethod
    def get_latest_active(cls):
        return cls.objects.filter(is_all_clear=False).first()


class AlertDelivery(models.Model):
    """
    Tracks the delivery status of each individual alert
    sent to each individual subscriber.
    One row per alert per subscriber per channel.
    """

    STATUS_CHOICES = [
        ('pending',   'Pending'),
        ('sent',      'Sent'),
        ('delivered', 'Delivered'),
        ('failed',    'Failed'),
    ]
    CHANNEL_CHOICES = [
        ('sms',   'SMS'),
        ('email', 'Email'),
        ('push',  'Push Notification'),
    ]

    alert               = models.ForeignKey(
                              FloodAlert,
                              on_delete=models.CASCADE,
                              related_name='deliveries'
                          )
    subscriber          = models.ForeignKey(
                              AlertSubscriber,
                              on_delete=models.CASCADE,
                              related_name='deliveries'
                          )
    channel             = models.CharField(max_length=10, choices=CHANNEL_CHOICES)
    status              = models.CharField(
                              max_length=10,
                              choices=STATUS_CHOICES,
                              default='pending'
                          )
    provider_message_id = models.CharField(max_length=100, blank=True)
    sent_at             = models.DateTimeField(null=True, blank=True)
    error_code          = models.CharField(max_length=50, blank=True)

    class Meta:
        unique_together = ('alert', 'subscriber', 'channel')

    def __str__(self):
        return f"{self.channel} to {self.subscriber} — {self.status}"