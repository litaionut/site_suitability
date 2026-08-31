import uuid
from django.db import models


class Project(models.Model):
    """
    Wind turbine project container.
    """
    uuid = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=200)
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.name

    class Meta:
        ordering = ['-created_at']


class ClassEnvelope(models.Model):
    """
    User-editable wind class envelope parameters.
    Screening against a user-editable class envelope, not a certified IEC 61400-1 assessment.
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

    project = models.OneToOneField(
        Project,
        on_delete=models.CASCADE,
        related_name='class_envelope'
    )
    
    vref_i = models.FloatField(default=50.0, help_text="Vref for Class I (m/s)")
    vref_ii = models.FloatField(default=42.5, help_text="Vref for Class II (m/s)")
    vref_iii = models.FloatField(default=37.5, help_text="Vref for Class III (m/s)")
    
    iref_a_plus = models.FloatField(default=0.18, help_text="Iref for A+")
    iref_a = models.FloatField(default=0.16, help_text="Iref for A")
    iref_b = models.FloatField(default=0.14, help_text="Iref for B")
    iref_c = models.FloatField(default=0.12, help_text="Iref for C")
    
    vave_over_vref = models.FloatField(default=0.2, help_text="Vave/Vref ratio")

    def __str__(self):
        return f"ClassEnvelope for {self.project.name}"

    def get_vref(self, speed_class):
        """Get Vref for a given speed class."""
        if speed_class == self.CLASS_I:
            return self.vref_i
        elif speed_class == self.CLASS_II:
            return self.vref_ii
        elif speed_class == self.CLASS_III:
            return self.vref_iii
        return None

    def get_iref(self, ti_category):
        """Get Iref for a given TI category."""
        if ti_category == self.TI_A_PLUS:
            return self.iref_a_plus
        elif ti_category == self.TI_A:
            return self.iref_a
        elif ti_category == self.TI_B:
            return self.iref_b
        elif ti_category == self.TI_C:
            return self.iref_c
        return None

    class Meta:
        verbose_name = 'Class Envelope'
        verbose_name_plural = 'Class Envelopes'
