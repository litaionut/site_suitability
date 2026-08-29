from django.db import models


class MeteoMast(models.Model):
    """
    Meteorological mast metadata (STORE only for Slice 0).
    """
    site = models.ForeignKey('sites.Site', on_delete=models.CASCADE, related_name='meteo_masts')
    name = models.CharField(max_length=200)
    x_m = models.FloatField(help_text="Easting in site CRS (m)")
    y_m = models.FloatField(help_text="Northing in site CRS (m)")
    z_base_m = models.FloatField(help_text="Base elevation (m)")

    def __str__(self):
        return f"{self.name} ({self.site.name})"

    class Meta:
        ordering = ['site', 'name']


class MeteoHeight(models.Model):
    """
    Measurement height on a meteorological mast (STORE only for Slice 0).
    """
    mast = models.ForeignKey(MeteoMast, on_delete=models.CASCADE, related_name='heights')
    height_m = models.FloatField(help_text="Height above base (m)")
    has_wind_speed = models.BooleanField(default=True)
    has_wind_direction = models.BooleanField(default=False)
    has_ti = models.BooleanField(default=False)

    def __str__(self):
        return f"{self.mast.name} @ {self.height_m}m"

    class Meta:
        ordering = ['mast', 'height_m']
        unique_together = ['mast', 'height_m']


class MeteoSeries(models.Model):
    """
    Time series file reference (STORE only for Slice 0).
    File storage, not 10-min rows in Postgres.
    """
    height = models.ForeignKey(MeteoHeight, on_delete=models.CASCADE, related_name='series')
    data_file = models.FileField(upload_to='meteo_series/')
    start_date = models.DateTimeField()
    end_date = models.DateTimeField()
    
    duration_lt_1y = models.BooleanField(default=False)
    not_integer_years = models.BooleanField(default=False)
    recovery_lt_90 = models.BooleanField(default=False)
    timestep_ne_10min = models.BooleanField(default=False)
    no_ti = models.BooleanField(default=False)
    height_ne_hub = models.BooleanField(default=False)

    def __str__(self):
        return f"Series for {self.height}"

    class Meta:
        verbose_name_plural = 'Meteo series'


class HubClimate(models.Model):
    """
    Processed hub-height climate data for assessment.
    This is what Slice 0 runs on (not raw meteo data).
    """
    site = models.ForeignKey('sites.Site', on_delete=models.CASCADE, related_name='hub_climates')
    turbine = models.ForeignKey(
        'turbines.Turbine',
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='hub_climates',
        help_text="Optional specific turbine"
    )
    name = models.CharField(max_length=200)
    
    period_hours = models.FloatField(default=8760, help_text="Period length (hours)")
    bin_width_mps = models.FloatField(help_text="Wind speed bin width (m/s)")
    rho_kgm3 = models.FloatField(default=1.225, help_text="Air density (kg/m³)")
    v50_mps = models.FloatField(help_text="50-year extreme wind speed (m/s)")
    
    shear_alpha = models.FloatField(null=True, blank=True, help_text="Omni-directional shear exponent")
    inflow_angle_deg = models.FloatField(null=True, blank=True, help_text="Omni-directional inflow angle (deg)")

    def __str__(self):
        return f"{self.name} ({self.site.name})"

    class Meta:
        ordering = ['site', 'name']


class TiBin(models.Model):
    """
    TI bin data for HubClimate.
    """
    hub_climate = models.ForeignKey(HubClimate, on_delete=models.CASCADE, related_name='ti_bins')
    v_center_mps = models.FloatField(help_text="Bin center wind speed (m/s)")
    hours = models.FloatField(help_text="Hours in this bin")
    mean_sigma_mps = models.FloatField(help_text="Mean standard deviation (m/s)")
    std_sigma_mps = models.FloatField(
        null=True,
        blank=True,
        help_text="Std dev of sigma (null → COV=0.3 flag)"
    )
    
    shear_alpha_override = models.FloatField(null=True, blank=True, help_text="Per-bin shear override")
    inflow_angle_deg_override = models.FloatField(null=True, blank=True, help_text="Per-bin inflow override")

    class Meta:
        ordering = ['hub_climate', 'v_center_mps']
        unique_together = ['hub_climate', 'v_center_mps']

    def __str__(self):
        return f"Bin {self.v_center_mps} m/s ({self.hub_climate.name})"


class SectorWeibull(models.Model):
    """
    Optional diagnostic sector Weibull parameters (STORE only for Slice 0).
    Slice 0 uses TiBin hours, not reconstructed Weibull.
    """
    hub_climate = models.ForeignKey(HubClimate, on_delete=models.CASCADE, related_name='sector_weibulls')
    sector_from_deg = models.FloatField(help_text="Sector start (deg)")
    sector_to_deg = models.FloatField(help_text="Sector end (deg)")
    frequency = models.FloatField(help_text="Sector frequency [0,1]")
    A = models.FloatField(help_text="Weibull scale parameter")
    k = models.FloatField(help_text="Weibull shape parameter")

    def __str__(self):
        return f"Sector {self.sector_from_deg}-{self.sector_to_deg}° ({self.hub_climate.name})"

    class Meta:
        ordering = ['hub_climate', 'sector_from_deg']
