from django.contrib.gis.db import models as gis_models
from django.db import models
import math


class Site(models.Model):
    """
    Wind farm site with CRS calculation.
    """
    COMPLEXITY_SIMPLE = 'simple'
    COMPLEXITY_COMPLEX = 'complex'
    COMPLEXITY_CHOICES = [
        (COMPLEXITY_SIMPLE, 'Simple'),
        (COMPLEXITY_COMPLEX, 'Complex'),
    ]

    project = models.ForeignKey('projects.Project', on_delete=models.CASCADE, related_name='sites')
    name = models.CharField(max_length=200)
    center_lon_deg = models.FloatField(help_text="Center longitude (EPSG:4326)")
    center_lat_deg = models.FloatField(help_text="Center latitude (EPSG:4326)")
    
    utm_zone = models.IntegerField(editable=False)
    utm_north = models.BooleanField(editable=False)
    crs_epsg = models.IntegerField(editable=False, help_text="UTM CRS EPSG code")
    
    default_complexity = models.CharField(
        max_length=10,
        choices=COMPLEXITY_CHOICES,
        default=COMPLEXITY_SIMPLE,
        help_text="Default terrain complexity for CCT calculation"
    )
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def save(self, *args, **kwargs):
        self.utm_zone = math.floor((self.center_lon_deg + 180) / 6) + 1
        self.utm_north = self.center_lat_deg >= 0
        self.crs_epsg = (32600 if self.utm_north else 32700) + self.utm_zone
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.name} ({self.project.name})"

    class Meta:
        ordering = ['project', 'name']


class ElevationDataset(models.Model):
    """
    Elevation data source metadata (STORE only for Slice 0).
    """
    KIND_GRID = 'grid'
    KIND_CONTOURS = 'contours'
    KIND_CHOICES = [
        (KIND_GRID, 'Grid'),
        (KIND_CONTOURS, 'Contours'),
    ]

    site = models.ForeignKey(Site, on_delete=models.CASCADE, related_name='elevation_datasets')
    kind = models.CharField(max_length=20, choices=KIND_CHOICES)
    source_label = models.CharField(max_length=200, help_text="e.g., SRTM, ASTER, custom survey")
    vertical_datum = models.CharField(max_length=100, blank=True)
    is_surface_not_dtm = models.BooleanField(
        default=True,
        help_text="True if source matches srtm|aster|dsm|surface"
    )
    coverage_radius_target_m = models.FloatField(default=7000)
    coverage_ok = models.BooleanField(default=False)
    coverage_note = models.TextField(blank=True)

    def __str__(self):
        return f"{self.source_label} ({self.kind}) - {self.site.name}"

    class Meta:
        ordering = ['site', 'kind', 'source_label']


class ElevationGrid(models.Model):
    """
    Raster elevation grid (STORE only).
    """
    dataset = models.ForeignKey(ElevationDataset, on_delete=models.CASCADE, related_name='grids')
    origin_x = models.FloatField(help_text="Origin X in site CRS (m)")
    origin_y = models.FloatField(help_text="Origin Y in site CRS (m)")
    dx = models.FloatField(help_text="Cell width (m)")
    dy = models.FloatField(help_text="Cell height (m)")
    nrows = models.IntegerField()
    ncols = models.IntegerField()
    nodata_value = models.FloatField(null=True, blank=True)
    geotiff_file = models.FileField(upload_to='elevation_grids/')

    def __str__(self):
        return f"Grid {self.ncols}x{self.nrows} - {self.dataset.source_label}"


class ElevationContour(models.Model):
    """
    Elevation contour line (STORE only).
    """
    dataset = models.ForeignKey(ElevationDataset, on_delete=models.CASCADE, related_name='contours')
    z_m = models.FloatField(help_text="Elevation (m)")
    geometry = gis_models.LineStringField(srid=4326, help_text="Contour line geometry")

    def __str__(self):
        return f"Contour {self.z_m}m - {self.dataset.site.name}"


class RoughnessDataset(models.Model):
    """
    Surface roughness data source metadata (STORE only for Slice 0).
    """
    site = models.ForeignKey(Site, on_delete=models.CASCADE, related_name='roughness_datasets')
    background_z0_m = models.FloatField(
        default=0.03,
        help_text="Background roughness length (m), product default not IEC"
    )
    coverage_radius_m = models.FloatField(default=20000)
    coverage_ok = models.BooleanField(default=False)
    coverage_note = models.TextField(blank=True)

    def __str__(self):
        return f"Roughness dataset - {self.site.name}"


class RoughnessPolygon(models.Model):
    """
    Polygon with uniform roughness (STORE only).
    """
    dataset = models.ForeignKey(RoughnessDataset, on_delete=models.CASCADE, related_name='polygons')
    geometry = gis_models.PolygonField(srid=4326)
    z0_m = models.FloatField(help_text="Roughness length (m)")
    class_label = models.CharField(max_length=100, blank=True, help_text="Optional land class label")

    def __str__(self):
        return f"z0={self.z0_m}m {self.class_label or ''}"


class RoughnessLine(models.Model):
    """
    Line with different roughness on each side (STORE only).
    """
    dataset = models.ForeignKey(RoughnessDataset, on_delete=models.CASCADE, related_name='lines')
    geometry = gis_models.LineStringField(srid=4326)
    z0_left_m = models.FloatField(help_text="Roughness length on left side (m)")
    z0_right_m = models.FloatField(help_text="Roughness length on right side (m)")

    def __str__(self):
        return f"z0_L={self.z0_left_m}m, z0_R={self.z0_right_m}m"
