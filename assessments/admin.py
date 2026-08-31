from django.contrib import admin
from .models import Assessment, AssessmentTurbine, CheckResult


class AssessmentTurbineInline(admin.StackedInline):
    model = AssessmentTurbine
    extra = 0


@admin.register(Assessment)
class AssessmentAdmin(admin.ModelAdmin):
    list_display = ['name', 'site', 'edition', 'overall_status', 'created_at']
    list_filter = ['edition', 'overall_status', 'site__project']
    search_fields = ['name', 'site__name']
    readonly_fields = ['created_at', 'updated_at']
    inlines = [AssessmentTurbineInline]


@admin.register(AssessmentTurbine)
class AssessmentTurbineAdmin(admin.ModelAdmin):
    list_display = ['turbine', 'assessment', 'resolved_vref_mps', 'resolved_iref', 'cct']
    list_filter = ['assessment__site']


@admin.register(CheckResult)
class CheckResultAdmin(admin.ModelAdmin):
    list_display = ['assessment_turbine', 'check_id', 'status', 'value', 'limit', 'units']
    list_filter = ['check_id', 'status']
