"""
Forms for turbines app.
"""
from django import forms
from .models import Layout, Turbine, WtgModel


class LayoutForm(forms.ModelForm):
    """Form for creating and editing layouts."""
    
    class Meta:
        model = Layout
        fields = ['name']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control'}),
        }


class TurbineForm(forms.ModelForm):
    """Form for creating and editing turbines."""
    
    class Meta:
        model = Turbine
        fields = [
            'local_id', 'role', 'x_m', 'y_m', 'z_base_m',
            'hub_height_m', 'rotor_d_m', 'model',
            'speed_class_override', 'ti_category_override'
        ]
        widgets = {
            'local_id': forms.TextInput(attrs={'class': 'form-control'}),
            'role': forms.Select(attrs={'class': 'form-control'}),
            'x_m': forms.NumberInput(attrs={'class': 'form-control', 'step': 'any'}),
            'y_m': forms.NumberInput(attrs={'class': 'form-control', 'step': 'any'}),
            'z_base_m': forms.NumberInput(attrs={'class': 'form-control', 'step': 'any'}),
            'hub_height_m': forms.NumberInput(attrs={'class': 'form-control', 'step': 'any'}),
            'rotor_d_m': forms.NumberInput(attrs={'class': 'form-control', 'step': 'any'}),
            'model': forms.Select(attrs={'class': 'form-control'}),
            'speed_class_override': forms.Select(attrs={'class': 'form-control'}),
            'ti_category_override': forms.Select(attrs={'class': 'form-control'}),
        }
