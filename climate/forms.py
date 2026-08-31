"""
Forms for climate app.
"""
from django import forms
from django.forms import inlineformset_factory
from .models import HubClimate, TiBin


class HubClimateForm(forms.ModelForm):
    """Form for creating and editing hub climates."""
    
    class Meta:
        model = HubClimate
        fields = [
            'name', 'period_hours', 'bin_width_mps', 'rho_kgm3',
            'v50_mps', 'shear_alpha', 'inflow_angle_deg'
        ]
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control'}),
            'period_hours': forms.NumberInput(attrs={'class': 'form-control', 'step': 'any'}),
            'bin_width_mps': forms.NumberInput(attrs={'class': 'form-control', 'step': 'any'}),
            'rho_kgm3': forms.NumberInput(attrs={'class': 'form-control', 'step': 'any'}),
            'v50_mps': forms.NumberInput(attrs={'class': 'form-control', 'step': 'any'}),
            'shear_alpha': forms.NumberInput(attrs={'class': 'form-control', 'step': 'any'}),
            'inflow_angle_deg': forms.NumberInput(attrs={'class': 'form-control', 'step': 'any'}),
        }


class TiBinForm(forms.ModelForm):
    """Form for TI bin."""
    
    class Meta:
        model = TiBin
        fields = ['v_center_mps', 'hours', 'mean_sigma_mps', 'std_sigma_mps']
        widgets = {
            'v_center_mps': forms.NumberInput(attrs={'class': 'form-control', 'step': 'any'}),
            'hours': forms.NumberInput(attrs={'class': 'form-control', 'step': 'any'}),
            'mean_sigma_mps': forms.NumberInput(attrs={'class': 'form-control', 'step': 'any'}),
            'std_sigma_mps': forms.NumberInput(attrs={'class': 'form-control', 'step': 'any'}),
        }


TiBinFormSet = inlineformset_factory(
    HubClimate,
    TiBin,
    form=TiBinForm,
    extra=5,
    can_delete=True
)
