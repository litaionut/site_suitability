"""
Views for sites app.
"""
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib import messages
from .models import Site
from .forms import SiteForm
from projects.models import Project


def site_create(request, project_uuid):
    """Create a new site for a project."""
    project = get_object_or_404(Project, uuid=project_uuid)
    if request.method == 'POST':
        form = SiteForm(request.POST)
        if form.is_valid():
            site = form.save(commit=False)
            site.project = project
            site.save()
            messages.success(request, f'Site "{site.name}" created successfully.')
            return redirect('sites:detail', pk=site.pk)
    else:
        form = SiteForm()
    
    return render(request, 'sites/form.html', {'form': form, 'title': 'Create Site', 'project': project})


def site_detail(request, pk):
    """Site detail view."""
    site = get_object_or_404(Site, pk=pk)
    layouts = site.layouts.all()
    hub_climates = site.hub_climates.filter(turbine__isnull=True)
    return render(request, 'sites/detail.html', {
        'site': site,
        'layouts': layouts,
        'hub_climates': hub_climates
    })


def site_edit(request, pk):
    """Edit an existing site."""
    site = get_object_or_404(Site, pk=pk)
    if request.method == 'POST':
        form = SiteForm(request.POST, instance=site)
        if form.is_valid():
            site = form.save()
            messages.success(request, f'Site "{site.name}" updated successfully.')
            return redirect('sites:detail', pk=site.pk)
    else:
        form = SiteForm(instance=site)
    
    return render(request, 'sites/form.html', {'form': form, 'title': 'Edit Site', 'site': site})


def site_compare_layouts(request, pk):
    """Compare all layouts on a site."""
    site = get_object_or_404(Site, pk=pk)
    layouts = site.layouts.all()
    
    # For each layout, get the worst status from assessments
    layout_data = []
    for layout in layouts:
        # Get the most recent assessment for this layout
        assessments = []
        for turbine in layout.turbines.filter(role='new_scored'):
            turbine_assessments = turbine.assessmentturbine_set.select_related(
                'assessment'
            ).order_by('-assessment__created_at')
            if turbine_assessments.exists():
                assessments.append(turbine_assessments.first())
        
        if assessments:
            # Find worst status
            status_priority = {'Fail': 3, 'Warn': 2, 'Pass': 1}
            worst_status = 'Pass'
            worst_check = None
            
            for at in assessments:
                checks = at.check_results.all()
                for check in checks:
                    if status_priority.get(check.status, 0) > status_priority.get(worst_status, 0):
                        worst_status = check.status
                        worst_check = check.get_check_id_display()
            
            layout_data.append({
                'layout': layout,
                'overall_status': worst_status,
                'worst_check': worst_check,
                'turbine_count': layout.turbines.count()
            })
        else:
            layout_data.append({
                'layout': layout,
                'overall_status': None,
                'worst_check': None,
                'turbine_count': layout.turbines.count()
            })
    
    return render(request, 'sites/compare_layouts.html', {
        'site': site,
        'layout_data': layout_data
    })
