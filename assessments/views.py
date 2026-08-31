"""
Views for assessments app.
"""
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import transaction
from .models import Assessment, AssessmentTurbine, CheckResult
from .services import run_assessment_for_turbine
from turbines.models import Layout, Turbine
from climate.models import HubClimate
from projects.models import ClassEnvelope


def assessment_list(request):
    """List all assessments."""
    assessments = Assessment.objects.all().select_related('project', 'site')
    return render(request, 'assessments/list.html', {'assessments': assessments})


def assessment_detail(request, pk):
    """Assessment detail view."""
    assessment = get_object_or_404(Assessment, pk=pk)
    return render(request, 'assessments/detail.html', {'assessment': assessment})


def assessment_report(request, pk):
    """Generate HTML report for assessment."""
    assessment = get_object_or_404(Assessment, pk=pk)
    assessment_turbines = assessment.assessment_turbines.all().prefetch_related('check_results')
    
    # Compute speed window for each turbine
    turbine_data = []
    for at in assessment_turbines:
        # Get speed window from engine output (stored in check results or compute)
        speed_window = None
        v_lo, v_hi = None, None
        
        if assessment.edition == 'ed4':
            # Ed4: [Vave, 2*Vave]
            v_lo = at.resolved_vave_mps
            v_hi = at.resolved_vave_mps * 2
        elif assessment.edition == 'ed3' and at.turbine.model:
            # Ed3: [0.6*Vr, Vout]
            v_lo = at.turbine.model.v_rated_mps * 0.6
            v_hi = at.turbine.model.v_out_mps
        
        speed_window = {'v_lo': v_lo, 'v_hi': v_hi}
        
        turbine_data.append({
            'assessment_turbine': at,
            'speed_window': speed_window
        })
    
    return render(request, 'assessments/report.html', {
        'assessment': assessment,
        'assessment_turbines': assessment_turbines,
        'turbine_data': turbine_data,
    })


@login_required
def run_assessment_view(request, pk):
    """Run assessment for all turbines."""
    assessment = get_object_or_404(Assessment, pk=pk)
    
    for assessment_turbine in assessment.assessment_turbines.all():
        try:
            run_assessment_for_turbine(assessment_turbine)
            messages.success(request, f"Assessment completed for {assessment_turbine.turbine.local_id}")
        except Exception as e:
            messages.error(request, f"Error assessing {assessment_turbine.turbine.local_id}: {e}")
    
    return redirect('assessments:detail', pk=pk)


@login_required
def layout_assessment_setup(request, layout_pk):
    """Setup assessment for a layout."""
    layout = get_object_or_404(Layout, pk=layout_pk)
    site = layout.site
    project = site.project
    
    # Get or create class envelope
    class_envelope, created = ClassEnvelope.objects.get_or_create(project=project)
    
    # Get available hub climates for this site
    hub_climates = HubClimate.objects.filter(site=site, turbine__isnull=True)
    
    if request.method == 'POST':
        hub_climate_id = request.POST.get('hub_climate_id')
        edition = request.POST.get('edition', 'ed4')
        
        if not hub_climate_id:
            messages.error(request, 'Please select a hub climate.')
            return render(request, 'assessments/layout_setup.html', {
                'layout': layout,
                'hub_climates': hub_climates
            })
        
        hub_climate = get_object_or_404(HubClimate, pk=hub_climate_id)
        
        # Get all new_scored turbines
        turbines = layout.turbines.filter(role=Turbine.ROLE_NEW_SCORED)
        
        if not turbines.exists():
            messages.error(request, 'No turbines with role "new_scored" found in this layout.')
            return redirect('turbines:layout_detail', pk=layout.pk)
        
        # Create assessment
        with transaction.atomic():
            # Check if class envelope was just created (Django defaults used)
            class_envelope_used_defaults = created
            
            assessment = Assessment.objects.create(
                project=project,
                site=site,
                name=f"{layout.name} - {hub_climate.name}",
                edition=edition,
                class_envelope_snapshot={
                    'vref_i': class_envelope.vref_i,
                    'vref_ii': class_envelope.vref_ii,
                    'vref_iii': class_envelope.vref_iii,
                    'iref_a_plus': class_envelope.iref_a_plus,
                    'iref_a': class_envelope.iref_a,
                    'iref_b': class_envelope.iref_b,
                    'iref_c': class_envelope.iref_c,
                    'vave_over_vref': class_envelope.vave_over_vref,
                    'class_envelope_django_defaults': class_envelope_used_defaults
                }
            )
            
            # Create assessment turbines
            for turbine in turbines:
                speed_class = turbine.get_speed_class() or 'II'
                ti_category = turbine.get_ti_category() or 'B'
                
                vref = class_envelope.get_vref(speed_class)
                iref = class_envelope.get_iref(ti_category)
                vave = vref * class_envelope.vave_over_vref
                
                AssessmentTurbine.objects.create(
                    assessment=assessment,
                    turbine=turbine,
                    hub_climate=hub_climate,
                    resolved_vref_mps=vref,
                    resolved_iref=iref,
                    resolved_vave_mps=vave,
                    cct=1.0,
                    apply_density_to_v50=False,
                    wohler_exponents=[4, 10]
                )
        
        # Run assessment
        for assessment_turbine in assessment.assessment_turbines.all():
            try:
                run_assessment_for_turbine(assessment_turbine)
            except Exception as e:
                messages.error(request, f"Error assessing {assessment_turbine.turbine.local_id}: {e}")
        
        messages.success(request, f'Assessment created and run for layout "{layout.name}".')
        return redirect('assessments:layout_result', layout_pk=layout.pk, assessment_pk=assessment.pk)
    
    return render(request, 'assessments/layout_setup.html', {
        'layout': layout,
        'hub_climates': hub_climates
    })


def layout_assessment_result(request, layout_pk, assessment_pk):
    """View assessment results for a layout."""
    layout = get_object_or_404(Layout, pk=layout_pk)
    assessment = get_object_or_404(Assessment, pk=assessment_pk)
    assessment_turbines = assessment.assessment_turbines.all().prefetch_related('check_results')
    
    return render(request, 'assessments/layout_result.html', {
        'layout': layout,
        'assessment': assessment,
        'assessment_turbines': assessment_turbines,
    })
