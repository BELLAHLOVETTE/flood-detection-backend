# apps/floods/admin.py
from django.contrib import admin
from .models import FloodEvent


@admin.register(FloodEvent)
class FloodEventAdmin(admin.ModelAdmin):
    list_display  = ['event_date', 'severity', 'affected_area_km2',
                     'affected_population', 'is_confirmed']
    list_filter   = ['severity', 'is_confirmed']
    search_fields = ['description', 'source']
    ordering      = ['-event_date']
    readonly_fields = ['created_at', 'updated_at']