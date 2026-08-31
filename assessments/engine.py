"""
Calculation engine for IEC 61400-1 inspired site suitability assessment.
Screening against a user-editable class envelope, not a certified IEC 61400-1 assessment.

Pure Python, no database required.
"""
import math


def interpolate_ct(v_mps, ct_curve):
    """
    Interpolate Ct value from curve.
    ct_curve: list of {'v_mps': float, 'ct': float} sorted by v_mps
    Returns: Ct value or None if outside range
    """
    if not ct_curve or len(ct_curve) == 0:
        return None
    
    # Extrapolate flat at boundaries
    if v_mps <= ct_curve[0]['v_mps']:
        return ct_curve[0]['ct']
    if v_mps >= ct_curve[-1]['v_mps']:
        return ct_curve[-1]['ct']
    
    # Linear interpolation
    for i in range(len(ct_curve) - 1):
        v1, ct1 = ct_curve[i]['v_mps'], ct_curve[i]['ct']
        v2, ct2 = ct_curve[i + 1]['v_mps'], ct_curve[i + 1]['ct']
        
        if v1 <= v_mps <= v2:
            if v2 == v1:
                return ct1
            return ct1 + (ct2 - ct1) * (v_mps - v1) / (v2 - v1)
    
    return None


def calculate_wake_sigma_slice1(v_mps, ct, distance_m, rotor_d_upstream_m):
    """
    Calculate wake-generated turbulence sigma using Slice 1 kernel.
    
    Public A1/Ct formulation (Master Bot approved SLICE1_CALC_SPEC):
    σ_wake = V / (1.5 + 0.8 · (d/D_up) / √Ct)
    
    Args:
        v_mps: Wind speed (m/s)
        ct: Thrust coefficient at this wind speed
        distance_m: Distance between turbines (m)
        rotor_d_upstream_m: Upstream (neighbor) rotor diameter (m)
    
    Returns:
        Wake-generated sigma in m/s
    """
    if ct <= 0 or distance_m <= 0 or rotor_d_upstream_m <= 0 or v_mps <= 0:
        return 0.0
    
    d_over_D = distance_m / rotor_d_upstream_m
    
    # Distance cutoff: only apply wake if d ≤ 10 D
    if d_over_D > 10.0:
        return 0.0
    
    # σ_wake = V / (1.5 + 0.8 · (d/D) / √Ct)
    sqrt_ct = math.sqrt(ct)
    if sqrt_ct < 1e-9:
        return 0.0
    
    denominator = 1.5 + 0.8 * d_over_D / sqrt_ct
    sigma_wake = v_mps / denominator
    
    return sigma_wake


def get_sector_from_bearing(bearing_deg, sector_width_deg=30):
    """
    Get sector index from bearing.
    Sectors: 0-30°, 30-60°, ..., 330-360° (12 sectors for 30°)
    
    Args:
        bearing_deg: Bearing in degrees (0° = North, clockwise)
        sector_width_deg: Sector width (default 30°)
    
    Returns:
        Sector index (0-11 for 30° sectors)
    """
    # Normalize bearing to [0, 360)
    bearing_deg = bearing_deg % 360
    sector_idx = int(bearing_deg / sector_width_deg)
    # Handle edge case of 360°
    if sector_idx >= 12:
        sector_idx = 0
    return sector_idx


def calculate_bearing_distance(x1, y1, x2, y2):
    """
    Calculate bearing and distance from point 1 to point 2.
    
    Args:
        x1, y1: Coordinates of point 1 (m)
        x2, y2: Coordinates of point 2 (m)
    
    Returns:
        bearing_deg: bearing from point 1 to point 2 (0° = North, clockwise)
        distance_m: distance between points (m)
    """
    dx = x2 - x1
    dy = y2 - y1
    distance_m = math.sqrt(dx**2 + dy**2)
    
    if distance_m < 1e-9:
        return 0.0, 0.0
    
    # Bearing: North = 0°, East = 90°, South = 180°, West = 270°
    bearing_rad = math.atan2(dx, dy)
    bearing_deg = math.degrees(bearing_rad)
    if bearing_deg < 0:
        bearing_deg += 360
    
    return bearing_deg, distance_m


def calculate_effective_turbulence_slice1(
    bins_in_window,
    iref,
    cct,
    target_turbine,
    neighbors,
    sector_frequencies=None,
    wohler_exponents=[4, 10],
    sector_width_deg=30
):
    """
    Calculate effective turbulence using Slice 1 kernel (Master Bot approved spec).
    
    This is a SECOND check (turbulence_ieff), separate from turbulence_ntm (Slice 0).
    
    Kernel (public A1/Ct formulation):
    - σ_c = σ90 · CCT (ambient, no-wake term)
    - σ_wake = V / (1.5 + 0.8 · (d/D_up) / √Ct) for nearest neighbor in 30° sector
    - σ_T = sqrt(σ_wake² + σ_c²) if d ≤ 10 D, else σ_T = σ_c
    - σ_eff = (Σ_j p_j · σ_T^m)^(1/m) with m=10 for direction weighting
    - R(m) = (Σ_i p_i · σ_eff^m)^(1/m) / (Σ_i p_i · σ1^m)^(1/m)
    - Status: Pass if no exceed; Warn if exceed but R(10)≤1; Fail if R(10)>1
    
    Args:
        bins_in_window: TI bins in speed window
        iref: Reference turbulence intensity
        cct: Complexity correction factor
        target_turbine: dict with 'x_m', 'y_m', 'rotor_d_m', 'ct_curve' (list of {'v_mps', 'ct'})
        neighbors: list of dicts with 'x_m', 'y_m', 'rotor_d_m', 'ct_curve'
        sector_frequencies: optional list of {'sector_idx': int, 'frequency': float} for 30° sectors
                           or None for omni-directional (uniform 1/12)
        wohler_exponents: list of m values (default [4, 10])
        sector_width_deg: sector width in degrees (30° for Slice 1)
    
    Returns:
        dict with check result
    """
    n_sectors = int(360 / sector_width_deg)  # 12 sectors for 30°
    flags = []
    
    # Check if omni or sectored
    is_omni = sector_frequencies is None or len(sector_frequencies) == 0
    
    if is_omni:
        # Uniform frequency per sector (omni-directional)
        sector_freq_array = [1.0 / n_sectors] * n_sectors
        flags.append('omni_rose_assumed')
    else:
        # Use provided sector frequencies
        # sector_frequencies is a list of {'sector_idx': int, 'frequency': float}
        sector_freq_array = [0.0] * n_sectors
        for sector_data in sector_frequencies:
            sector_idx = sector_data['sector_idx']
            if 0 <= sector_idx < n_sectors:
                sector_freq_array[sector_idx] = sector_data['frequency']
    
    # Flag for view angle documentation vs implementation
    flags.append('view_angle_bin_width_30')
    
    # Find nearest neighbor in each sector
    nearest_in_sector = {}
    
    for neighbor in neighbors:
        bearing_deg, distance_m = calculate_bearing_distance(
            target_turbine['x_m'], target_turbine['y_m'],
            neighbor['x_m'], neighbor['y_m']
        )
        
        if distance_m < 1e-9:
            continue  # Skip self or coincident turbines
        
        sector_idx = get_sector_from_bearing(bearing_deg, sector_width_deg)
        
        # Check if this is the nearest in this sector
        if sector_idx not in nearest_in_sector or distance_m < nearest_in_sector[sector_idx]['distance_m']:
            nearest_in_sector[sector_idx] = {
                'neighbor': neighbor,
                'distance_m': distance_m,
                'bearing_deg': bearing_deg
            }
    
    # Calculate effective turbulence for each bin
    ieff_results = []
    n_bins_exceeded = 0
    ieff_bin_details = []
    
    for bin_entry in bins_in_window:
        v_center = bin_entry['v_center']
        mean_sigma = bin_entry['mean_sigma']
        std_sigma = bin_entry.get('std_sigma')
        hours = bin_entry['hours']
        
        # Ambient term (no-wake): σ_c = σ90 * CCT
        sigma_90, assumed_cov = calculate_sigma_90(mean_sigma, std_sigma)
        sigma_c = sigma_90 * cct
        
        # NTM reference
        sigma_ntm = calculate_ntm_sigma(v_center, iref)
        
        # Get target Ct at this speed
        ct_curve_target = target_turbine.get('ct_curve', [])
        ct_target = interpolate_ct(v_center, ct_curve_target)
        ct_target_display = ct_target if ct_target is not None else 0.0
        
        # Direction-weighted effective turbulence using m=10
        m_direction = 10  # Wöhler exponent for direction weighting
        sigma_T_powered_sum = 0.0
        min_distance = None
        n_wake_sectors = 0
        
        for sector_idx in range(n_sectors):
            freq = sector_freq_array[sector_idx]
            
            if freq <= 0:
                continue  # Skip sectors with zero frequency
            
            if sector_idx in nearest_in_sector:
                n_wake_sectors += 1
                # Have a neighbor in this sector
                neighbor_info = nearest_in_sector[sector_idx]
                neighbor = neighbor_info['neighbor']
                distance_m = neighbor_info['distance_m']
                
                if min_distance is None or distance_m < min_distance:
                    min_distance = distance_m
                
                # Get neighbor Ct at this wind speed
                ct_curve = neighbor.get('ct_curve', [])
                ct = interpolate_ct(v_center, ct_curve)
                
                # Fallback for missing Ct: Ct = 7/V
                if ct is None or ct <= 0:
                    ct = 7.0 / v_center if v_center > 0 else 0.8
                    if 'ct_missing' not in flags:
                        flags.append('ct_missing')
                
                # Calculate wake sigma
                sigma_wake = calculate_wake_sigma_slice1(
                    v_center, ct, distance_m, neighbor['rotor_d_m']
                )
                
                # Total turbulence in this sector
                sigma_T = math.sqrt(sigma_wake**2 + sigma_c**2)
            else:
                # No neighbor in this sector, use ambient only
                sigma_T = sigma_c
            
            # Accumulate powered sum for direction weighting
            sigma_T_powered_sum += freq * (sigma_T ** m_direction)
        
        # Effective turbulence (direction-weighted)
        sigma_eff = sigma_T_powered_sum ** (1.0 / m_direction)
        
        # Check if exceeds NTM
        exceeded = sigma_eff > sigma_ntm
        if exceeded:
            n_bins_exceeded += 1
        
        ieff_results.append({
            'v_center': v_center,
            'sigma_eff': sigma_eff,
            'sigma_ntm': sigma_ntm,
            'exceeded': exceeded
        })
        
        # Store per-bin details for HTML display
        d_over_D = (min_distance / target_turbine['rotor_d_m']) if min_distance and target_turbine['rotor_d_m'] > 0 else None
        ieff_bin_details.append({
            'v_center': v_center,
            'ct': ct_target_display,
            'sigma_c': sigma_c,
            'sigma_eff': sigma_eff,
            'sigma_ntm': sigma_ntm,
            'i_eff': sigma_eff / v_center if v_center > 0 else 0,
            'i_ntm': sigma_ntm / v_center if v_center > 0 else 0,
            'exceeded': exceeded,
            'd_min_over_D': d_over_D,
            'n_wake_sectors': n_wake_sectors
        })
    
    # Calculate damage-equivalent ratios R(m)
    total_hours = sum(b['hours'] for b in bins_in_window)
    r_values = {}
    
    for m in wohler_exponents:
        if total_hours == 0:
            r_values[f'R_m_{m}'] = None
            continue
        
        numerator_sum = 0
        denominator_sum = 0
        
        for i, bin_entry in enumerate(bins_in_window):
            if bin_entry['hours'] == 0:
                continue
            
            p_i = bin_entry['hours'] / total_hours
            sigma_eff = ieff_results[i]['sigma_eff']
            sigma_ntm = ieff_results[i]['sigma_ntm']
            
            numerator_sum += p_i * (sigma_eff ** m)
            denominator_sum += p_i * (sigma_ntm ** m)
        
        if denominator_sum > 0:
            r_values[f'R_m_{m}'] = (numerator_sum / denominator_sum) ** (1 / m)
        else:
            r_values[f'R_m_{m}'] = None
    
    # Determine status based on R(10) ONLY (R(4) is diagnostic)
    r_10 = r_values.get('R_m_10')
    
    if r_10 is None:
        status = 'Fail'
    elif n_bins_exceeded == 0:
        status = 'Pass'
    elif r_10 <= 1.0:
        status = 'Warn'
    else:
        status = 'Fail'
    
    return {
        'check_id': 'turbulence_ieff',
        'status': status,
        'value': r_10,
        'limit': 1.0,
        'units': '',
        'detail': {
            'n_bins_exceeded': n_bins_exceeded,
            'n_neighbors_effective': len(nearest_in_sector),
            'ieff_bin_details': ieff_bin_details,
            **r_values
        },
        'flags': flags
    }


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
    dist_bin_details = []
    
    for bin_entry in bins_in_window:
        hours = bin_entry['hours']
        v_center = bin_entry['v_center']
        p_site = hours / period_hours
        p_rayleigh = bin_entry['rayleigh_prob']
        
        # relative tolerance 1e-6
        exceeded = p_site > p_rayleigh * (1 + 1e-6)
        if exceeded:
            n_bins_exceeded += 1
            ratio = p_site / p_rayleigh if p_rayleigh > 0 else float('inf')
            if ratio > max_bin_ratio:
                max_bin_ratio = ratio
        else:
            ratio = p_site / p_rayleigh if p_rayleigh > 0 else 0
        
        # Store per-bin details for HTML display
        dist_bin_details.append({
            'v_center': v_center,
            'p_site': p_site,
            'p_rayleigh': p_rayleigh,
            'ratio': ratio,
            'exceeded': exceeded
        })
    
    wind_dist_status = 'Pass' if n_bins_exceeded == 0 else 'Fail'
    
    wind_dist_check = {
        'check_id': 'wind_distribution',
        'status': wind_dist_status,
        'value': max_bin_ratio if n_bins_exceeded > 0 else 1.0,
        'limit': 1.0,
        'units': '',
        'detail': {
            'max_bin_ratio': max_bin_ratio if n_bins_exceeded > 0 else 1.0,
            'n_bins_exceeded': n_bins_exceeded,
            'dist_bin_details': dist_bin_details
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
        ti_bin_details = []
        
        for bin_entry in bins_in_window:
            v_center = bin_entry['v_center']
            mean_sigma = bin_entry['mean_sigma']
            std_sigma = bin_entry.get('std_sigma')
            hours = bin_entry['hours']
            
            sigma_90, assumed_cov = calculate_sigma_90(mean_sigma, std_sigma)
            if assumed_cov:
                assumed_cov_flag = True
            
            sigma_site = sigma_90 * cct
            sigma_ntm = calculate_ntm_sigma(v_center, iref)
            
            exceeded = sigma_site > sigma_ntm
            if exceeded:
                n_bins_exceeded_ti += 1
            
            # Store per-bin details for HTML display
            ti_bin_details.append({
                'v_center': v_center,
                'hours': hours,
                'sigma_90': sigma_90,
                'sigma_site': sigma_site,
                'sigma_ntm': sigma_ntm,
                'ti_site': sigma_site / v_center if v_center > 0 else 0,
                'ti_ntm': sigma_ntm / v_center if v_center > 0 else 0,
                'exceeded': exceeded
            })
        
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
                'ti_bin_details': ti_bin_details,
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
