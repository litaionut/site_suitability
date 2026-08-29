#!/usr/bin/env python3
"""
Standalone test for the assessment engine (no Django required).
"""
import json
import sys
from pathlib import Path

# Add assessments to path
sys.path.insert(0, str(Path(__file__).parent))

from assessments.engine import run_assessment


def assert_float_close(actual, expected, rel_tol=1e-5, abs_tol=1e-5, path=""):
    """Assert two floats are close with tolerance."""
    if expected is None and actual is None:
        return
    if expected is None or actual is None:
        raise AssertionError(f"{path}: Expected {expected}, got {actual}")
    if abs(actual - expected) >= abs_tol + rel_tol * abs(expected):
        raise AssertionError(f"{path}: Expected {expected}, got {actual}, diff={abs(actual-expected)}")


def test_golden_file(filename, test_name):
    """Test a golden JSON file."""
    print(f"\n{'='*60}")
    print(f"Testing {test_name}: {filename}")
    print('='*60)
    
    with open(Path(__file__).parent / 'tests' / filename, 'r') as f:
        golden = json.load(f)
    
    print(f"Description: {golden['description']}")
    
    result = run_assessment(golden['input'])
    
    if 'error' in result:
        print(f"ERROR: {result['error']}")
        return False
    
    expected = golden['expected']
    
    # Check overall
    print(f"\nOverall Status: {result['overall']} (expected: {expected['overall']})")
    assert result['overall'] == expected['overall'], f"Overall mismatch"
    
    print(f"CCT: {result['cct']} (expected: {expected['cct']})")
    assert result['cct'] == expected['cct'], f"CCT mismatch"
    
    print(f"Speed Range: {result['speed_range']} (expected: {expected['speed_range']})")
    assert result['speed_range'] == expected['speed_range'], f"Speed range mismatch"
    
    print(f"Flags: {result['flags']} (expected: {expected['flags']})")
    assert set(result['flags']) == set(expected['flags']), f"Flags mismatch"
    
    # Check each check
    print("\nCheck Results:")
    for check in result['checks']:
        check_id = check['check_id']
        expected_check = expected['checks'][check_id]
        
        print(f"\n  {check_id}:")
        print(f"    Status: {check['status']} (expected: {expected_check['status']})")
        assert check['status'] == expected_check['status'], f"{check_id}: Status mismatch"
        
        # Check detail values
        for key, expected_val in expected_check.get('detail', {}).items():
            actual_val = check['detail'].get(key)
            if isinstance(expected_val, float):
                print(f"    {key}: {actual_val:.6f} (expected: {expected_val:.6f})")
                assert_float_close(actual_val, expected_val, path=f"{check_id}.{key}")
            else:
                print(f"    {key}: {actual_val} (expected: {expected_val})")
                assert actual_val == expected_val, f"{check_id}.{key}: Expected {expected_val}, got {actual_val}"
    
    print(f"\n✅ {test_name} PASSED")
    return True


def main():
    """Run all golden tests."""
    print("="*60)
    print("WIND TURBINE SITE SUITABILITY - ENGINE TESTS")
    print("="*60)
    
    all_passed = True
    
    try:
        if not test_golden_file('golden_pass_t1.json', 'GOLDEN_PASS_T1'):
            all_passed = False
    except Exception as e:
        print(f"\n❌ GOLDEN_PASS_T1 FAILED: {e}")
        import traceback
        traceback.print_exc()
        all_passed = False
    
    try:
        if not test_golden_file('golden_fail_t1.json', 'GOLDEN_FAIL_T1'):
            all_passed = False
    except Exception as e:
        print(f"\n❌ GOLDEN_FAIL_T1 FAILED: {e}")
        import traceback
        traceback.print_exc()
        all_passed = False
    
    print("\n" + "="*60)
    if all_passed:
        print("✅ ALL TESTS PASSED")
        print("="*60)
        return 0
    else:
        print("❌ SOME TESTS FAILED")
        print("="*60)
        return 1


if __name__ == '__main__':
    sys.exit(main())
