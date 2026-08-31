from django.contrib import admin
from .models import (
    MeteoMast, MeteoHeight, MeteoSeries,
    HubClimate, TiBin, SectorWeibull
)


@admin.register(MeteoMast)
class MeteoMastAdmin(admin.ModelAdmin):
    list_display = ['name', 'site', 'x_m', 'y_m', 'z_base_m']
    list_filter = ['site']
    search_fields = ['name', 'site__name']


@admin.register(MeteoHeight)
class MeteoHeightAdmin(admin.ModelAdmin):
    list_display = ['mast', 'height_m', 'has_wind_speed', 'has_wind_direction', 'has_ti']
    list_filter = ['mast__site', 'has_wind_speed', 'has_ti']


@admin.register(MeteoSeries)
class MeteoSeriesAdmin(admin.ModelAdmin):
    list_display = ['height', 'start_date', 'end_date', 'duration_lt_1y', 'recovery_lt_90']
    list_filter = ['duration_lt_1y', 'not_integer_years', 'recovery_lt_90', 'no_ti']


class TiBinInline(admin.TabularInline):
    model = TiBin
    extra = 1


@admin.register(HubClimate)
class HubClimateAdmin(admin.ModelAdmin):
    list_display = ['name', 'site', 'turbine', 'period_hours', 'v50_mps', 'rho_kgm3']
    list_filter = ['site']
    search_fields = ['name', 'site__name']
    inlines = [TiBinInline]


@admin.register(TiBin)
class TiBinAdmin(admin.ModelAdmin):
    list_display = ['hub_climate', 'v_center_mps', 'hours', 'mean_sigma_mps', 'std_sigma_mps']
    list_filter = ['hub_climate__site']


@admin.register(SectorWeibull)
class SectorWeibullAdmin(admin.ModelAdmin):
    list_display = ['hub_climate', 'sector_from_deg', 'sector_to_deg', 'frequency', 'A', 'k']
    list_filter = ['hub_climate__site']
