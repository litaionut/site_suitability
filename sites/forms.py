"""
Forms for sites app.
"""
from django import forms
from .models import Site


class SiteForm(forms.ModelForm):
    """Form for creating and editing sites."""
    
    class Meta:
        model = Site
        fields = ['name', 'center_lon_deg', 'center_lat_deg', 'default_complexity']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control'}),
            'center_lon_deg': forms.NumberInput(attrs={'class': 'form-control', 'step': 'any'}),
            'center_lat_deg': forms.NumberInput(attrs={'class': 'form-control', 'step': 'any'}),
            'default_complexity': forms.Select(attrs={'class': 'form-control'}),
        }
        labels = {
            'center_lon_deg': 'Center Longitude (°)',
            'center_lat_deg': 'Center Latitude (°)',
            'default_complexity': 'Default Terrain Complexity',
        }
