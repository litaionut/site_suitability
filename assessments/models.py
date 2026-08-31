from django.db import models


class Assessment(models.Model):
    """
    Site suitability assessment.
    Screening against a user-editable class envelope, not a certified IEC 61400-1 assessment.
    """
    EDITION_ED3 = 'ed3'
    EDITION_ED4 = 'ed4'
    EDITION_CHOICES = [
        (EDITION_ED3, 'Edition 3'),
        (EDITION_ED4, 'Edition 4'),
    ]

    STATUS_PASS = 'Pass'
    STATUS_WARN = 'Warn'
    STATUS_FAIL = 'Fail'
    STATUS_CHOICES = [
        (STATUS_PASS, 'Pass'),
        (STATUS_WARN, 'Warn'),
        (STATUS_FAIL, 'Fail'),
    ]

    project = models.ForeignKey('projects.Project', on_delete=models.CASCADE, related_name='assessments')
    site = models.ForeignKey('sites.Site', on_delete=models.CASCADE, related_name='assessments')
    name = models.CharField(max_length=200)
    edition = models.CharField(max_length=10, choices=EDITION_CHOICES, default=EDITION_ED4)
    
    class_envelope_snapshot = models.JSONField(help_text="Snapshot of ClassEnvelope at assessment time")
    
    overall_status = models.CharField(max_length=10, choices=STATUS_CHOICES, null=True, blank=True)
    flags = models.JSONField(default=list, blank=True, help_text="Overall assessment flags")
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.name} ({self.site.name})"

    class Meta:
        ordering = ['-created_at']


class AssessmentTurbine(models.Model):
    """
    Turbine being assessed (must be new_scored, not existing_wake_source).
    """
    assessment = models.ForeignKey(Assessment, on_delete=models.CASCADE, related_name='assessment_turbines')
    turbine = models.ForeignKey('turbines.Turbine', on_delete=models.CASCADE)
    hub_climate = models.ForeignKey('climate.HubClimate', on_delete=models.CASCADE)
    
    resolved_vref_mps = models.FloatField(help_text="Resolved Vref (m/s)")
    resolved_iref = models.FloatField(help_text="Resolved Iref")
    resolved_vave_mps = models.FloatField(help_text="Resolved design Vave (m/s)")
    
    cct = models.FloatField(help_text="Complexity correction factor (1.00 or 1.15)")
    apply_density_to_v50 = models.BooleanField(
        default=False,
        help_text="Apply density correction to V50 in extreme wind check"
    )
    
    wohler_exponents = models.JSONField(
        default=list,
        help_text="Damage equivalent exponents [m1, m2, ...]",
        blank=True
    )

    class Meta:
        unique_together = ['assessment', 'turbine']

    def __str__(self):
        return f"{self.turbine.local_id} in {self.assessment.name}"


class CheckResult(models.Model):
    """
    Individual check result for an assessed turbine.
    """
    CHECK_EXTREME_WIND = 'extreme_wind'
    CHECK_WIND_DISTRIBUTION = 'wind_distribution'
    CHECK_TURBULENCE_NTM = 'turbulence_ntm'
    CHECK_SHEAR = 'shear'
    CHECK_INFLOW = 'inflow'
    CHECK_AIR_DENSITY = 'air_density'
    CHECK_COMPLEXITY = 'complexity'
    
    CHECK_ID_CHOICES = [
        (CHECK_EXTREME_WIND, 'Extreme Wind'),
        (CHECK_WIND_DISTRIBUTION, 'Wind Distribution'),
        (CHECK_TURBULENCE_NTM, 'Turbulence NTM'),
        (CHECK_SHEAR, 'Shear'),
        (CHECK_INFLOW, 'Inflow'),
        (CHECK_AIR_DENSITY, 'Air Density'),
        (CHECK_COMPLEXITY, 'Complexity'),
    ]

    STATUS_PASS = 'Pass'
    STATUS_WARN = 'Warn'
    STATUS_FAIL = 'Fail'
    STATUS_CHOICES = [
        (STATUS_PASS, 'Pass'),
        (STATUS_WARN, 'Warn'),
        (STATUS_FAIL, 'Fail'),
    ]

    assessment_turbine = models.ForeignKey(
        AssessmentTurbine,
        on_delete=models.CASCADE,
        related_name='check_results'
    )
    check_id = models.CharField(max_length=30, choices=CHECK_ID_CHOICES)
    status = models.CharField(max_length=10, choices=STATUS_CHOICES)
    
    value = models.FloatField(null=True, blank=True, help_text="Check value")
    limit = models.FloatField(null=True, blank=True, help_text="Check limit")
    units = models.CharField(max_length=50, blank=True)
    
    detail = models.JSONField(default=dict, blank=True, help_text="Additional check details")
    flags = models.JSONField(default=list, blank=True, help_text="Check-specific flags")

    class Meta:
        unique_together = ['assessment_turbine', 'check_id']
        ordering = ['assessment_turbine', 'check_id']

    def __str__(self):
        return f"{self.get_check_id_display()}: {self.status}"
