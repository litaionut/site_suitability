from django.contrib import admin
from .models import WtgModel, PowerCurvePoint, CtCurvePoint, Layout, Turbine


class PowerCurvePointInline(admin.TabularInline):
    model = PowerCurvePoint
    extra = 1


class CtCurvePointInline(admin.TabularInline):
    model = CtCurvePoint
    extra = 1


@admin.register(WtgModel)
class WtgModelAdmin(admin.ModelAdmin):
    list_display = ['name', 'rotor_d_m', 'hub_height_default_m', 'default_speed_class', 'default_ti_category', 'ct_status']
    list_filter = ['default_speed_class', 'default_ti_category', 'ct_status']
    search_fields = ['name']
    inlines = [PowerCurvePointInline, CtCurvePointInline]
    actions = ['update_ct_status_action']

    def update_ct_status_action(self, request, queryset):
        for wtg in queryset:
            wtg.update_ct_status()
            wtg.save()
        self.message_user(request, f"Updated Ct status for {queryset.count()} models")
    update_ct_status_action.short_description = "Update Ct status"


@admin.register(Layout)
class LayoutAdmin(admin.ModelAdmin):
    list_display = ['name', 'site', 'created_at', 'updated_at']
    list_filter = ['site']
    search_fields = ['name', 'site__name']


@admin.register(Turbine)
class TurbineAdmin(admin.ModelAdmin):
    list_display = ['local_id', 'layout', 'role', 'x_m', 'y_m', 'hub_height_m', 'model']
    list_filter = ['role', 'layout__site']
    search_fields = ['local_id', 'layout__name']
