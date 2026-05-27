from django.contrib import admin

# Register your models here.
# apps/predictions/admin.py
from django.contrib import admin
from .models import (
    RiskAssessment,
    SatelliteObservation,
    RainfallReading,
    WaterLevelReading,
    MLModel,
)


@admin.register(RiskAssessment)
class RiskAssessmentAdmin(admin.ModelAdmin):
    list_display  = ['assessed_at', 'risk_level', 'probability',
                     'model_version', 'is_manual_override']
    list_filter   = ['risk_level', 'is_manual_override']
    ordering      = ['-assessed_at']
    readonly_fields = ['assessed_at']


@admin.register(SatelliteObservation)
class SatelliteObservationAdmin(admin.ModelAdmin):
    list_display  = ['acquisition_date', 'satellite', 'status']
    list_filter   = ['satellite', 'status']
    ordering      = ['-acquisition_date']
    readonly_fields = ['created_at']


@admin.register(RainfallReading)
class RainfallReadingAdmin(admin.ModelAdmin):
    list_display  = ['date', 'rainfall_mm', 'cumulative_7d',
                     'cumulative_30d', 'source']
    ordering      = ['-date']
    readonly_fields = ['created_at']


@admin.register(WaterLevelReading)
class WaterLevelReadingAdmin(admin.ModelAdmin):
    list_display  = ['date', 'water_area_km2', 'baseline_area_km2',
                     'change_percent', 'source']
    ordering      = ['-date']
    readonly_fields = ['created_at']


@admin.register(MLModel)
class MLModelAdmin(admin.ModelAdmin):
    list_display  = ['version', 'model_type', 'is_active',
                     'f1_score', 'auc_roc', 'trained_at']
    list_filter   = ['model_type', 'is_active']
    ordering      = ['-trained_at']
    readonly_fields = ['created_at']