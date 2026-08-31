# Slice 1: Effective Turbulence (turbulence_ieff) Calculation Specification

**STATUS:** Master Bot ACCEPTED

## Overview

Slice 1 adds effective turbulence assessment with wake contributions as a SECOND check alongside the existing Slice 0 ambient turbulence NTM check. This is check ID `turbulence_ieff`.

**IMPORTANT:** This does NOT replace `turbulence_ntm`. Both checks run. Slice 0 golden tests PASS_T1 and FAIL_T1 must remain valid.

## Calculation Kernel (Public A1/Ct formulation)

For each wind speed bin `i` and direction sector `j`:

### 1. Ambient Component
```
σ_c = σ90 · CCT
```
Where:
- σ90 = mean_sigma + 1.28 · std_sigma (as in Slice 0)
- CCT = complexity correction (1.00 simple, 1.15 complex)

### 2. Wake Component (Nearest Neighbor Only)

For the nearest neighbor within the 30° sector containing bearing to neighbor:

```
σ_wake = V / (1.5 + 0.8 · (d/D_up) / √Ct)
```

Where:
- V = bin center wind speed (m/s)
- d = distance between turbines (m)
- D_up = upstream (neighbor) rotor diameter (m)
- Ct = thrust coefficient at speed V (interpolated from ct_curve)

**Distance cutoff:** Only apply wake if d ≤ 10 D_up. Otherwise σ_T = σ_c.

### 3. Total Turbulence
```
σ_T,i,j = sqrt(σ_wake² + σ_c²)  if nearest neighbor exists with d ≤ 10 D
σ_T,i,j = σ_c                   otherwise
```

### 4. Direction-Weighted Effective Turbulence

Using Wöhler exponent m=10 for status (m=4 for diagnostic):

```
σ_eff,i = (Σ_j p_j · σ_T,i,j^m)^(1/m)
```

Where:
- p_j = sector frequency (from SectorWeibull if available, else uniform 1/12)
- Sum over all 12 sectors (30° each)

### 5. NTM Reference
```
σ1(V) = Iref · (0.75 · V + 5.6)
```

### 6. Damage-Equivalent Ratio

Same form as Slice 0 but with σ_eff on site side:

```
R(m) = (Σ_i p_i · σ_eff,i^m)^(1/m) / (Σ_i p_i · σ1,i^m)^(1/m)
```

Where:
- p_i = hours_i / total_hours_in_window
- i ranges over bins in speed window

## Wake Modeling Rules

### Sector Binning
- **30° sectors**: 0-30°, 30-60°, ..., 330-360° (12 sectors total)
- Bearing from target to neighbor determines sector assignment
- Bearing convention: 0° = North, 90° = East, clockwise
- **Flag:** `view_angle_bin_width_30` (documents 21.6° design but 30° implementation)

### Neighbor Selection
- **Nearest neighbor in each sector only** (not all neighbors)
- Distance measured center-to-center (Euclidean)
- Only consider neighbors with d ≤ 10 D_up
- **Sources:** All turbines in layout with rotor_d_m > 0:
  - `role = new_scored` (also wake sources, can be scored)
  - `role = existing_wake_source` (source only, never scored)
- **Never self-wake** (exclude target turbine itself)

### Ct Curve Handling
- **Interpolate** ct_curve linear between points
- **Extrapolate flat** at boundaries
- **Missing Ct curve:** Use fallback Ct = 7/V and set flag `ct_missing`
- **Invalid Ct (≤0):** Treat as missing, use fallback

## Direction Integration

### With Sector Data (SectorWeibull)
- Use provided sector frequencies p_j
- Must sum to 1.0 (validate)

### Omni-Directional (No Sectors)
- Assume uniform 1/12 per sector
- Set flag `omni_rose_assumed`
- Wake is still geometric (directional) even though ambient TI is omni

## Status Determination

Uses **R(10) only** for status (R(4) is diagnostic):

- **Pass:** All bins σ_eff,i ≤ σ1,i
- **Warn:** Some bins exceed but R(10) ≤ 1.0
- **Fail:** R(10) > 1.0

## Golden Test Requirements

### Test Setup
- **Class IIB ed4:** Vref = 42.5 m/s, Iref = 0.14
- **Climate:** Slice 0 PASS_T1 climate with σ90 = 0.1256 · V
- **CCT:** 1.0 (simple terrain)
- **Speed window:** 9 to 17 m/s (Vave = 8.5, 2·Vave = 17)
- **Turbines:** D = 120 m, all at z = 0
- **Ct curve:** 0.80 for V ≤ 12 m/s, linear to 0.05 at V = 25 m/s
- **Direction:** Omni (uniform 1/12 per sector)

### Ct Curve Formula
```
V ≤ 12:     Ct = 0.80
12 < V < 25: Ct = 0.80 + (0.05 - 0.80) · (V - 12) / (25 - 12)
V ≥ 25:     Ct = 0.05
```

At V = 15 m/s:
```
Ct = 0.80 + (0.05 - 0.80) · (15 - 12) / 13
   = 0.80 - 0.75 · 3/13
   = 0.80 - 0.173077
   = 0.626923
```

### GOLDEN_IEFF_PASS (8 D spacing)
- **E1 position:** (0, 960)
- **E2 position:** (0, 0) [implied neighbor]
- **Distance:** d = 960 m = 8 D
- **At V = 15 m/s:**
  - Ct = 0.626923
  - σ_c = 0.1256 · 15 · 1.0 = 1.884
  - σ_wake = 15 / (1.5 + 0.8 · 8 / √0.626923) = 15 / (1.5 + 0.8 · 10.0980) = 15 / 9.5784 = 1.5656
  - σ_T = √(1.5656² + 1.884²) = √(2.4511 + 3.5495) = √6.0006 = 2.4497
  - σ1 = 0.14 · (0.75 · 15 + 5.6) = 0.14 · 16.85 = 2.359
  - σ_eff = 2.026 (direction-weighted with m=10)
  - **R(10) = 0.852606** → **Pass**

### GOLDEN_IEFF_FAIL (3 D spacing)
- **E1 position:** (0, 360)
- **E2 position:** (0, 0)
- **Distance:** d = 360 m = 3 D
- **At V = 15 m/s:**
  - σ_wake = 15 / (1.5 + 0.8 · 3 / √0.626923) = 15 / (1.5 + 3.0294) = 15 / 4.5294 = 3.3114
  - σ_T = √(3.3114² + 1.884²) = √(10.9654 + 3.5495) = √14.5149 = 3.8098
  - σ_eff = 2.974 (direction-weighted)
  - **R(10) = 1.246112** → **Fail**

### GOLDEN_IEFF_IDENTITY (10.1 D spacing)
- **Distance:** d = 10.1 D = 1212 m
- **Expected:** σ_eff = σ_c (no wake contribution, d > 10 D cutoff)

### Tolerance
- **Status:** Exact match (Pass/Warn/Fail)
- **Numeric values:** ±1e-5 absolute or ±1e-4 relative

## Exclusions (Out of Scope)

Slice 1 does NOT implement:
- WAsP wind flow modeling
- DEM terrain complexity engine (WindPRO 25-plane fit)
- LOAD RESPONSE calculations
- EMD yellow-band numeric thresholds
- Large-farm wake correction (σ_w term)
- Mean-speed wake deficit
- Edition 2 compatibility
- Tropical cyclone / seismic / lightning / icing

## Report Requirements

- **Check ID:** `turbulence_ieff` (separate from `turbulence_ntm`)
- **Label:** "Effective Turbulence (Frandsen)" or similar
- **Show:** Per-bin σ_eff vs σ1, R(4) and R(10), status, flags
- **Disclaimer:** "IEC 61400-1-inspired screening, not certification"
- **Do NOT label as "IEC Table 1" classes** (user-editable envelope)

## Implementation Notes

- Public domain A1/Ct formulation (DNV-style, not IEC Ed.3 0.9/0.3√V)
- Nearest-neighbor only (not full farm wake summation)
- 30° sector binning for practical implementation
- Conservative fallback for missing Ct data
- Screening tool only, not a certified assessment
