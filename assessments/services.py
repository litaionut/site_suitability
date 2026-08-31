"""
Assessment service layer for running assessments.
"""
from .models import Assessment, AssessmentTurbine, CheckResult
from .engine import run_assessment, calculate_effective_turbulence_slice1
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
    
    # ===== SLICE 1: EFFECTIVE TURBULENCE (turbulence_ieff) =====
    # Get all turbines in layout for wake modeling
    layout = turbine.layout
    all_layout_turbines = layout.turbines.filter(
        rotor_d_m__gt=0
    ).select_related('model')
    
    # Prepare target turbine data
    target_turbine_data = {
        'x_m': turbine.x_m,
        'y_m': turbine.y_m,
        'rotor_d_m': turbine.rotor_d_m,
        'ct_curve': []
    }
    
    if turbine.model:
        ct_points = turbine.model.ct_curve_points.all().order_by('v_mps')
        target_turbine_data['ct_curve'] = [
            {'v_mps': p.v_mps, 'ct': p.ct} for p in ct_points
        ]
    
    # Prepare neighbor data (all other turbines with rotor diameter)
    neighbors_data = []
    for neighbor in all_layout_turbines:
        if neighbor.id == turbine.id:
            continue  # Skip self
        
        neighbor_data = {
            'x_m': neighbor.x_m,
            'y_m': neighbor.y_m,
            'rotor_d_m': neighbor.rotor_d_m,
            'ct_curve': []
        }
        
        if neighbor.model:
            ct_points = neighbor.model.ct_curve_points.all().order_by('v_mps')
            neighbor_data['ct_curve'] = [
                {'v_mps': p.v_mps, 'ct': p.ct} for p in ct_points
            ]
        
        neighbors_data.append(neighbor_data)
    
    # Get sector frequencies if available
    sector_frequencies = None
    sector_weibulls = hub_climate.sector_weibulls.all().order_by('sector_from_deg')
    if sector_weibulls.exists():
        # Map SectorWeibull data to 30° sector indices
        sector_freq_list = []
        for sw in sector_weibulls:
            # Calculate which 30° sector(s) this SectorWeibull overlaps
            # For simplicity, assign frequency to the sector containing the midpoint
            sector_center = (sw.sector_from_deg + sw.sector_to_deg) / 2
            sector_idx = int(sector_center / 30) % 12
            sector_freq_list.append({
                'sector_idx': sector_idx,
                'frequency': sw.frequency
            })
        sector_frequencies = sector_freq_list
    
    # Calculate effective turbulence
    bins_in_window = []
    v_lo, v_hi = result['speed_range']
    for bin_data in ti_bins_data:
        # Check if bin is in window (copied from engine logic)
        v_center = bin_data['v_center']
        if (v_lo - 1e-9) <= v_center <= (v_hi + 1e-9):
            bins_in_window.append(bin_data)
    
    if len(bins_in_window) > 0:
        eff_turb_check = calculate_effective_turbulence_slice1(
            bins_in_window,
            assessment_turbine.resolved_iref,
            result['cct'],
            target_turbine_data,
            neighbors_data,
            sector_frequencies=sector_frequencies,
            wohler_exponents=assessment_turbine.wohler_exponents or [4, 10],
            sector_width_deg=30
        )
        
        # Persist effective turbulence check
        CheckResult.objects.create(
            assessment_turbine=assessment_turbine,
            check_id=eff_turb_check['check_id'],
            status=eff_turb_check['status'],
            value=eff_turb_check.get('value'),
            limit=eff_turb_check.get('limit'),
            units=eff_turb_check.get('units', ''),
            detail=eff_turb_check.get('detail', {}),
            flags=eff_turb_check.get('flags', []),
        )
        
        # Update overall status if effective turbulence is worse
        status_priority = {'Fail': 3, 'Warn': 2, 'Pass': 1}
        if status_priority[eff_turb_check['status']] > status_priority[result['overall']]:
            result['overall'] = eff_turb_check['status']
    
    # Update assessment overall status and flags
    assessment.overall_status = result['overall']
    assessment.flags = result['flags']
    assessment.save()
    
    return result
