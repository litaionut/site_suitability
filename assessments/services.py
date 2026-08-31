"""
Assessment service layer for running assessments.
"""
from .models import Assessment, AssessmentTurbine, CheckResult
from .engine import run_assessment
from turbines.models import Turbine


def run_assessment_for_turbine(assessment_turbine: AssessmentTurbine):
    """
    Run assessment for a single turbine.
    Maps Django models to engine input format and persists results.
    """
    assessment = assessment_turbine.assessment
    turbine = assessment_turbine.turbine
    hub_climate = assessment_turbine.hub_climate
    
    # Validate turbine role
    if turbine.role != Turbine.ROLE_NEW_SCORED:
        raise ValueError(f"Turbine {turbine.local_id} must have role 'new_scored', not '{turbine.role}'")
    
    # Get TI bins
    ti_bins_data = []
    for ti_bin in hub_climate.ti_bins.all().order_by('v_center_mps'):
        ti_bins_data.append({
            'v_center': ti_bin.v_center_mps,
            'hours': ti_bin.hours,
            'mean_sigma': ti_bin.mean_sigma_mps,
            'std_sigma': ti_bin.std_sigma_mps,
            'shear_alpha_override': ti_bin.shear_alpha_override,
            'inflow_angle_deg_override': ti_bin.inflow_angle_deg_override,
        })
    
    # Prepare engine input
    engine_input = {
        'edition': assessment.edition,
        'vref': assessment_turbine.resolved_vref_mps,
        'iref': assessment_turbine.resolved_iref,
        'vave': assessment_turbine.resolved_vave_mps,
        'v50': hub_climate.v50_mps,
        'rho': hub_climate.rho_kgm3,
        'apply_density_to_v50': assessment_turbine.apply_density_to_v50,
        'complexity': turbine.layout.site.default_complexity,
        'bin_width': hub_climate.bin_width_mps,
        'period_hours': hub_climate.period_hours,
        'ti_bins': ti_bins_data,
        'shear_alpha': hub_climate.shear_alpha,
        'inflow_angle_deg': hub_climate.inflow_angle_deg,
        'wohler_exponents': assessment_turbine.wohler_exponents or [4, 10],
    }
    
    # Add v_rated and v_out if ed3
    if assessment.edition == 'ed3':
        if turbine.model:
            engine_input['v_rated'] = turbine.model.v_rated_mps
            engine_input['v_out'] = turbine.model.v_out_mps
        else:
            raise ValueError(f"Turbine {turbine.local_id} requires a model for ed3 assessment")
    
    # Run engine
    result = run_assessment(engine_input)
    
    if 'error' in result:
        raise ValueError(f"Assessment error: {result['error']}")
    
    # Update assessment turbine CCT
    assessment_turbine.cct = result['cct']
    assessment_turbine.save()
    
    # Delete existing check results
    assessment_turbine.check_results.all().delete()
    
    # Persist check results
    for check in result['checks']:
        CheckResult.objects.create(
            assessment_turbine=assessment_turbine,
            check_id=check['check_id'],
            status=check['status'],
            value=check.get('value'),
            limit=check.get('limit'),
            units=check.get('units', ''),
            detail=check.get('detail', {}),
            flags=check.get('flags', []),
        )
    
    # Update assessment overall status and flags
    assessment.overall_status = result['overall']
    assessment.flags = result['flags']
    assessment.save()
    
    return result
