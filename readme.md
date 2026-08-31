# Wind Turbine Site Suitability Web App

**DISCLAIMER:** Screening against a user-editable class envelope, not a certified IEC 61400-1 assessment.

A Django-based web application for assessing wind turbine site suitability based on IEC 61400-1 inspired criteria. This is a screening tool that evaluates sites against user-editable class envelopes.

## Features

- **Django 5.x** with Python 3.12
- **PostGIS** for geographic data
- **Five Django apps:**
  - `projects` - Project and class envelope management
  - `sites` - Site definitions with automatic CRS calculation
  - `turbines` - Wind turbine models, layouts, and positions
  - `climate` - Hub climate data and TI bins
  - `assessments` - Site suitability assessments with 7 checks
- **Assessment checks:**
  1. Complexity (CCT factor)
  2. Extreme wind
  3. Wind distribution (Rayleigh comparison)
  4. Turbulence NTM with damage-equivalent ratios (Slice 0)
  5. Effective turbulence with wake (Slice 1, Frandsen-inspired)
  6. Shear (energy-weighted)
  7. Inflow angle (energy-weighted)
  8. Air density
- **Test coverage** with pytest and golden test fixtures
- **CI/CD** with GitHub Actions running tests on every push/PR
- **HTML reports** with disclaimer (Slice 0 reports are HTML-only; PDF is later)

## What This Tool Does NOT Include

This screening tool does NOT implement:
- WAsP wind flow modeling
- PARK or other AEP calculations
- MCP (Measure-Correlate-Predict)
- Mesoscale wind data
- DEM terrain complexity analysis (WindPRO 25-plane fit)
- Turbine load response calculations
- EMD yellow-band numeric thresholds
- Large-farm wake correction models

## Slice 1: Effective Turbulence (Frandsen-Inspired Wake Model)

**Added:** Effective turbulence assessment with wake contributions as check ID `turbulence_ieff`.

This is a SECOND turbulence check that runs alongside the existing ambient NTM check from Slice 0. It uses a public A1/Ct wake kernel:

```
σ_wake = V / (1.5 + 0.8 · (d/D_up) / √Ct)
σ_T = sqrt(σ_wake² + σ_c²)  for nearest neighbor in 30° sector with d ≤ 10 D
σ_eff = (Σ_j p_j · σ_T^m)^(1/m)  with m=10 for direction weighting
```

**Key features:**
- 30° sector binning (12 sectors, nearest neighbor per sector)
- 10D distance cutoff
- Ct fallback: Ct = 7/V if curve missing (flagged)
- Omni-directional default (uniform 1/12 per sector, flagged)
- Status: Pass if no exceedance; Warn if exceed but R(10)≤1; Fail if R(10)>1

**Public domain reference:** DNV-style formulation, not IEC Edition 3 coefficients. See `docs/slice1/SLICE1_CALC_SPEC.md` for full specification.

**Important:** This is screening against a user-editable class envelope, not a certified IEC 61400-1 assessment. Do not use for load response calculations.

## Quick Start

### 1. Start the database

```bash
docker-compose up -d
```

This starts a PostGIS database on port 5432.

### 2. Install dependencies

```bash
pip install -r requirements.txt
```

### 3. Run migrations

```bash
python manage.py migrate
```

### 4. Create a superuser

```bash
python manage.py createsuperuser
```

### 5. Run the development server

```bash
python manage.py runserver
```

Access the app at http://localhost:8000 and admin at http://localhost:8000/admin/

## Running Tests

```bash
pytest
```

Or with coverage:

```bash
pytest --cov=. --cov-report=html
```

All tests must pass before merging. CI runs tests automatically on every push.

## Sample Assessment Workflow

### 1. Create a project via admin

1. Go to http://localhost:8000/admin/
2. Create a Project (e.g., "North Wind Farm")
3. A ClassEnvelope is automatically created with IEC-inspired defaults:
   - Vref I/II/III = 50/42.5/37.5 m/s
   - Iref A+/A/B/C = 0.18/0.16/0.14/0.12
   - Vave/Vref = 0.2

### 2. Create a site

1. Add a Site with center coordinates (lon/lat in EPSG:4326)
2. The system automatically calculates UTM zone and CRS
3. Set default complexity: `simple` (CCT=1.0) or `complex` (CCT=1.15)

### 3. Create a WTG model

1. Add a WtgModel with specifications
2. Add PowerCurvePoints and CtCurvePoints if available
3. The system checks Ct curve validity

### 4. Create a layout and turbine

1. Add a Layout for the site
2. Add a Turbine with:
   - `local_id` (e.g., "T01")
   - `role` = `new_scored` (only scored turbines are assessed)
   - Position in site CRS (x_m, y_m, z_base_m)
   - Hub height and rotor diameter
   - Link to WtgModel

### 5. Create hub climate data

1. Add a HubClimate for the site
2. Add TiBin records for each wind speed bin with:
   - `v_center_mps` - bin center wind speed
   - `hours` - hours in this bin
   - `mean_sigma_mps` - mean turbulence std dev
   - `std_sigma_mps` - std dev of sigma (null → COV=0.3 assumed)
3. Set V50, rho, bin_width, and optional shear_alpha / inflow_angle_deg

### 6. Create an assessment

1. Add an Assessment
2. Link to project and site
3. Choose edition (`ed4` or `ed3`)
4. Add an AssessmentTurbine linking:
   - The turbine to assess
   - The hub climate to use
   - Resolved Vref, Iref, Vave from class envelope
   - CCT will be calculated
   - Optional wohler_exponents (default [4, 10])

### 7. Run the assessment

**Via management command:**
```bash
python manage.py run_assessment <assessment_id>
```

**Via web interface:**
Visit http://localhost:8000/assessments/ and click "Run" for your assessment.

### 8. View the report

Visit http://localhost:8000/assessments/<id>/report/ to see the HTML report with all check results and the disclaimer.

## CRS Calculation

Sites automatically calculate their UTM zone and EPSG code from center coordinates:

```python
zone = floor((lon + 180) / 6) + 1
epsg = 32600 + zone if lat >= 0 else 32700 + zone
```

All layout coordinates (turbine x, y) are in this CRS, in metres.

## Golden Tests

Four golden test fixtures are included:

**Slice 0 (Ambient Turbulence NTM):**
1. **GOLDEN_PASS_T1** - Class IIB, ed4, passing all checks
2. **GOLDEN_FAIL_T1** - Class IIB, ed4, failing extreme wind and turbulence

**Slice 1 (Effective Turbulence with Wake):**
3. **GOLDEN_IEFF_PASS** - 8D spacing, R(10)=0.852606, Pass
4. **GOLDEN_IEFF_FAIL** - 3D spacing, R(10)=1.246112, Fail

These are the contract. The numbers must match exactly (±1e-5 tolerance).

## Technology Stack

- **Backend:** Python 3.12, Django 5.1
- **Database:** PostgreSQL 16 with PostGIS 3.4
- **Testing:** pytest, pytest-django
- **CI:** GitHub Actions
- **GIS:** django.contrib.gis

## License

See LICENSE file for details.

## Contributing

1. All tests must pass locally and in CI
2. Follow Django conventions
3. Update tests for new features
4. Never invent IEC numbers - only use specified defaults
5. Always include the disclaimer in reports 
