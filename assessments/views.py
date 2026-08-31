"""
Views for assessments app.
"""
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib import messages
from .models import Assessment, AssessmentTurbine, CheckResult
from .services import run_assessment_for_turbine


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
    
    return render(request, 'assessments/report.html', {
        'assessment': assessment,
        'assessment_turbines': assessment_turbines,
    })


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
