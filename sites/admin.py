from django.contrib import admin
from .models import (
    Site, ElevationDataset, ElevationGrid, ElevationContour,
    RoughnessDataset, RoughnessPolygon, RoughnessLine
)


@admin.register(Site)
class SiteAdmin(admin.ModelAdmin):
    list_display = ['name', 'project', 'center_lon_deg', 'center_lat_deg', 'utm_zone', 'crs_epsg', 'default_complexity']
    list_filter = ['project', 'default_complexity']
    search_fields = ['name', 'project__name']
    readonly_fields = ['utm_zone', 'utm_north', 'crs_epsg', 'created_at', 'updated_at']


@admin.register(ElevationDataset)
class ElevationDatasetAdmin(admin.ModelAdmin):
    list_display = ['source_label', 'kind', 'site', 'coverage_ok']
    list_filter = ['kind', 'coverage_ok']


@admin.register(ElevationGrid)
class ElevationGridAdmin(admin.ModelAdmin):
    list_display = ['dataset', 'ncols', 'nrows', 'dx', 'dy']


@admin.register(ElevationContour)
class ElevationContourAdmin(admin.ModelAdmin):
    list_display = ['dataset', 'z_m']


@admin.register(RoughnessDataset)
class RoughnessDatasetAdmin(admin.ModelAdmin):
    list_display = ['site', 'background_z0_m', 'coverage_ok']


@admin.register(RoughnessPolygon)
class RoughnessPolygonAdmin(admin.ModelAdmin):
    list_display = ['dataset', 'z0_m', 'class_label']


@admin.register(RoughnessLine)
class RoughnessLineAdmin(admin.ModelAdmin):
    list_display = ['dataset', 'z0_left_m', 'z0_right_m']
