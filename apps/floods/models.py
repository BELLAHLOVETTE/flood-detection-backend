# apps/floods/models.py
import uuid
from django.db import models


class FloodEvent(models.Model):
    """
    Records a confirmed historical or current flood event
    in the Maga region. Data comes from UNOSAT, OCHA reports,
    and our own GEE detection system.
    """

    SEVERITY_CHOICES = [
        ('low',      'Low'),
        ('medium',   'Medium'),
        ('high',     'High'),
        ('critical', 'Critical'),
    ]

    id                   = models.UUIDField(
                               primary_key=True,
                               default=uuid.uuid4,
                               editable=False
                           )
    event_date           = models.DateField(db_index=True)
    end_date             = models.DateField(null=True, blank=True)
    severity             = models.CharField(
                               max_length=10,
                               choices=SEVERITY_CHOICES,
                               default='medium'
                           )
    affected_area_km2    = models.FloatField(default=0.0)
    affected_population  = models.IntegerField(default=0)
    max_water_level_m    = models.FloatField(null=True, blank=True)
    description          = models.TextField(blank=True)
    source               = models.CharField(max_length=200, blank=True)
    is_confirmed         = models.BooleanField(default=True)
    flood_extent_geojson = models.JSONField(null=True, blank=True)
    created_at           = models.DateTimeField(auto_now_add=True)
    updated_at           = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-event_date']
        indexes  = [
            models.Index(fields=['event_date']),
            models.Index(fields=['severity']),
        ]

    def __str__(self):
        return f"Flood Event — {self.event_date} ({self.severity})"

    def get_duration_days(self):
        """How many days did this flood last?"""
        if self.end_date and self.event_date:
            return (self.end_date - self.event_date).days
        return None

    def get_severity_display_fr(self):
        """Return severity in French for the Cameroon audience."""
        mapping = {
            'low':      'Faible',
            'medium':   'Modéré',
            'high':     'Élevé',
            'critical': 'Critique',
        }
        return mapping.get(self.severity, self.severity)