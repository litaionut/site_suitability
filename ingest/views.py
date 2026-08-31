"""
Views for site package ingest.
"""
import json
import uuid
from django.shortcuts import render, redirect
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
from django.db import transaction
from django.core.cache import cache

from .parsers import parse_file, ParseError
from .serializers import SitePackageSerializer, Gap
from projects.models import Project, ClassEnvelope
from sites.models import Site
from turbines.models import Layout, Turbine, WtgModel, PowerCurvePoint, CtCurvePoint
from climate.models import HubClimate, TiBin, SectorWeibull
from assessments.models import Assessment, AssessmentTurbine
from assessments.services import run_assessment_for_turbine


def upload_page(request):
    """Display upload page."""
    return render(request, 'ingest/upload.html')


@require_http_methods(["POST"])
def upload_file(request):
    """
    POST endpoint to upload and parse site package file.
    Returns JSON with parsed package and preview URL.
    """
    if 'file' not in request.FILES:
        return JsonResponse({'status': 'error', 'message': 'No file uploaded'}, status=400)

    uploaded_file = request.FILES['file']
    filename = uploaded_file.name

    try:
        # Parse file
        package_data = parse_file(uploaded_file, filename)

        # Validate
        serializer = SitePackageSerializer(package_data)
        is_valid = serializer.validate()

        # Store in cache with session ID
        session_id = str(uuid.uuid4())
        cache_key = f'ingest_package_{session_id}'
        cache.set(cache_key, package_data, timeout=3600)  # 1 hour

        return JsonResponse({
            'status': 'success',
            'session_id': session_id,
            'package': package_data,
            'gaps': serializer.get_gaps(),
            'can_commit': is_valid,
            'preview_url': f'/ingest/preview/{session_id}/'
        })

    except ParseError as e:
        return JsonResponse({'status': 'error', 'message': str(e)}, status=400)
    except Exception as e:
        return JsonResponse({'status': 'error', 'message': f'Unexpected error: {str(e)}'}, status=500)


def preview_package(request, session_id):
    """Display preview of parsed site package."""
    cache_key = f'ingest_package_{session_id}'
    package_data = cache.get(cache_key)

    if not package_data:
        return render(request, 'ingest/error.html', {
            'message': 'Session expired or invalid. Please upload the file again.'
        })

    # Re-validate
    serializer = SitePackageSerializer(package_data)
    is_valid = serializer.validate()
    gaps = serializer.get_gaps()

    # Count gaps by severity
    gap_counts = {
        'run_blocker': sum(1 for g in gaps if g['severity'] == 'run_blocker'),
        'flag': sum(1 for g in gaps if g['severity'] == 'flag'),
        'store_only_missing': sum(1 for g in gaps if g['severity'] == 'store_only_missing'),
        'unmapped_column': sum(1 for g in gaps if g['severity'] == 'unmapped_column'),
        'invalid': sum(1 for g in gaps if g['severity'] == 'invalid'),
    }

    context = {
        'session_id': session_id,
        'package': package_data,
        'gaps': gaps,
        'gap_counts': gap_counts,
        'can_commit': is_valid,
        'turbine_count': len(package_data.get('layout', {}).get('turbines', [])),
        'model_count': len(package_data.get('wtg_models', [])),
        'climate_count': len(package_data.get('hub_climates', [])),
    }

    return render(request, 'ingest/preview.html', context)


@require_http_methods(["POST"])
def commit_package(request, session_id):
    """
    POST endpoint to commit site package to database.
    Creates all necessary Django model instances.
    """
    cache_key = f'ingest_package_{session_id}'
    package_data = cache.get(cache_key)

    if not package_data:
        return JsonResponse({
            'status': 'error',
            'message': 'Session expired or invalid'
        }, status=400)

    # Validate before commit
    serializer = SitePackageSerializer(package_data)
    is_valid = serializer.validate()

    if not is_valid:
        gaps = serializer.get_gaps()
        blocker_gaps = [g for g in gaps if g['severity'] == 'run_blocker']
        return JsonResponse({
            'status': 'error',
            'message': f'Cannot commit: {len(blocker_gaps)} run_blocker gap(s) present',
            'gaps': blocker_gaps
        }, status=400)

    try:
        with transaction.atomic():
            # Create Project
            project_data = package_data.get('project', {})
            project = Project.objects.create(
                name=project_data.get('name', 'Imported Project'),
                notes=project_data.get('notes', '')
            )

            # Create ClassEnvelope (Django defaults if null)
            class_env_data = package_data.get('class_envelope')
            if class_env_data:
                class_envelope = ClassEnvelope.objects.create(
                    project=project,
                    vref_i=class_env_data.get('vref_i', 50.0),
                    vref_ii=class_env_data.get('vref_ii', 42.5),
                    vref_iii=class_env_data.get('vref_iii', 37.5),
                    iref_a_plus=class_env_data.get('iref_a_plus', 0.18),
                    iref_a=class_env_data.get('iref_a', 0.16),
                    iref_b=class_env_data.get('iref_b', 0.14),
                    iref_c=class_env_data.get('iref_c', 0.12),
                    vave_over_vref=class_env_data.get('vave_over_vref', 0.2)
                )
            else:
                # Use Django model defaults
                class_envelope = ClassEnvelope.objects.create(project=project)

            # Create Site
            site_data = package_data.get('site', {})
            site = Site.objects.create(
                project=project,
                name=site_data.get('name', 'Imported Site'),
                center_lon_deg=site_data.get('center_lon_deg', 0.0),
                center_lat_deg=site_data.get('center_lat_deg', 0.0),
                default_complexity=site_data.get('default_complexity', 'simple')
            )

            # Create WTG Models
            wtg_model_map = {}
            for model_data in package_data.get('wtg_models', []):
                model_name = model_data.get('name')
                if not model_name:
                    continue

                # Check if model already exists
                existing_model = WtgModel.objects.filter(name=model_name).first()
                if existing_model:
                    wtg_model = existing_model
                else:
                    # Don't default speed_class or ti_category without explicit values
                    speed_class = model_data.get('default_speed_class')
                    ti_category = model_data.get('default_ti_category')
                    
                    wtg_model = WtgModel.objects.create(
                        name=model_name,
                        rotor_d_m=model_data.get('rotor_d_m'),
                        hub_height_default_m=model_data.get('hub_height_default_m'),
                        v_in_mps=model_data.get('v_in_mps'),
                        v_rated_mps=model_data.get('v_rated_mps'),
                        v_out_mps=model_data.get('v_out_mps'),
                        default_speed_class=speed_class if speed_class else 'II',
                        default_ti_category=ti_category if ti_category else 'B',
                        ct_status='missing' if not model_data.get('ct_curve') else 'ok'
                    )

                    # Create Power Curve Points
                    for pc_point in model_data.get('power_curve', []):
                        PowerCurvePoint.objects.create(
                            wtg_model=wtg_model,
                            v_mps=pc_point['v_mps'],
                            p_kw=pc_point['p_kw']
                        )

                    # Create Ct Curve Points (if present)
                    for ct_point in model_data.get('ct_curve', []):
                        CtCurvePoint.objects.create(
                            wtg_model=wtg_model,
                            v_mps=ct_point['v_mps'],
                            ct=ct_point['ct']
                        )

                    # Update Ct status based on curve
                    wtg_model.update_ct_status()
                    wtg_model.save()

                wtg_model_map[model_name] = wtg_model

            # Create Layout
            layout_data = package_data.get('layout', {})
            layout = Layout.objects.create(
                site=site,
                name=layout_data.get('name', 'Imported Layout')
            )

            # Create Turbines
            for turbine_data in layout_data.get('turbines', []):
                model_name = turbine_data.get('model_name')
                wtg_model = wtg_model_map.get(model_name) if model_name else None

                Turbine.objects.create(
                    layout=layout,
                    local_id=turbine_data.get('local_id'),
                    role=turbine_data.get('role', 'new_scored'),
                    x_m=turbine_data.get('x_m'),
                    y_m=turbine_data.get('y_m'),
                    z_base_m=turbine_data.get('z_base_m'),
                    hub_height_m=turbine_data.get('hub_height_m'),
                    rotor_d_m=turbine_data.get('rotor_d_m'),
                    model=wtg_model
                )

            # Create Hub Climates
            for climate_data in package_data.get('hub_climates', []):
                # Find turbine if specified
                turbine = None
                turbine_local_id = climate_data.get('turbine_local_id')
                if turbine_local_id:
                    turbine = Turbine.objects.filter(
                        layout=layout,
                        local_id=turbine_local_id
                    ).first()

                # Use Django defaults for optional fields if not provided
                hub_climate = HubClimate.objects.create(
                    site=site,
                    turbine=turbine,
                    name=climate_data.get('name', 'Imported Climate'),
                    period_hours=climate_data.get('period_hours') or 8760.0,
                    bin_width_mps=climate_data.get('bin_width_mps') or 1.0,
                    rho_kgm3=climate_data.get('rho_kgm3') or 1.225,
                    v50_mps=climate_data.get('v50_mps'),
                    shear_alpha=climate_data.get('shear_alpha'),
                    inflow_angle_deg=climate_data.get('inflow_angle_deg')
                )

                # Create TI Bins
                for ti_bin_data in climate_data.get('ti_bins', []):
                    TiBin.objects.create(
                        hub_climate=hub_climate,
                        v_center_mps=ti_bin_data.get('v_center_mps'),
                        hours=ti_bin_data.get('hours'),
                        mean_sigma_mps=ti_bin_data.get('mean_sigma_mps'),
                        std_sigma_mps=ti_bin_data.get('std_sigma_mps')
                    )

                # Create Sector Weibull (if present)
                for sector_data in climate_data.get('sector_weibull', []):
                    SectorWeibull.objects.create(
                        hub_climate=hub_climate,
                        sector_from_deg=sector_data.get('sector_from_deg'),
                        sector_to_deg=sector_data.get('sector_to_deg'),
                        frequency=sector_data.get('frequency'),
                        A=sector_data.get('A'),
                        k=sector_data.get('k')
                    )

            # Run Slice 0+1 assessment for new_scored turbines
            # Get the first hub_climate for the assessment
            first_hub_climate = HubClimate.objects.filter(site=site).first()
            
            if not first_hub_climate:
                raise ValueError("No hub climate data found for assessment")
            
            # Create Assessment with class envelope snapshot
            class_envelope_snapshot = {
                'vref_i': class_envelope.vref_i,
                'vref_ii': class_envelope.vref_ii,
                'vref_iii': class_envelope.vref_iii,
                'iref_a_plus': class_envelope.iref_a_plus,
                'iref_a': class_envelope.iref_a,
                'iref_b': class_envelope.iref_b,
                'iref_c': class_envelope.iref_c,
                'vave_over_vref': class_envelope.vave_over_vref
            }
            
            assessment = Assessment.objects.create(
                project=project,
                site=site,
                name=f"Assessment for {layout.name}",
                edition='ed4',
                class_envelope_snapshot=class_envelope_snapshot
            )

            # Create AssessmentTurbine for each new_scored turbine and run assessment
            assessment_results = []
            for turbine in layout.turbines.filter(role=Turbine.ROLE_NEW_SCORED):
                assessment_turbine = AssessmentTurbine.objects.create(
                    assessment=assessment,
                    turbine=turbine,
                    hub_climate=first_hub_climate
                )
                
                try:
                    # Run assessment to execute turbulence_ieff with persisted neighbors+Ct
                    run_assessment_for_turbine(assessment_turbine)
                    assessment_results.append({
                        'turbine_id': turbine.local_id,
                        'status': 'completed'
                    })
                except Exception as e:
                    assessment_results.append({
                        'turbine_id': turbine.local_id,
                        'status': 'failed',
                        'error': str(e)
                    })

            # Clear cache
            cache.delete(cache_key)

            return JsonResponse({
                'status': 'success',
                'project_uuid': str(project.uuid),
                'site_id': site.id,
                'layout_id': layout.id,
                'turbine_count': layout.turbines.count(),
                'assessment_id': assessment.id,
                'assessment_results': assessment_results,
                'redirect_url': f'/assessments/{assessment.id}/'
            })

    except Exception as e:
        return JsonResponse({
            'status': 'error',
            'message': f'Failed to commit: {str(e)}'
        }, status=500)
