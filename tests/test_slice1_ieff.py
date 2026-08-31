"""
Tests for Slice 1: Effective Turbulence (turbulence_ieff).
"""
import json
import pytest
import math
from pathlib import Path
from assessments.engine import (
    calculate_effective_turbulence_slice1,
    interpolate_ct,
    calculate_wake_sigma_slice1,
    get_sector_from_bearing,
    calculate_bearing_distance
)


def load_golden_slice1(filename):
    """Load Slice 1 golden test JSON file."""
    doc_dir = Path(__file__).parent.parent / 'docs' / 'slice1'
    with open(doc_dir / filename, 'r') as f:
        return json.load(f)


def assert_float_close(actual, expected, rel_tol=1e-4, abs_tol=1e-5):
    """Assert two floats are close with tolerance."""
    if expected is None:
        assert actual is None
        return
    if actual is None:
        assert expected is None
        return
    assert abs(actual - expected) < abs_tol + rel_tol * abs(expected), \
        f"Expected {expected}, got {actual}, diff={abs(actual - expected)}"


class TestSlice1Kernel:
    """Test Slice 1 wake kernel formula."""
    
    def test_wake_sigma_8d(self):
        """Test wake sigma at 8D spacing (GOLDEN_IEFF_PASS case)."""
        # V=15, Ct=0.626923, d=960m, D=120m (8D)
        v = 15.0
        ct = 0.626923
        distance_m = 960.0
        rotor_d_m = 120.0
        
        # Expected: σ_wake = V / (1.5 + 0.8 · (d/D) / √Ct)
        #                  = 15 / (1.5 + 0.8 · 8 / √0.626923)
        #                  = 15 / (1.5 + 0.8 · 8 / 0.791785)
        #                  = 15 / (1.5 + 8.0784)
        #                  = 15 / 9.5784
        #                  = 1.5656
        
        sigma_wake = calculate_wake_sigma_slice1(v, ct, distance_m, rotor_d_m)
        assert_float_close(sigma_wake, 1.5656, abs_tol=1e-3)  # Slightly higher tolerance for hand-calculated values
    
    def test_wake_sigma_3d(self):
        """Test wake sigma at 3D spacing (GOLDEN_IEFF_FAIL case)."""
        # V=15, Ct=0.626923, d=360m, D=120m (3D)
        v = 15.0
        ct = 0.626923
        distance_m = 360.0
        rotor_d_m = 120.0
        
        # Expected: σ_wake = 15 / (1.5 + 0.8 · 3 / √0.626923)
        #                  = 15 / (1.5 + 3.0294)
        #                  = 15 / 4.5294
        #                  = 3.3114
        
        sigma_wake = calculate_wake_sigma_slice1(v, ct, distance_m, rotor_d_m)
        assert_float_close(sigma_wake, 3.3114, abs_tol=1e-3)  # Slightly higher tolerance for hand-calculated values
    
    def test_wake_sigma_cutoff_10d(self):
        """Test wake cutoff at 10.1D (no wake contribution)."""
        v = 15.0
        ct = 0.8
        distance_m = 1212.0  # 10.1 * 120
        rotor_d_m = 120.0
        
        sigma_wake = calculate_wake_sigma_slice1(v, ct, distance_m, rotor_d_m)
        assert sigma_wake == 0.0  # Beyond 10D cutoff


class TestSlice1CtInterpolation:
    """Test Ct curve interpolation and fallback."""
    
    def test_ct_interpolation_linear(self):
        """Test linear Ct interpolation."""
        # Ct curve: 0.80 at V≤12, linear to 0.05 at V=25
        ct_curve = [
            {'v_mps': 12, 'ct': 0.80},
            {'v_mps': 25, 'ct': 0.05}
        ]
        
        # At V=15: Ct = 0.80 + (0.05-0.80)*(15-12)/(25-12)
        #            = 0.80 - 0.75*3/13
        #            = 0.80 - 0.173077
        #            = 0.626923
        ct_15 = interpolate_ct(15.0, ct_curve)
        assert_float_close(ct_15, 0.626923, abs_tol=1e-6)
    
    def test_ct_extrapolate_flat_low(self):
        """Test Ct extrapolation below curve (flat)."""
        ct_curve = [{'v_mps': 5, 'ct': 0.85}]
        ct_3 = interpolate_ct(3.0, ct_curve)
        assert ct_3 == 0.85  # Flat extrapolation
    
    def test_ct_extrapolate_flat_high(self):
        """Test Ct extrapolation above curve (flat)."""
        ct_curve = [{'v_mps': 20, 'ct': 0.10}]
        ct_25 = interpolate_ct(25.0, ct_curve)
        assert ct_25 == 0.10  # Flat extrapolation
    
    def test_ct_missing_returns_none(self):
        """Test missing Ct curve returns None."""
        ct_curve = []
        ct = interpolate_ct(10.0, ct_curve)
        assert ct is None


class TestSlice1SectorLogic:
    """Test 30° sector binning."""
    
    def test_sector_north(self):
        """Test bearing 0° (North) maps to sector 0."""
        sector = get_sector_from_bearing(0.0, sector_width_deg=30)
        assert sector == 0
    
    def test_sector_northeast(self):
        """Test bearing 45° maps to sector 1."""
        sector = get_sector_from_bearing(45.0, sector_width_deg=30)
        assert sector == 1
    
    def test_sector_east(self):
        """Test bearing 90° (East) maps to sector 3."""
        sector = get_sector_from_bearing(90.0, sector_width_deg=30)
        assert sector == 3
    
    def test_sector_south(self):
        """Test bearing 180° (South) maps to sector 6."""
        sector = get_sector_from_bearing(180.0, sector_width_deg=30)
        assert sector == 6
    
    def test_sector_west(self):
        """Test bearing 270° (West) maps to sector 9."""
        sector = get_sector_from_bearing(270.0, sector_width_deg=30)
        assert sector == 9
    
    def test_bearing_calculation(self):
        """Test bearing and distance calculation."""
        # From (0, 0) to (0, 960): North, 960m
        bearing, distance = calculate_bearing_distance(0, 0, 0, 960)
        assert_float_close(bearing, 0.0, abs_tol=1e-6)
        assert_float_close(distance, 960.0, abs_tol=1e-6)
        
        # From (0, 0) to (960, 0): East, 960m
        bearing, distance = calculate_bearing_distance(0, 0, 960, 0)
        assert_float_close(bearing, 90.0, abs_tol=1e-6)
        assert_float_close(distance, 960.0, abs_tol=1e-6)


class TestGoldenIeffPass:
    """Test GOLDEN_IEFF_PASS (8D spacing, R(10)=0.852606 Pass)."""
    
    def test_golden_ieff_pass(self):
        """Test 8D spacing case passes with R(10)=0.852606."""
        golden = load_golden_slice1('golden_ieff_pass_expected.json')
        input_data = golden['input']
        expected = golden['expected']
        
        # Prepare bins in window (9-17 m/s)
        bins_in_window = input_data['ti_bins']
        
        result = calculate_effective_turbulence_slice1(
            bins_in_window,
            input_data['iref'],
            input_data['cct'],
            input_data['target_turbine'],
            input_data['neighbors'],
            sector_frequencies=input_data.get('sector_frequencies'),
            wohler_exponents=input_data['wohler_exponents']
        )
        
        # Check status
        assert result['status'] == expected['status']
        assert result['check_id'] == expected['check_id']
        
        # Check R values
        assert_float_close(result['detail']['R_m_10'], expected['detail']['R_m_10'], abs_tol=1e-4)
        assert_float_close(result['detail']['R_m_4'], expected['detail']['R_m_4'], abs_tol=1e-4)
        
        # Check flags
        assert 'omni_rose_assumed' in result['flags']
        assert 'view_angle_bin_width_30' in result['flags']


class TestGoldenIeffFail:
    """Test GOLDEN_IEFF_FAIL (3D spacing, R(10)=1.246112 Fail)."""
    
    def test_golden_ieff_fail(self):
        """Test 3D spacing case fails with R(10)=1.246112."""
        golden = load_golden_slice1('golden_ieff_fail_expected.json')
        input_data = golden['input']
        expected = golden['expected']
        
        # Prepare bins in window (9-17 m/s)
        bins_in_window = input_data['ti_bins']
        
        result = calculate_effective_turbulence_slice1(
            bins_in_window,
            input_data['iref'],
            input_data['cct'],
            input_data['target_turbine'],
            input_data['neighbors'],
            sector_frequencies=input_data.get('sector_frequencies'),
            wohler_exponents=input_data['wohler_exponents']
        )
        
        # Check status
        assert result['status'] == expected['status']
        assert result['check_id'] == expected['check_id']
        
        # Check R values
        assert_float_close(result['detail']['R_m_10'], expected['detail']['R_m_10'], abs_tol=1e-4)
        assert_float_close(result['detail']['R_m_4'], expected['detail']['R_m_4'], abs_tol=1e-4)
        
        # Check n_bins_exceeded
        assert result['detail']['n_bins_exceeded'] == expected['detail']['n_bins_exceeded']
