# apps/core/admin.py
from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import User, AuditLog


@admin.register(User)
class CustomUserAdmin(UserAdmin):
    list_display = ['username', 'email', 'role', 'organisation', 'is_active']
    list_filter  = ['role', 'is_active', 'is_staff']
    fieldsets    = UserAdmin.fieldsets + (
        ('Flood-Watch Info', {
            'fields': ('role', 'organisation', 'phone')
        }),
    )
    add_fieldsets = UserAdmin.add_fieldsets + (
        ('Flood-Watch Info', {
            'fields': ('role', 'organisation', 'phone')
        }),
    )


@admin.register(AuditLog)
class AuditLogAdmin(admin.ModelAdmin):
    list_display    = ['timestamp', 'action', 'actor', 'object_type', 'object_id']
    list_filter     = ['action', 'object_type']
    ordering        = ['-timestamp']
    readonly_fields = ['timestamp', 'action', 'actor',
                       'object_type', 'object_id', 'details', 'ip_address']