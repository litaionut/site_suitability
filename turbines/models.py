from django.db import models


class WtgModel(models.Model):
    """
    Wind turbine generator model specification.
    """
    CLASS_I = 'I'
    CLASS_II = 'II'
    CLASS_III = 'III'
    CLASS_S = 'S'
    SPEED_CLASS_CHOICES = [
        (CLASS_I, 'Class I'),
        (CLASS_II, 'Class II'),
        (CLASS_III, 'Class III'),
        (CLASS_S, 'Class S'),
    ]

    TI_A_PLUS = 'A+'
    TI_A = 'A'
    TI_B = 'B'
    TI_C = 'C'
    TI_S = 'S'
    TI_CATEGORY_CHOICES = [
        (TI_A_PLUS, 'A+'),
        (TI_A, 'A'),
        (TI_B, 'B'),
        (TI_C, 'C'),
        (TI_S, 'S'),
    ]

    CT_STATUS_OK = 'ok'
    CT_STATUS_MISSING = 'missing'
    CT_STATUS_SUSPECT = 'suspect'
    CT_STATUS_CHOICES = [
        (CT_STATUS_OK, 'OK'),
        (CT_STATUS_MISSING, 'Missing'),
        (CT_STATUS_SUSPECT, 'Suspect'),
    ]

    name = models.CharField(max_length=200, unique=True)
    rotor_d_m = models.FloatField(help_text="Rotor diameter (m)")
    hub_height_default_m = models.FloatField(help_text="Default hub height (m)")
    v_in_mps = models.FloatField(help_text="Cut-in wind speed (m/s)")
    v_rated_mps = models.FloatField(help_text="Rated wind speed (m/s)")
    v_out_mps = models.FloatField(help_text="Cut-out wind speed (m/s)")
    default_speed_class = models.CharField(max_length=5, choices=SPEED_CLASS_CHOICES, default=CLASS_II)
    default_ti_category = models.CharField(max_length=5, choices=TI_CATEGORY_CHOICES, default=TI_B)
    ct_status = models.CharField(max_length=10, choices=CT_STATUS_CHOICES, default=CT_STATUS_MISSING)

    def __str__(self):
        return self.name

    def update_ct_status(self):
        """
        Update Ct status based on curve data.
        Never invent Ct values.
        """
        ct_points = self.ct_curve_points.all().order_by('v_mps')
        if not ct_points.exists():
            self.ct_status = self.CT_STATUS_MISSING
            return

        v_values = [p.v_mps for p in ct_points]
        ct_values = [p.ct for p in ct_points]

        if any(ct < 0 or ct > 1.2 for ct in ct_values):
            self.ct_status = self.CT_STATUS_SUSPECT
            return

        for i in range(len(v_values) - 1):
            if v_values[i + 1] - v_values[i] > 1.5:
                self.ct_status = self.CT_STATUS_SUSPECT
                return

        self.ct_status = self.CT_STATUS_OK

    class Meta:
        verbose_name = 'WTG Model'
        verbose_name_plural = 'WTG Models'
        ordering = ['name']


class PowerCurvePoint(models.Model):
    """
    Single point on a power curve.
    """
    wtg_model = models.ForeignKey(WtgModel, on_delete=models.CASCADE, related_name='power_curve_points')
    v_mps = models.FloatField(help_text="Wind speed (m/s)")
    p_kw = models.FloatField(help_text="Power output (kW)")

    class Meta:
        ordering = ['wtg_model', 'v_mps']
        unique_together = ['wtg_model', 'v_mps']

    def __str__(self):
        return f"{self.wtg_model.name} @ {self.v_mps} m/s: {self.p_kw} kW"


class CtCurvePoint(models.Model):
    """
    Single point on a thrust coefficient curve.
    """
    wtg_model = models.ForeignKey(WtgModel, on_delete=models.CASCADE, related_name='ct_curve_points')
    v_mps = models.FloatField(help_text="Wind speed (m/s)")
    ct = models.FloatField(help_text="Thrust coefficient")

    class Meta:
        ordering = ['wtg_model', 'v_mps']
        unique_together = ['wtg_model', 'v_mps']

    def __str__(self):
        return f"{self.wtg_model.name} @ {self.v_mps} m/s: Ct={self.ct}"


class Layout(models.Model):
    """
    Turbine layout for a site.
    """
    site = models.ForeignKey('sites.Site', on_delete=models.CASCADE, related_name='layouts')
    name = models.CharField(max_length=200)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.name} ({self.site.name})"

    class Meta:
        ordering = ['site', 'name']


class Turbine(models.Model):
    """
    Individual turbine instance in a layout.
    """
    ROLE_NEW_SCORED = 'new_scored'
    ROLE_EXISTING_WAKE_SOURCE = 'existing_wake_source'
    ROLE_CHOICES = [
        (ROLE_NEW_SCORED, 'New (scored)'),
        (ROLE_EXISTING_WAKE_SOURCE, 'Existing (wake source)'),
    ]

    layout = models.ForeignKey(Layout, on_delete=models.CASCADE, related_name='turbines')
    local_id = models.CharField(max_length=50, help_text="Unique ID within layout (e.g., T01)")
    role = models.CharField(max_length=30, choices=ROLE_CHOICES, default=ROLE_NEW_SCORED)
    
    x_m = models.FloatField(help_text="Easting in site CRS (m)")
    y_m = models.FloatField(help_text="Northing in site CRS (m)")
    z_base_m = models.FloatField(help_text="Base elevation (m)")
    
    hub_height_m = models.FloatField(help_text="Hub height above base (m)")
    rotor_d_m = models.FloatField(help_text="Rotor diameter (m)")
    
    model = models.ForeignKey(WtgModel, on_delete=models.PROTECT, null=True, blank=True)
    
    speed_class_override = models.CharField(
        max_length=5,
        choices=WtgModel.SPEED_CLASS_CHOICES,
        null=True,
        blank=True,
        help_text="Override model's default speed class"
    )
    ti_category_override = models.CharField(
        max_length=5,
        choices=WtgModel.TI_CATEGORY_CHOICES,
        null=True,
        blank=True,
        help_text="Override model's default TI category"
    )
    
    curtailment_json = models.JSONField(null=True, blank=True, help_text="Optional curtailment settings")

    class Meta:
        ordering = ['layout', 'local_id']
        unique_together = ['layout', 'local_id']

    def __str__(self):
        return f"{self.local_id} ({self.layout.name})"

    def get_speed_class(self):
        """Get effective speed class (override or model default)."""
        return self.speed_class_override or (self.model.default_speed_class if self.model else None)

    def get_ti_category(self):
        """Get effective TI category (override or model default)."""
        return self.ti_category_override or (self.model.default_ti_category if self.model else None)
