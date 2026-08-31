# Site Package Ingest API - site-package-v1

## Overview

The ingest API accepts wind farm site data in multiple formats (JSON, Excel, CSV, HTML screening reports) and converts them to the canonical `site-package-v1` JSON format. Users can preview the parsed data and validation gaps before committing it to the database.

## Workflow

1. **POST Upload** - User uploads report/Excel/CSV file
2. **Parse** - Convert to JSON site-package-v1 format
3. **Preview** - Show parsed data, validation gaps, no DB write
4. **Commit** - Persist to Django models (Project, Site, Layout, Turbines, etc.)
5. **Assess** - Run existing Slice 0+1 assessment on the layout

## Data Models Persisted

When committing a site package, the following Django models are created/updated:

- **Project** - Wind turbine project container
- **ClassEnvelope** - Wind class envelope parameters (only numerics stated in file; otherwise Django defaults + gap flag)
- **Site** - Wind farm site with CRS calculation
- **Layout** - Turbine layout for a site
- **Turbine** - Individual turbine instances
- **WtgModel** - Turbine generator model specification
- **PowerCurvePoint** - Power curve data points
- **CtCurvePoint** - Thrust coefficient curve points
- **HubClimate** - Hub-height climate data for assessment
- **TiBin** - TI bin data for HubClimate
- **SectorWeibull** - Optional sector wind rose data (if present)

## site-package-v1 JSON Format

### Root Structure

```json
{
  "package_version": "site-package-v1",
  "project": { ... },
  "site": { ... },
  "class_envelope": { ... },
  "layout": { ... },
  "wtg_models": [ ... ],
  "hub_climates": [ ... ],
  "gaps": [ ... ]
}
```

### Project

```json
"project": {
  "name": "Synthetic Ridge Wind Farm",
  "notes": "Example site package for testing"
}
```

### Site

```json
"site": {
  "name": "Synthetic Ridge Site",
  "center_lon_deg": 45.0,
  "center_lat_deg": 9.0,
  "default_complexity": "simple"
}
```

### Class Envelope

```json
"class_envelope": {
  "vref_i": 50.0,
  "vref_ii": 42.5,
  "vref_iii": 37.5,
  "iref_a_plus": 0.18,
  "iref_a": 0.16,
  "iref_b": 0.14,
  "iref_c": 0.12,
  "vave_over_vref": 0.2
}
```

### Layout

```json
"layout": {
  "name": "Main Layout",
  "turbines": [
    {
      "local_id": "T01",
      "role": "new_scored",
      "x_m": 0.0,
      "y_m": 0.0,
      "z_base_m": 100.0,
      "hub_height_m": 120.0,
      "rotor_d_m": 120.0,
      "model_name": "N123-120"
    },
    {
      "local_id": "E01",
      "role": "existing_wake_source",
      "x_m": 0.0,
      "y_m": 960.0,
      "z_base_m": 100.0,
      "hub_height_m": 120.0,
      "rotor_d_m": 120.0,
      "model_name": "N123-120"
    }
  ]
}
```

**Turbine Roles:**
- `new_scored` - New turbine to be scored in assessment (default)
- `existing_wake_source` - Existing turbine that acts as wake source but not scored

**Validation:**
- Duplicate `local_id` within a layout is rejected (all-or-nothing on commit)

### WTG Models

```json
"wtg_models": [
  {
    "name": "N123-120",
    "rotor_d_m": 120.0,
    "hub_height_default_m": 120.0,
    "v_in_mps": 3.0,
    "v_rated_mps": 12.0,
    "v_out_mps": 25.0,
    "default_speed_class": "II",
    "default_ti_category": "B",
    "power_curve": [
      {"v_mps": 3.0, "p_kw": 0.0},
      {"v_mps": 12.0, "p_kw": 3000.0},
      {"v_mps": 25.0, "p_kw": 3000.0}
    ],
    "ct_curve": [
      {"v_mps": 0.0, "ct": 0.0},
      {"v_mps": 12.0, "ct": 0.8},
      {"v_mps": 25.0, "ct": 0.05}
    ]
  }
]
```

**Missing Ct Handling:**
- If `ct_curve` is empty or missing → `ct_status = "missing"`, gap with `ct_missing` code
- Do NOT invent Ct values (e.g., 7/V fallback)
- Slice 1 assessment handles fallback internally when flagged

### Hub Climates

```json
"hub_climates": [
  {
    "name": "GOLDEN_PASS_T1",
    "turbine_local_id": null,
    "period_hours": 8760.0,
    "bin_width_mps": 1.0,
    "rho_kgm3": 1.225,
    "v50_mps": 40.0,
    "shear_alpha": 0.2,
    "inflow_angle_deg": 3.0,
    "ti_bins": [
      {"v_center_mps": 1.0, "hours": 187.88556, "mean_sigma_mps": 0.1, "std_sigma_mps": 0.02},
      {"v_center_mps": 2.0, "hours": 363.735745, "mean_sigma_mps": 0.2, "std_sigma_mps": 0.04}
    ],
    "sector_weibull": []
  }
]
```

**TI Bins:**
- `std_sigma_mps` may be null/empty → COV=0.3 flag in assessment

**Sector Weibull (optional):**
```json
"sector_weibull": [
  {"sector_from_deg": 0, "sector_to_deg": 30, "frequency": 0.083, "A": 8.5, "k": 2.1}
]
```

### Gaps

Validation gaps with severity levels:

```json
"gaps": [
  {
    "severity": "run_blocker",
    "path": "layout.turbines[2]",
    "code": "missing_coordinates",
    "message": "Turbine T03 has missing X or Y coordinates",
    "source_hint": "Sheet: Layout, Row 4"
  },
  {
    "severity": "flag",
    "path": "wtg_models[0].ct_curve",
    "code": "ct_missing",
    "message": "Ct curve is empty for model N123-120",
    "source_hint": "Sheet: CtCurve"
  }
]
```

**Severity Levels:**
- `run_blocker` - Prevents commit and assessment execution
- `flag` - Warning, commit allowed, flagged in assessment
- `store_only_missing` - Data accepted but incomplete
- `unmapped_column` - Column in source not mapped to schema
- `invalid` - Data validation error

**Common Gap Codes:**
- `ct_missing` - Ct curve empty or missing
- `missing_coordinates` - Turbine position missing
- `duplicate_local_id` - Duplicate turbine ID in layout
- `invalid_class` - Invalid speed class or TI category
- `missing_v50` - V50 extreme wind speed missing

## Input Formats

### 1. JSON (site-package-v1)

Direct JSON upload matching the canonical format above.

### 2. CSV Files

**Turbines CSV** (`turbines.csv`):
```
local_id,role,x_m,y_m,z_base_m,hub_height_m,rotor_d_m,model_name
T01,new_scored,0.0,0.0,100.0,120.0,120.0,N123-120
E01,existing_wake_source,0.0,960.0,100.0,120.0,120.0,N123-120
```
- UTF-8 encoding with header
- `role` defaults to `new_scored` if omitted
- Duplicate `local_id` rejected on commit (all-or-nothing)

**TI Bins CSV** (`ti_bins.csv`):
```
v_center_mps,hours,mean_sigma_mps,std_sigma_mps
1.0,187.88556,0.1,0.02
2.0,363.735745,0.2,0.04
```
- `std_sigma_mps` may be empty (null)

**Set of CSVs** (uploaded as ZIP):
- `site.csv` - Site metadata
- `wtg_models.csv` - Turbine models
- `power_curve.csv` - Power curve points
- `ct_curve.csv` - Ct curve points
- `hub_climate.csv` - Climate metadata
- `sector_weibull.csv` - Sector wind rose (optional)
- `turbines.csv` - Layout turbines

### 3. Excel (.xlsx)

**Sheet Names** (aliases accepted, case-insensitive):
- `Site` - Site metadata
- `Layout` or `WTGs` or `Turbines` - Turbine layout
- `WtgModels` - Turbine models
- `PowerCurve` - Power curve points
- `CtCurve` - Ct curve points
- `HubClimate` - Climate metadata
- `TiBins` - TI bins
- `SectorWeibull` - Optional sector wind rose

**Header Processing:**
- Case-insensitive matching
- Strip units in brackets `[]` or parentheses `()` from headers
- Example: `V [m/s]` → `v_mps`

**Combined Class Cell:**
- Single cell like `IIB` → speed class `II` + TI category `B`
- Split and map to `default_speed_class` and `default_ti_category`

### 4. HTML Screening Report

Parse HTML screening reports for:
- Climate/class/TI table data
- **Do NOT scrape Pass/Fail as climate data**
- Coordinates often missing → `run_blocker` gap

### Rejected Formats

The following formats are **NOT supported** and will be rejected with clear error:
- WAsP-CFD files
- Flowres files
- LOAD RESPONSE files
- `.map` / `.lib` files
- GeoTIFF DEM files
- Shapefile (.shp)

Display **screening disclaimer** on ingest pages:
> "This is an IEC 61400-1-inspired screening tool, not a certified assessment. User-editable class envelope, not IEC Table 1 classes."

## Field Name Mapping

Ensure compatibility with current `main` branch field names:

| Model | Field | Description |
|-------|-------|-------------|
| WtgModel | `v_in_mps` | Cut-in wind speed (m/s) |
| WtgModel | `v_rated_mps` | Rated wind speed (m/s) |
| WtgModel | `v_out_mps` | Cut-out wind speed (m/s) |
| HubClimate | `inflow_angle_deg` | Omni-directional inflow angle (deg) |
| Turbine | `role` | `new_scored` or `existing_wake_source` |

## Validation Rules

### What to NEVER Invent:
- **Vref** - Reference wind speed
- **Iref** - Reference turbulence intensity
- **V50** - 50-year extreme wind speed
- **σ (sigma)** - Turbulence standard deviation
- **Ct** - Thrust coefficient
- **Class numbers** - Speed class or TI category
- **Coordinates** - Turbine X/Y/Z positions

### Missing Ct Handling:
1. If Ct curve is empty or missing:
   - Set `ct_status = "missing"`
   - Add gap with severity `flag` and code `ct_missing`
   - Do NOT write 7/V fallback points to database
2. Slice 1 calculation (`turbulence_ieff`) handles flagged fallback internally

### Duplicate Local ID:
- If duplicate `local_id` found in layout during commit:
  - Reject entire layout (all-or-nothing)
  - Add gap with severity `run_blocker` and code `duplicate_local_id`
  - Nothing persisted to database

## API Endpoints

### POST `/ingest/upload/`
Upload file (JSON/Excel/CSV/HTML) and parse to site-package-v1 format.

**Request:**
- Multipart form data with `file` field
- Accepted content types: `application/json`, `application/vnd.openxmlformats-officedocument.spreadsheetml.sheet`, `text/csv`, `text/html`, `application/zip`

**Response:**
```json
{
  "status": "success",
  "package": { ... },
  "gaps": [ ... ],
  "preview_url": "/ingest/preview/<session_id>/"
}
```

### GET `/ingest/preview/<session_id>/`
Display parsed site package with gaps for user review.

**Response:**
- HTML page with:
  - Project/Site/Layout summary
  - Turbine count and models
  - Climate data summary
  - Gap list with severity indicators
  - Commit button (disabled if `run_blocker` gaps exist)

### POST `/ingest/commit/<session_id>/`
Persist site package to Django database.

**Response:**
```json
{
  "status": "success",
  "project_uuid": "123e4567-e89b-12d3-a456-426614174000",
  "site_id": 1,
  "layout_id": 1,
  "turbine_count": 9,
  "redirect_url": "/sites/1/"
}
```

**Error (run_blocker gaps):**
```json
{
  "status": "error",
  "message": "Cannot commit: 2 run_blocker gaps present",
  "gaps": [ ... ]
}
```

## Testing Requirements

All tests must be in `tests/test_ingest.py` and must PASS in CI.

### Test 1: Round-Trip Example Site Package
**Synthetic Ridge Layout:**
- Site: 9°E 45°N (lon, lat)
- T01 at (0, 0) `new_scored`
- E01 at (0, 960) `existing_wake_source` (8D spacing)
- N123-120 model with golden Ct curve
- HubClimate: GOLDEN_PASS_T1 climate
  - V50 = 40 m/s
  - rho = 1.225 kg/m³
  - alpha = 0.2
  - inflow_angle_deg = 3°

**Test Steps:**
1. Load `docs/ingest/example_site_package.json`
2. Commit to database
3. Verify all objects exist:
   - Project, Site, Layout created
   - 2 Turbines (T01, E01)
   - WtgModel N123-120 with Ct curve
   - HubClimate with TI bins
4. Run Slice 0+1 assessment
5. Verify assessment completes successfully

### Test 2: Missing Ct Stays Empty
**Test Steps:**
1. Upload site package with WtgModel having empty `ct_curve`
2. Verify gap added: severity=`flag`, code=`ct_missing`
3. Commit package
4. Verify `ct_status = "missing"` on WtgModel
5. Verify NO 7/V rows in `CtCurvePoint` table for that model

### Test 3: Duplicate Local ID Rejected
**Test Steps:**
1. Create site package with duplicate `local_id` in layout
2. Attempt commit
3. Verify gap added: severity=`run_blocker`, code=`duplicate_local_id`
4. Verify commit fails
5. Verify NO objects persisted (rollback)

### Test 4: Existing Slice 0 and Slice 1 Goldens Stay Green
**Test Steps:**
1. Run existing golden tests:
   - `tests/test_slice1_ieff.py::test_golden_ieff_pass`
   - `tests/test_slice1_ieff.py::test_golden_ieff_fail`
   - `tests/test_engine.py::test_golden_pass`
   - `tests/test_engine.py::test_golden_fail`
2. Verify all tests PASS
3. Ensure no regressions from ingest changes

## UI Requirements

### Upload Page (`/ingest/upload/`)
- Simple file upload form (not admin-only)
- Accepted formats listed
- Screening disclaimer displayed
- Clear error messages for rejected formats

### Preview Page (`/ingest/preview/<session_id>/`)
- Project/Site/Layout summary
- Turbine table with coordinates, roles, models
- Climate data summary
- Gap list with severity badges:
  - 🔴 `run_blocker` - Red badge
  - 🟡 `flag` - Yellow badge
  - 🔵 `store_only_missing` - Blue badge
  - ⚪ `unmapped_column` - Gray badge
- Commit button:
  - Disabled if `run_blocker` gaps exist
  - Shows tooltip explaining blockers

### Integration with Existing Nav
- Wire ingest into existing project/site navigation if easy
- No new design system required
- Use existing templates (`templates/base.html`) for consistency

## Out of Scope

The following are **NOT** part of this implementation:
- WAsP/DEM engine integration
- LOAD RESPONSE calculations
- EMD yellow-band thresholds
- Changing `engine.py` formulas
- Modifying Ieff kernel
- Rebuilding the UI design system
- METEO Path A 10-min as V50 substitute

## Success Criteria

✅ PR vs `main` branch
✅ Green CI (all tests pass)
✅ Preview+commit workflow functional
✅ Example site package round-trips successfully
✅ Disclaimer present on ingest pages
✅ No regressions in existing Slice 0/1 golden tests
