"""
Tests for the assessment calculation engine.
"""
import json
import pytest
from pathlib import Path
from assessments.engine import run_assessment


def load_golden_test(filename):
    """Load golden test JSON file."""
    test_dir = Path(__file__).parent
    with open(test_dir / filename, 'r') as f:
        return json.load(f)


def assert_float_close(actual, expected, rel_tol=1e-5, abs_tol=1e-5):
    """Assert two floats are close with tolerance."""
    if expected is None:
        assert actual is None
        return
    if actual is None:
        assert expected is None
        return
    assert abs(actual - expected) < abs_tol + rel_tol * abs(expected), \
        f"Expected {expected}, got {actual}"


def assert_check_matches(actual_check, expected_check, check_id):
    """Assert check result matches expected."""
    assert actual_check['check_id'] == check_id
    assert actual_check['status'] == expected_check['status'], \
        f"{check_id}: Expected status {expected_check['status']}, got {actual_check['status']}"
    
    # Check detail values
    for key, expected_val in expected_check.get('detail', {}).items():
        actual_val = actual_check['detail'].get(key)
        if isinstance(expected_val, float):
            assert_float_close(actual_val, expected_val)
        else:
            assert actual_val == expected_val, \
                f"{check_id}.{key}: Expected {expected_val}, got {actual_val}"


class TestGoldenPass:
    """Test GOLDEN_PASS_T1 scenario."""
    
    def test_golden_pass_t1(self):
        """Test passing assessment with all checks."""
        golden = load_golden_test('golden_pass_t1.json')
        result = run_assessment(golden['input'])
        
        assert 'error' not in result
        assert result['overall'] == golden['expected']['overall']
        assert result['cct'] == golden['expected']['cct']
        assert result['speed_range'] == golden['expected']['speed_range']
        assert result['flags'] == golden['expected']['flags']
        
        # Check each check
        for check in result['checks']:
            check_id = check['check_id']
            expected_check = golden['expected']['checks'][check_id]
            assert_check_matches(check, expected_check, check_id)


class TestGoldenFail:
    """Test GOLDEN_FAIL_T1 scenario."""
    
    def test_golden_fail_t1(self):
        """Test failing assessment with extreme wind and turbulence failures."""
        golden = load_golden_test('golden_fail_t1.json')
        result = run_assessment(golden['input'])
        
        assert 'error' not in result
        assert result['overall'] == golden['expected']['overall']
        assert result['cct'] == golden['expected']['cct']
        assert result['speed_range'] == golden['expected']['speed_range']
        assert 'assumed_cov_0_3' in result['flags']
        
        # Check each check
        for check in result['checks']:
            check_id = check['check_id']
            expected_check = golden['expected']['checks'][check_id]
            assert_check_matches(check, expected_check, check_id)


class TestEditionValidation:
    """Test edition-specific validation."""
    
    def test_ed3_requires_vrated_and_vout(self):
        """Test that ed3 requires v_rated and v_out."""
        input_data = {
            'edition': 'ed3',
            'vref': 42.5,
            'iref': 0.14,
            'vave': 8.5,
            'v50': 40.0,
            'rho': 1.225,
            'complexity': 'simple',
            'bin_width': 1.0,
            'period_hours': 8760,
            'ti_bins': []
        }
        
        result = run_assessment(input_data)
        assert 'error' in result
        assert 'ed3 requires v_rated and v_out' in result['error']
    
    def test_ed3_rejects_a_plus(self):
        """Test that ed3 rejects A+ (Iref >= 0.18)."""
        input_data = {
            'edition': 'ed3',
            'vref': 50.0,
            'iref': 0.18,
            'vave': 10.0,
            'v50': 45.0,
            'rho': 1.225,
            'complexity': 'simple',
            'v_rated': 12.0,
            'v_out': 25.0,
            'bin_width': 1.0,
            'period_hours': 8760,
            'ti_bins': []
        }
        
        result = run_assessment(input_data)
        assert 'error' in result
        assert 'A+' in result['error'] and 'ed3' in result['error']


class TestComplexityCorrection:
    """Test CCT calculation."""
    
    def test_simple_cct(self):
        """Test CCT=1.0 for simple terrain."""
        input_data = {
            'edition': 'ed4',
            'vref': 42.5,
            'iref': 0.14,
            'vave': 8.5,
            'v50': 40.0,
            'rho': 1.225,
            'complexity': 'simple',
            'bin_width': 1.0,
            'period_hours': 8760,
            'ti_bins': []
        }
        
        result = run_assessment(input_data)
        assert result['cct'] == 1.0
    
    def test_complex_cct(self):
        """Test CCT=1.15 for complex terrain."""
        input_data = {
            'edition': 'ed4',
            'vref': 42.5,
            'iref': 0.14,
            'vave': 8.5,
            'v50': 40.0,
            'rho': 1.225,
            'complexity': 'complex',
            'bin_width': 1.0,
            'period_hours': 8760,
            'ti_bins': []
        }
        
        result = run_assessment(input_data)
        assert result['cct'] == 1.15


class TestDensityCorrection:
    """Test air density checks."""
    
    def test_density_above_standard_fails(self):
        """Test that rho > 1.225 fails density check."""
        input_data = {
            'edition': 'ed4',
            'vref': 42.5,
            'iref': 0.14,
            'vave': 8.5,
            'v50': 40.0,
            'rho': 1.3,
            'complexity': 'simple',
            'bin_width': 1.0,
            'period_hours': 8760,
            'ti_bins': []
        }
        
        result = run_assessment(input_data)
        density_check = [c for c in result['checks'] if c['check_id'] == 'air_density'][0]
        assert density_check['status'] == 'Fail'
        assert density_check['detail']['reason'] == 'density_compensation_unlicensed'
    
    def test_density_apply_to_v50(self):
        """Test density correction applied to V50."""
        input_data = {
            'edition': 'ed4',
            'vref': 42.5,
            'iref': 0.14,
            'vave': 8.5,
            'v50': 40.0,
            'rho': 1.1,
            'apply_density_to_v50': True,
            'complexity': 'simple',
            'bin_width': 1.0,
            'period_hours': 8760,
            'ti_bins': []
        }
        
        result = run_assessment(input_data)
        extreme_wind_check = [c for c in result['checks'] if c['check_id'] == 'extreme_wind'][0]
        
        # V_use = V50 * sqrt(rho/1.225) = 40 * sqrt(1.1/1.225)
        import math
        expected_v_use = 40.0 * math.sqrt(1.1 / 1.225)
        assert_float_close(extreme_wind_check['value'], expected_v_use)
        assert 'rho_ne_std' in extreme_wind_check['flags']


class TestEmptyWindow:
    """Test empty TI window handling."""
    
    def test_empty_ti_window_fails(self):
        """Test that empty TI window results in Fail with flag."""
        input_data = {
            'edition': 'ed4',
            'vref': 42.5,
            'iref': 0.14,
            'vave': 8.5,
            'v50': 40.0,
            'rho': 1.225,
            'complexity': 'simple',
            'bin_width': 1.0,
            'period_hours': 8760,
            'ti_bins': [
                {'v_center': 1.0, 'hours': 100, 'mean_sigma': 0.1, 'std_sigma': 0.02},
                {'v_center': 2.0, 'hours': 200, 'mean_sigma': 0.2, 'std_sigma': 0.04}
            ]
        }
        
        result = run_assessment(input_data)
        ti_check = [c for c in result['checks'] if c['check_id'] == 'turbulence_ntm'][0]
        assert ti_check['status'] == 'Fail'
        assert 'empty_ti_window' in ti_check['flags']
