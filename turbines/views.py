"""
Views for turbines app (layouts and turbines).
"""
import csv
import io
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib import messages
from django.db import transaction
from .models import Layout, Turbine, WtgModel
from .forms import LayoutForm, TurbineForm
from sites.models import Site


def layout_create(request, site_pk):
    """Create a new layout for a site."""
    site = get_object_or_404(Site, pk=site_pk)
    if request.method == 'POST':
        form = LayoutForm(request.POST)
        if form.is_valid():
            layout = form.save(commit=False)
            layout.site = site
            layout.save()
            messages.success(request, f'Layout "{layout.name}" created successfully.')
            return redirect('turbines:layout_detail', pk=layout.pk)
    else:
        form = LayoutForm()
    
    return render(request, 'turbines/layout_form.html', {
        'form': form,
        'title': 'Create Layout',
        'site': site
    })


def layout_detail(request, pk):
    """Layout detail view with turbine table."""
    layout = get_object_or_404(Layout, pk=pk)
    turbines = layout.turbines.all().select_related('model')
    return render(request, 'turbines/layout_detail.html', {
        'layout': layout,
        'turbines': turbines
    })


def layout_edit(request, pk):
    """Edit an existing layout."""
    layout = get_object_or_404(Layout, pk=pk)
    if request.method == 'POST':
        form = LayoutForm(request.POST, instance=layout)
        if form.is_valid():
            layout = form.save()
            messages.success(request, f'Layout "{layout.name}" updated successfully.')
            return redirect('turbines:layout_detail', pk=layout.pk)
    else:
        form = LayoutForm(instance=layout)
    
    return render(request, 'turbines/layout_form.html', {
        'form': form,
        'title': 'Edit Layout',
        'layout': layout
    })


def turbine_create(request, layout_pk):
    """Create a new turbine for a layout."""
    layout = get_object_or_404(Layout, pk=layout_pk)
    if request.method == 'POST':
        form = TurbineForm(request.POST)
        if form.is_valid():
            turbine = form.save(commit=False)
            turbine.layout = layout
            try:
                turbine.save()
                messages.success(request, f'Turbine "{turbine.local_id}" added successfully.')
                return redirect('turbines:layout_detail', pk=layout.pk)
            except Exception as e:
                messages.error(request, f'Error saving turbine: {e}')
    else:
        form = TurbineForm()
    
    return render(request, 'turbines/turbine_form.html', {
        'form': form,
        'title': 'Add Turbine',
        'layout': layout
    })


def turbine_edit(request, pk):
    """Edit an existing turbine."""
    turbine = get_object_or_404(Turbine, pk=pk)
    if request.method == 'POST':
        form = TurbineForm(request.POST, instance=turbine)
        if form.is_valid():
            turbine = form.save()
            messages.success(request, f'Turbine "{turbine.local_id}" updated successfully.')
            return redirect('turbines:layout_detail', pk=turbine.layout.pk)
    else:
        form = TurbineForm(instance=turbine)
    
    return render(request, 'turbines/turbine_form.html', {
        'form': form,
        'title': 'Edit Turbine',
        'turbine': turbine
    })


def turbine_delete(request, pk):
    """Delete a turbine."""
    turbine = get_object_or_404(Turbine, pk=pk)
    layout_pk = turbine.layout.pk
    if request.method == 'POST':
        turbine.delete()
        messages.success(request, f'Turbine "{turbine.local_id}" deleted successfully.')
    return redirect('turbines:layout_detail', pk=layout_pk)


def turbine_import_csv(request, layout_pk):
    """Import turbines from CSV."""
    layout = get_object_or_404(Layout, pk=layout_pk)
    
    if request.method == 'POST':
        csv_file = request.FILES.get('csv_file')
        if not csv_file:
            messages.error(request, 'No file uploaded.')
            return redirect('turbines:layout_detail', pk=layout.pk)
        
        if not csv_file.name.endswith('.csv'):
            messages.error(request, 'File must be a CSV.')
            return redirect('turbines:layout_detail', pk=layout.pk)
        
        try:
            # Read CSV
            content = csv_file.read().decode('utf-8')
            csv_reader = csv.DictReader(io.StringIO(content))
            
            # Validate required columns
            required_cols = ['local_id', 'x_m', 'y_m', 'z_base_m', 'hub_height_m', 'rotor_d_m']
            if not all(col in csv_reader.fieldnames for col in required_cols):
                messages.error(request, f'CSV must contain columns: {", ".join(required_cols)}')
                return redirect('turbines:layout_detail', pk=layout.pk)
            
            errors = []
            turbines_to_create = []
            existing_local_ids = set(layout.turbines.values_list('local_id', flat=True))
            new_local_ids = set()
            
            for row_num, row in enumerate(csv_reader, start=2):
                try:
                    local_id = row['local_id'].strip()
                    
                    # Check for duplicates
                    if local_id in existing_local_ids or local_id in new_local_ids:
                        errors.append(f'Row {row_num}: Duplicate local_id "{local_id}"')
                        continue
                    
                    new_local_ids.add(local_id)
                    
                    # Parse role
                    role = row.get('role', 'new_scored').strip()
                    if role not in ['new_scored', 'existing_wake_source']:
                        role = 'new_scored'
                    
                    # Parse model_name
                    model = None
                    model_name = row.get('model_name', '').strip()
                    if model_name:
                        try:
                            model = WtgModel.objects.get(name=model_name)
                        except WtgModel.DoesNotExist:
                            # Create stub model if rotor_d and hub_height present
                            rotor_d = float(row['rotor_d_m'])
                            hub_height = float(row['hub_height_m'])
                            model = WtgModel.objects.create(
                                name=model_name,
                                rotor_d_m=rotor_d,
                                hub_height_default_m=hub_height,
                                v_in_mps=3.0,
                                v_rated_mps=11.0,
                                v_out_mps=25.0,
                                ct_status=WtgModel.CT_STATUS_MISSING
                            )
                            messages.warning(request, f'Row {row_num}: Created stub model "{model_name}" (Ct missing)')
                    
                    turbine = Turbine(
                        layout=layout,
                        local_id=local_id,
                        role=role,
                        x_m=float(row['x_m']),
                        y_m=float(row['y_m']),
                        z_base_m=float(row['z_base_m']),
                        hub_height_m=float(row['hub_height_m']),
                        rotor_d_m=float(row['rotor_d_m']),
                        model=model
                    )
                    turbines_to_create.append(turbine)
                
                except (ValueError, KeyError) as e:
                    errors.append(f'Row {row_num}: {str(e)}')
            
            # All or nothing: if errors, don't import
            if errors:
                messages.error(request, 'Import failed with errors:')
                for error in errors:
                    messages.error(request, error)
                return redirect('turbines:layout_detail', pk=layout.pk)
            
            # Save all turbines
            with transaction.atomic():
                for turbine in turbines_to_create:
                    turbine.save()
            
            messages.success(request, f'Successfully imported {len(turbines_to_create)} turbines.')
            return redirect('turbines:layout_detail', pk=layout.pk)
        
        except Exception as e:
            messages.error(request, f'Error processing CSV: {str(e)}')
            return redirect('turbines:layout_detail', pk=layout.pk)
    
    return render(request, 'turbines/import_csv.html', {'layout': layout})
