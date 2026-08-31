"""
Views for climate app (HubClimate and TiBins).
"""
import csv
import io
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import transaction
from .models import HubClimate, TiBin
from .forms import HubClimateForm, TiBinFormSet
from sites.models import Site


@login_required
def hub_climate_create(request, site_pk):
    """Create a new hub climate for a site."""
    site = get_object_or_404(Site, pk=site_pk)
    if request.method == 'POST':
        form = HubClimateForm(request.POST)
        if form.is_valid():
            hub_climate = form.save(commit=False)
            hub_climate.site = site
            hub_climate.save()
            messages.success(request, f'Hub climate "{hub_climate.name}" created successfully.')
            return redirect('climate:detail', pk=hub_climate.pk)
    else:
        form = HubClimateForm()
    
    return render(request, 'climate/form.html', {
        'form': form,
        'title': 'Create Hub Climate',
        'site': site
    })


def hub_climate_detail(request, pk):
    """Hub climate detail view."""
    hub_climate = get_object_or_404(HubClimate, pk=pk)
    ti_bins = hub_climate.ti_bins.all().order_by('v_center_mps')
    return render(request, 'climate/detail.html', {
        'hub_climate': hub_climate,
        'ti_bins': ti_bins
    })


@login_required
def hub_climate_edit(request, pk):
    """Edit an existing hub climate."""
    hub_climate = get_object_or_404(HubClimate, pk=pk)
    if request.method == 'POST':
        form = HubClimateForm(request.POST, instance=hub_climate)
        formset = TiBinFormSet(request.POST, instance=hub_climate)
        if form.is_valid() and formset.is_valid():
            hub_climate = form.save()
            formset.save()
            messages.success(request, f'Hub climate "{hub_climate.name}" updated successfully.')
            return redirect('climate:detail', pk=hub_climate.pk)
    else:
        form = HubClimateForm(instance=hub_climate)
        formset = TiBinFormSet(instance=hub_climate)
    
    return render(request, 'climate/edit.html', {
        'form': form,
        'formset': formset,
        'title': 'Edit Hub Climate',
        'hub_climate': hub_climate
    })


@login_required
def ti_bin_import_csv(request, hub_climate_pk):
    """Import TI bins from CSV."""
    hub_climate = get_object_or_404(HubClimate, pk=hub_climate_pk)
    
    if request.method == 'POST':
        csv_file = request.FILES.get('csv_file')
        replace_existing = request.POST.get('replace_existing') == 'on'
        
        if not csv_file:
            messages.error(request, 'No file uploaded.')
            return redirect('climate:detail', pk=hub_climate.pk)
        
        if not csv_file.name.endswith('.csv'):
            messages.error(request, 'File must be a CSV.')
            return redirect('climate:detail', pk=hub_climate.pk)
        
        # Check if bins already exist and replace not confirmed
        if hub_climate.ti_bins.exists() and not replace_existing:
            messages.warning(request, 'TI bins already exist. Check "Replace existing bins" to overwrite.')
            return redirect('climate:ti_bin_import', hub_climate_pk=hub_climate.pk)
        
        try:
            # Read CSV
            content = csv_file.read().decode('utf-8')
            csv_reader = csv.DictReader(io.StringIO(content))
            
            # Validate required columns
            required_cols = ['v_center_mps', 'hours', 'mean_sigma_mps']
            if not all(col in csv_reader.fieldnames for col in required_cols):
                messages.error(request, f'CSV must contain columns: {", ".join(required_cols)}')
                return redirect('climate:detail', pk=hub_climate.pk)
            
            errors = []
            bins_to_create = []
            
            for row_num, row in enumerate(csv_reader, start=2):
                try:
                    v_center = float(row['v_center_mps'])
                    hours = float(row['hours'])
                    mean_sigma = float(row['mean_sigma_mps'])
                    
                    # std_sigma_mps may be empty
                    std_sigma_str = row.get('std_sigma_mps', '').strip()
                    std_sigma = float(std_sigma_str) if std_sigma_str else None
                    
                    ti_bin = TiBin(
                        hub_climate=hub_climate,
                        v_center_mps=v_center,
                        hours=hours,
                        mean_sigma_mps=mean_sigma,
                        std_sigma_mps=std_sigma
                    )
                    bins_to_create.append(ti_bin)
                
                except (ValueError, KeyError) as e:
                    errors.append(f'Row {row_num}: {str(e)}')
            
            if errors:
                messages.error(request, 'Import failed with errors:')
                for error in errors:
                    messages.error(request, error)
                return redirect('climate:detail', pk=hub_climate.pk)
            
            # Delete existing bins if replacing
            with transaction.atomic():
                if replace_existing:
                    hub_climate.ti_bins.all().delete()
                
                for ti_bin in bins_to_create:
                    ti_bin.save()
            
            messages.success(request, f'Successfully imported {len(bins_to_create)} TI bins.')
            return redirect('climate:detail', pk=hub_climate.pk)
        
        except Exception as e:
            messages.error(request, f'Error processing CSV: {str(e)}')
            return redirect('climate:detail', pk=hub_climate.pk)
    
    return render(request, 'climate/import_csv.html', {
        'hub_climate': hub_climate,
        'has_existing_bins': hub_climate.ti_bins.exists()
    })
