"""
Calculation engine for IEC 61400-1 inspired site suitability assessment.
Screening against a user-editable class envelope, not a certified IEC 61400-1 assessment.

Pure Python, no database required.
"""
import math


def calculate_ntm_sigma(v_mps, iref):
    """
    Calculate NTM representative turbulence intensity.
    σ1(V) = Iref * (0.75*V + 5.6) m/s
    """
    return iref * (0.75 * v_mps + 5.6)


def calculate_sigma_90(mean_sigma, std_sigma=None, cov=0.3):
    """
    Calculate 90th percentile sigma.
    σ90 = mean_σ + 1.28*σσ
    If σσ missing: σσ=0.3*mean_σ (flag assumed_cov_0_3)
    """
    if std_sigma is None:
        std_sigma = cov * mean_sigma
        assumed_cov = True
    else:
        assumed_cov = False
    
    sigma_90 = mean_sigma + 1.28 * std_sigma
    return sigma_90, assumed_cov


def calculate_rayleigh_distribution(vave, bin_centers, bin_width):
    """
    Calculate Rayleigh distribution probabilities for bins.
    F(V) = 1 - exp(-π/4 * (V/Vave)^2) for V>0
    p_R,i = F(hi) - F(lo) with ΔV = bin_width
    """
    probabilities = []
    
    for v_center in bin_centers:
        v_lo = v_center - bin_width / 2
        v_hi = v_center + bin_width / 2
        
        if v_lo < 0:
            v_lo = 0
        
        if v_lo > 0:
            f_lo = 1 - math.exp(-math.pi / 4 * (v_lo / vave) ** 2)
        else:
            f_lo = 0
        
        f_hi = 1 - math.exp(-math.pi / 4 * (v_hi / vave) ** 2)
        
        p_r = f_hi - f_lo
        probabilities.append(p_r)
    
    return probabilities


def get_speed_window(edition, vave, v_rated=None, v_out=None):
    """
    Determine speed window based on edition.
    ed4: [Vave, 2*Vave] using DESIGN Vave (not site mean)
    ed3: [0.6*Vr, Vout]; Vr and Vout required
    
    Returns: (v_lo, v_hi, error_message)
    """
    if edition == 'ed4':
        return (vave, 2 * vave, None)
    elif edition == 'ed3':
        if v_rated is None or v_out is None:
            return (None, None, "ed3 requires v_rated and v_out")
        return (0.6 * v_rated, v_out, None)
    else:
        return (None, None, f"Unknown edition: {edition}")


def bin_in_window(v_center, v_lo, v_hi, bin_width, tolerance=1e-9):
    """
    Check if bin center is in the window.
    Include bin i in window iff V_lo ≤ V_center ≤ V_hi (with tolerance)
    """
    return (v_lo - tolerance) <= v_center <= (v_hi + tolerance)


def calculate_energy_weights(bins_in_window):
    """
    Calculate energy weights for bins.
    w_i = hours_i * V_i^3
    
    Returns: list of weights, total weight
    """
    weights = []
    total_weight = 0
    
    for bin_data in bins_in_window:
        w = bin_data['hours'] * (bin_data['v_center'] ** 3)
        weights.append(w)
        total_weight += w
    
    return weights, total_weight


def calculate_energy_weighted_value(bins_in_window, param_name):
    """
    Calculate energy-weighted value of a parameter.
    α_ew = Σ(w_i * α_i) / Σ(w_i)
    """
    weights, total_weight = calculate_energy_weights(bins_in_window)
    
    if total_weight == 0:
        return None
    
    weighted_sum = 0
    for i, bin_data in enumerate(bins_in_window):
        value = bin_data.get(param_name)
        if value is not None:
            weighted_sum += weights[i] * value
    
    return weighted_sum / total_weight


def calculate_damage_equivalent_ratio(bins_in_window, sigma_site_func, sigma_ntm_func, m):
    """
    Calculate damage-equivalent ratio R(m).
    p_i = hours_i / sum hours in WINDOW (skip hours=0)
    R(m) = (Σ p_i * σ_site^m)^{1/m} / (Σ p_i * σ_NTM^m)^{1/m}
    """
    total_hours = sum(b['hours'] for b in bins_in_window)
    if total_hours == 0:
        return None
    
    numerator_sum = 0
    denominator_sum = 0
    
    for bin_data in bins_in_window:
        if bin_data['hours'] == 0:
            continue
        
        p_i = bin_data['hours'] / total_hours
        v_center = bin_data['v_center']
        
        sigma_site = sigma_site_func(v_center)
        sigma_ntm = sigma_ntm_func(v_center)
        
        numerator_sum += p_i * (sigma_site ** m)
        denominator_sum += p_i * (sigma_ntm ** m)
    
    if denominator_sum == 0:
        return None
    
    return (numerator_sum / denominator_sum) ** (1 / m)


def run_assessment(input_data):
    """
    Run complete assessment from input data.
    
    Input format:
    {
        'edition': 'ed4' | 'ed3',
        'vref': float,
        'iref': float,
        'vave': float,  # design Vave
        'v50': float,
        'rho': float,
        'apply_density_to_v50': bool,
        'complexity': 'simple' | 'complex',
        'v_rated': float (required for ed3),
        'v_out': float (required for ed3),
        'bin_width': float,
        'period_hours': float,
        'ti_bins': [
            {
                'v_center': float,
                'hours': float,
                'mean_sigma': float,
                'std_sigma': float | None
            }
        ],
        'shear_alpha': float | None,  # omni or None
        'inflow_angle_deg': float | None,  # omni or None
        'wohler_exponents': [4, 10]  # default
    }
    
    Returns assessment results with all checks.
    """
    edition = input_data['edition']
    vref = input_data['vref']
    iref = input_data['iref']
    vave_design = input_data['vave']
    v50 = input_data['v50']
    rho = input_data['rho']
    apply_density_to_v50 = input_data.get('apply_density_to_v50', False)
    complexity = input_data['complexity']
    bin_width = input_data['bin_width']
    period_hours = input_data['period_hours']
    ti_bins = input_data['ti_bins']
    wohler_exponents = input_data.get('wohler_exponents', [4, 10])
    
    # Complexity correction factor
    cct = 1.15 if complexity == 'complex' else 1.00
    
    # Determine speed window
    v_rated = input_data.get('v_rated')
    v_out = input_data.get('v_out')
    v_lo, v_hi, window_error = get_speed_window(edition, vave_design, v_rated, v_out)
    
    if window_error:
        return {'error': window_error}
    
    # Validate A+ with ed3
    if edition == 'ed3' and iref >= 0.18:
        return {'error': "A+ (Iref >= 0.18) rejected on ed3"}
    
    # Calculate Rayleigh distribution for all bins
    all_bin_centers = [b['v_center'] for b in ti_bins]
    rayleigh_probs = calculate_rayleigh_distribution(vave_design, all_bin_centers, bin_width)
    
    # Filter bins in window
    bins_in_window = []
    for i, bin_data in enumerate(ti_bins):
        if bin_in_window(bin_data['v_center'], v_lo, v_hi, bin_width):
            bin_entry = bin_data.copy()
            bin_entry['rayleigh_prob'] = rayleigh_probs[i]
            bins_in_window.append(bin_entry)
    
    # Overall flags
    overall_flags = []
    
    # ===== CHECK 1: EXTREME WIND =====
    v_use = v50
    if apply_density_to_v50:
        v_use = v50 * math.sqrt(rho / 1.225)
    
    extreme_wind_ratio = v_use / vref
    extreme_wind_status = 'Pass' if extreme_wind_ratio <= 1.0 else 'Fail'
    extreme_wind_flags = []
    
    if abs(rho - 1.225) > 0.001:
        extreme_wind_flags.append('rho_ne_std')
    
    extreme_wind_check = {
        'check_id': 'extreme_wind',
        'status': extreme_wind_status,
        'value': v_use,
        'limit': vref,
        'units': 'm/s',
        'detail': {
            'V50': v50,
            'Vref': vref,
            'ratio': extreme_wind_ratio
        },
        'flags': extreme_wind_flags
    }
    
    # ===== CHECK 2: WIND DISTRIBUTION =====
    max_bin_ratio = 0
    n_bins_exceeded = 0
    
    for bin_entry in bins_in_window:
        hours = bin_entry['hours']
        p_site = hours / period_hours
        p_rayleigh = bin_entry['rayleigh_prob']
        
        # relative tolerance 1e-6
        if p_site > p_rayleigh * (1 + 1e-6):
            n_bins_exceeded += 1
            ratio = p_site / p_rayleigh if p_rayleigh > 0 else float('inf')
            if ratio > max_bin_ratio:
                max_bin_ratio = ratio
    
    wind_dist_status = 'Pass' if n_bins_exceeded == 0 else 'Fail'
    
    wind_dist_check = {
        'check_id': 'wind_distribution',
        'status': wind_dist_status,
        'value': max_bin_ratio if n_bins_exceeded > 0 else 1.0,
        'limit': 1.0,
        'units': '',
        'detail': {
            'max_bin_ratio': max_bin_ratio if n_bins_exceeded > 0 else 1.0,
            'n_bins_exceeded': n_bins_exceeded
        },
        'flags': []
    }
    
    # ===== CHECK 3: TURBULENCE NTM =====
    if len(bins_in_window) == 0:
        turbulence_check = {
            'check_id': 'turbulence_ntm',
            'status': 'Fail',
            'value': None,
            'limit': None,
            'units': '',
            'detail': {},
            'flags': ['empty_ti_window']
        }
    else:
        n_bins_exceeded_ti = 0
        max_r_values = {}
        assumed_cov_flag = False
        
        for bin_entry in bins_in_window:
            v_center = bin_entry['v_center']
            mean_sigma = bin_entry['mean_sigma']
            std_sigma = bin_entry.get('std_sigma')
            
            sigma_90, assumed_cov = calculate_sigma_90(mean_sigma, std_sigma)
            if assumed_cov:
                assumed_cov_flag = True
            
            sigma_site = sigma_90 * cct
            sigma_ntm = calculate_ntm_sigma(v_center, iref)
            
            if sigma_site > sigma_ntm:
                n_bins_exceeded_ti += 1
        
        # Damage equivalent ratios
        for m in wohler_exponents:
            def sigma_site_func(v):
                # Find bin
                for b in bins_in_window:
                    if abs(b['v_center'] - v) < 1e-9:
                        mean_sigma = b['mean_sigma']
                        std_sigma = b.get('std_sigma')
                        sigma_90, _ = calculate_sigma_90(mean_sigma, std_sigma)
                        return sigma_90 * cct
                return None
            
            def sigma_ntm_func(v):
                return calculate_ntm_sigma(v, iref)
            
            r_m = calculate_damage_equivalent_ratio(bins_in_window, sigma_site_func, sigma_ntm_func, m)
            max_r_values[f'R_m_{m}'] = r_m
        
        max_r = max(max_r_values.values()) if max_r_values else 0
        
        # Determine status
        if n_bins_exceeded_ti == 0:
            ti_status = 'Pass'
        elif n_bins_exceeded_ti > 0 and max_r <= 1.0:
            ti_status = 'Warn'
        else:
            ti_status = 'Fail'
        
        ti_flags = []
        if assumed_cov_flag:
            ti_flags.append('assumed_cov_0_3')
            overall_flags.append('assumed_cov_0_3')
        
        turbulence_check = {
            'check_id': 'turbulence_ntm',
            'status': ti_status,
            'value': max_r,
            'limit': 1.0,
            'units': '',
            'detail': {
                'n_bins_exceeded': n_bins_exceeded_ti,
                'assumed_cov_0_3': assumed_cov_flag,
                **max_r_values
            },
            'flags': ti_flags
        }
    
    # ===== CHECK 4: SHEAR =====
    # Energy-weighted alpha over ALL bins (not just window) or scalar
    shear_alpha_global = input_data.get('shear_alpha')
    
    if shear_alpha_global is not None:
        alpha_ew = shear_alpha_global
    else:
        # Calculate from bins (energy-weighted over all bins)
        all_bins = [{'v_center': b['v_center'], 'hours': b['hours'], 
                     'shear_alpha': b.get('shear_alpha_override', 0.0)} 
                    for b in ti_bins]
        alpha_ew = calculate_energy_weighted_value(all_bins, 'shear_alpha')
        if alpha_ew is None:
            alpha_ew = 0.0
    
    shear_status = 'Pass' if 0.05 <= alpha_ew <= 0.25 else 'Fail'
    
    shear_check = {
        'check_id': 'shear',
        'status': shear_status,
        'value': alpha_ew,
        'limit': None,
        'units': '',
        'detail': {
            'alpha_ew': alpha_ew,
            'limits': [0.05, 0.25]
        },
        'flags': []
    }
    
    # ===== CHECK 5: INFLOW =====
    inflow_angle_global = input_data.get('inflow_angle_deg')
    
    if inflow_angle_global is not None:
        abs_inflow_ew = abs(inflow_angle_global)
    else:
        # Calculate from bins
        all_bins = [{'v_center': b['v_center'], 'hours': b['hours'],
                     'inflow_angle_deg': b.get('inflow_angle_deg_override', 0.0)}
                    for b in ti_bins]
        inflow_ew = calculate_energy_weighted_value(all_bins, 'inflow_angle_deg')
        abs_inflow_ew = abs(inflow_ew) if inflow_ew is not None else 0
    
    inflow_status = 'Pass' if abs_inflow_ew <= 8.0 else 'Fail'
    
    inflow_check = {
        'check_id': 'inflow',
        'status': inflow_status,
        'value': abs_inflow_ew,
        'limit': 8.0,
        'units': 'deg',
        'detail': {
            'abs_inflow_ew_deg': abs_inflow_ew
        },
        'flags': []
    }
    
    # ===== CHECK 6: AIR DENSITY =====
    if rho <= 1.225:
        density_status = 'Pass'
        density_reason = None
    else:
        density_status = 'Fail'
        density_reason = 'density_compensation_unlicensed'
    
    density_check = {
        'check_id': 'air_density',
        'status': density_status,
        'value': rho,
        'limit': 1.225,
        'units': 'kg/m³',
        'detail': {
            'rho': rho,
            'reason': density_reason
        },
        'flags': []
    }
    
    # ===== CHECK 7: COMPLEXITY =====
    complexity_check = {
        'check_id': 'complexity',
        'status': 'Pass',
        'value': cct,
        'limit': None,
        'units': '',
        'detail': {
            'user': complexity,
            'cct': cct
        },
        'flags': []
    }
    
    # Overall status: worst of seven
    all_checks = [
        extreme_wind_check,
        wind_dist_check,
        turbulence_check,
        shear_check,
        inflow_check,
        density_check,
        complexity_check
    ]
    
    status_priority = {'Fail': 3, 'Warn': 2, 'Pass': 1}
    worst_status = 'Pass'
    for check in all_checks:
        if status_priority[check['status']] > status_priority[worst_status]:
            worst_status = check['status']
    
    return {
        'overall': worst_status,
        'cct': cct,
        'speed_range': [v_lo, v_hi],
        'flags': overall_flags,
        'checks': all_checks
    }
