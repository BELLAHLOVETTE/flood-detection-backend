# apps/predictions/models.py
import uuid
from django.db import models
from django.contrib.auth import get_user_model

User = get_user_model()

RISK_LEVELS = [
    ('low',      'Low'),
    ('medium',   'Medium'),
    ('high',     'High'),
    ('critical', 'Critical'),
]


class SatelliteObservation(models.Model):
    """
    Records each time our system fetches satellite data from GEE.
    Stores the raw results — flood extent GeoJSON, features used
    for ML inference, and the status of the fetch operation.
    """

    SATELLITE_CHOICES = [
        ('sentinel1', 'Sentinel-1 SAR'),
        ('sentinel2', 'Sentinel-2 Optical'),
        ('chirps',    'CHIRPS Rainfall'),
        ('jrc',       'JRC Surface Water'),
    ]
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('success', 'Success'),
        ('failed',  'Failed'),
    ]

    id                   = models.UUIDField(
                               primary_key=True,
                               default=uuid.uuid4,
                               editable=False
                           )
    acquisition_date     = models.DateTimeField(db_index=True)
    satellite            = models.CharField(
                               max_length=20,
                               choices=SATELLITE_CHOICES,
                               default='sentinel1'
                           )
    status               = models.CharField(
                               max_length=10,
                               choices=STATUS_CHOICES,
                               default='pending'
                           )
    flood_extent_geojson = models.JSONField(null=True, blank=True)
    processed_features   = models.JSONField(default=dict)
    error_message        = models.TextField(blank=True)
    gee_task_id          = models.CharField(max_length=100, blank=True)
    created_at           = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-acquisition_date']

    def __str__(self):
        return f"Observation {self.satellite} — {self.acquisition_date.date()} ({self.status})"

    def get_flood_area_km2(self):
        return self.processed_features.get('flood_area_km2', 0.0)

    @classmethod
    def get_latest_successful(cls):
        return cls.objects.filter(status='success').first()


class RiskAssessment(models.Model):
    """
    Stores each ML model inference result.
    Created every 6 hours by the Celery task after
    new satellite data is fetched from GEE.
    """

    id                  = models.UUIDField(
                              primary_key=True,
                              default=uuid.uuid4,
                              editable=False
                          )
    assessed_at         = models.DateTimeField(
                              auto_now_add=True,
                              db_index=True
                          )
    probability         = models.FloatField()
    risk_level          = models.CharField(
                              max_length=10,
                              choices=RISK_LEVELS,
                              db_index=True
                          )
    previous_risk_level = models.CharField(
                              max_length=10,
                              choices=RISK_LEVELS,
                              blank=True
                          )
    model_version       = models.CharField(max_length=30, default='rule-based-v1')
    feature_vector      = models.JSONField(default=dict)
    is_manual_override  = models.BooleanField(default=False)
    override_by         = models.ForeignKey(
                              User,
                              null=True,
                              blank=True,
                              on_delete=models.SET_NULL,
                              related_name='risk_overrides'
                          )
    satellite_obs       = models.ForeignKey(
                              SatelliteObservation,
                              null=True,
                              blank=True,
                              on_delete=models.SET_NULL
                          )

    class Meta:
        ordering = ['-assessed_at']
        indexes  = [
            models.Index(fields=['assessed_at', 'risk_level']),
        ]

    def __str__(self):
        return f"Risk: {self.risk_level} ({self.probability:.0%}) — {self.assessed_at.date()}"

    @property
    def is_escalation(self):
        """True if risk went UP compared to previous assessment."""
        levels = ['low', 'medium', 'high', 'critical']
        if not self.previous_risk_level:
            return False
        try:
            return (levels.index(self.risk_level) >
                    levels.index(self.previous_risk_level))
        except ValueError:
            return False

    def get_risk_color(self):
        """Return hex colour for this risk level."""
        colors = {
            'low':      '#22c55e',
            'medium':   '#eab308',
            'high':     '#f97316',
            'critical': '#ef4444',
        }
        return colors.get(self.risk_level, '#gray')

    @classmethod
    def get_current(cls):
        """Get the most recent risk assessment."""
        return cls.objects.first()

    @classmethod
    def get_history(cls, days=30):
        """Get all assessments from the last N days."""
        from django.utils import timezone
        cutoff = timezone.now() - timezone.timedelta(days=days)
        return cls.objects.filter(assessed_at__gte=cutoff)


class RainfallReading(models.Model):
    """
    Daily rainfall readings for the Maga region.
    Data comes from CHIRPS via GEE, fetched every 6 hours
    by the Celery ingestion task.
    """

    date          = models.DateField(unique=True, db_index=True)
    rainfall_mm   = models.FloatField()
    cumulative_7d  = models.FloatField(default=0.0)
    cumulative_30d = models.FloatField(default=0.0)
    source        = models.CharField(max_length=50, default='CHIRPS')
    created_at    = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-date']

    def __str__(self):
        return f"Rainfall {self.date}: {self.rainfall_mm}mm"


class WaterLevelReading(models.Model):
    """
    Estimated Lake Maga water surface area readings.
    Derived from JRC Global Surface Water monthly data via GEE.
    Used to track how full the lake is relative to its baseline.
    """

    date              = models.DateField(unique=True, db_index=True)
    water_area_km2    = models.FloatField()
    baseline_area_km2 = models.FloatField(default=130.0)
    change_percent    = models.FloatField(default=0.0)
    ndwi_mean         = models.FloatField(null=True, blank=True)
    sar_backscatter_ratio = models.FloatField(null=True, blank=True)
    source            = models.CharField(max_length=50, default='JRC')
    created_at        = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-date']

    def __str__(self):
        return f"Water Level {self.date}: {self.water_area_km2}km²"

    def get_fill_percentage(self):
        """How full is the lake compared to baseline?"""
        if self.baseline_area_km2 == 0:
            return 0
        return round((self.water_area_km2 / self.baseline_area_km2) * 100, 1)

    @classmethod
    def get_latest(cls):
        return cls.objects.first()


class MLModel(models.Model):
    """
    Tracks trained ML model versions, their performance
    metrics, and which one is currently active for inference.
    """

    MODEL_TYPE_CHOICES = [
        ('random_forest', 'Random Forest'),
        ('lstm',          'LSTM Neural Network'),
        ('rule_based',    'Rule-Based Fallback'),
    ]

    id               = models.UUIDField(
                           primary_key=True,
                           default=uuid.uuid4,
                           editable=False
                       )
    version          = models.CharField(max_length=30, unique=True)
    model_type       = models.CharField(max_length=20, choices=MODEL_TYPE_CHOICES)
    file_path        = models.CharField(max_length=500, blank=True)
    is_active        = models.BooleanField(default=False)
    f1_score         = models.FloatField(null=True, blank=True)
    precision        = models.FloatField(null=True, blank=True)
    recall           = models.FloatField(null=True, blank=True)
    auc_roc          = models.FloatField(null=True, blank=True)
    training_samples = models.IntegerField(default=0)
    feature_names    = models.JSONField(default=list)
    hyperparameters  = models.JSONField(default=dict)
    trained_at       = models.DateTimeField(null=True, blank=True)
    created_at       = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-trained_at']

    def __str__(self):
        active = " [ACTIVE]" if self.is_active else ""
        return f"{self.version} ({self.model_type}){active}"

    @classmethod
    def get_active(cls):
        """Get the currently active model for inference."""
        return cls.objects.filter(is_active=True).first()