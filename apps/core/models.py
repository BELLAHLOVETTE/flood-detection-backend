# apps/core/models.py
from django.db import models
from django.contrib.auth.models import AbstractUser


class User(AbstractUser):
    """
    Extended Django user with role-based access control.
    Admins can do everything.
    Authorities can trigger manual alerts.
    Analysts can view data but not trigger alerts.
    """

    ROLE_CHOICES = [
        ('admin',     'System Administrator'),
        ('authority', 'Government Authority / NGO'),
        ('analyst',   'Researcher / Analyst'),
    ]

    role         = models.CharField(
                       max_length=15,
                       choices=ROLE_CHOICES,
                       default='analyst'
                   )
    organisation = models.CharField(max_length=100, blank=True)
    phone        = models.CharField(max_length=20, blank=True)

    def __str__(self):
        return f"{self.username} ({self.role})"

    def is_admin(self) -> bool:
        return self.role == 'admin' or self.is_superuser

    def is_authority(self) -> bool:
        return self.role in ('admin', 'authority') or self.is_superuser

    def can_trigger_alerts(self) -> bool:
        return self.is_authority()


class AuditLog(models.Model):
    """
    Immutable log of all important actions taken in the system.
    Who did what and when — for accountability.
    """

    action      = models.CharField(max_length=100)
    actor       = models.ForeignKey(
                      User,
                      null=True,
                      blank=True,
                      on_delete=models.SET_NULL,
                      related_name='audit_logs'
                  )
    object_type = models.CharField(max_length=50, blank=True)
    object_id   = models.CharField(max_length=50, blank=True)
    details     = models.JSONField(default=dict)
    ip_address  = models.GenericIPAddressField(null=True, blank=True)
    timestamp   = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ['-timestamp']

    def __str__(self):
        actor = self.actor.username if self.actor else 'System'
        return f"{actor} → {self.action} at {self.timestamp}"

    @classmethod
    def log(cls, action, actor=None, obj=None, details=None, ip=None):
        """Simple factory method to create a log entry."""
        return cls.objects.create(
            action=action,
            actor=actor,
            object_type=type(obj).__name__ if obj else '',
            object_id=str(obj.pk) if obj else '',
            details=details or {},
            ip_address=ip,
        )