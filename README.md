# Wind Site Suitability Assessment

IEC 61400-1 inspired site suitability screening tool. This is a screening tool, **not a certified IEC assessment**.

## Overview

This Django application provides a web interface for assessing wind farm site suitability based on IEC 61400-1 principles. It supports multiple layouts per site, CSV import for turbines and wind data, and comparative analysis between layouts.

## Features

- **Project and Site Management**: Create projects with multiple sites
- **Multiple Layouts**: Test different turbine configurations on the same site
- **CSV Import**: Bulk import turbines and wind climate data
- **IEC 61400-1 Inspired Assessment**: Screen sites against user-editable class envelopes
- **Layout Comparison**: Compare assessment results across multiple layouts

## Installation

### Requirements

- Python 3.9+
- PostgreSQL with PostGIS
- GDAL

### Setup

1. Clone the repository
2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
3. Set up database (PostgreSQL with PostGIS)
4. Run migrations:
   ```bash
   python manage.py migrate
   ```
5. Create a superuser (for admin access):
   ```bash
   python manage.py createsuperuser
   ```
6. Run the development server:
   ```bash
   python manage.py runserver
   ```

## Entering Turbines and Wind Data

### Getting Started

1. **Create a Project**: Navigate to the home page and click "Create New Project"
2. **Add a Site**: From the project detail page, click "Add Site" and enter:
   - Site name
   - Center coordinates (latitude/longitude in EPSG:4326)
   - Default terrain complexity (Simple or Complex)
3. **Create a Hub Climate**: From the site detail page, click "Add Hub Climate" to define wind conditions

### Entering Wind Climate Data

#### Manual Entry

1. Navigate to the site detail page
2. Click "Add Hub Climate"
3. Fill in the climate parameters:
   - **Name**: Descriptive name (e.g., "Hub 120m 2020-2021")
   - **Period Hours**: Total measurement period (default: 8760 hours for 1 year)
   - **Bin Width**: Wind speed bin width in m/s
   - **Air Density (ρ)**: Air density in kg/m³ (default: 1.225)
   - **V50**: 50-year extreme wind speed in m/s
   - **Shear Alpha**: Omni-directional shear exponent (optional)
   - **Inflow Angle**: Omni-directional inflow angle in degrees (optional)

#### CSV Import for TI Bins

Wind climate data can be imported from a CSV file containing turbulence intensity bins.

**CSV Format** (UTF-8 encoding with header row):

```csv
v_center_mps,hours,mean_sigma_mps,std_sigma_mps
4.0,120.5,0.45,0.12
5.0,245.8,0.52,0.15
6.0,389.2,0.58,0.18
7.0,512.3,0.64,0.20
...
```

**Columns:**
- `v_center_mps` (required): Bin center wind speed in m/s
- `hours` (required): Hours in this bin
- `mean_sigma_mps` (required): Mean standard deviation in m/s
- `std_sigma_mps` (optional): Standard deviation of sigma in m/s. May be empty; if missing, COV=0.3 will be assumed and flagged during assessment

**To Import:**
1. Navigate to the hub climate detail page
2. Click "Import CSV"
3. Upload your CSV file
4. If bins already exist, check "Replace existing bins" to overwrite them

### Creating Layouts and Adding Turbines

#### Create a Layout

1. From the site detail page, click "New Layout"
2. Enter a descriptive name (e.g., "Layout A", "Layout B", "Alternative 1")

#### Manual Turbine Entry

1. Navigate to the layout detail page
2. Click "Add Turbine"
3. Fill in the turbine parameters:
   - **Local ID**: Unique identifier within the layout (e.g., "T01", "WTG-01")
   - **Role**: Either "New (scored)" or "Existing (wake source)"
     - New turbines are assessed
     - Existing turbines are stored but not scored (reserved for future wake calculations)
   - **Coordinates**: X (Easting), Y (Northing), Z Base elevation in site CRS (meters)
   - **Hub Height**: Hub height above base in meters
   - **Rotor Diameter**: Rotor diameter in meters
   - **Model**: Select from available WTG models (optional)

#### CSV Import for Turbines

Bulk import turbines from a CSV file.

**CSV Format** (UTF-8 encoding with header row):

```csv
local_id,role,x_m,y_m,z_base_m,hub_height_m,rotor_d_m,model_name
T01,new_scored,563120.5,6223450.2,45.0,120.0,150.0,V150-4.2
T02,new_scored,563670.8,6223450.2,46.5,120.0,150.0,V150-4.2
T03,new_scored,564221.1,6223450.2,48.0,120.0,150.0,V150-4.2
T04,existing_wake_source,562570.0,6224000.0,50.0,115.0,140.0,V140-4.0
...
```

**Columns:**
- `local_id` (required): Unique identifier within this layout
- `role` (optional): Either "new_scored" or "existing_wake_source" (default: new_scored)
- `x_m` (required): Easting in site CRS (meters)
- `y_m` (required): Northing in site CRS (meters)
- `z_base_m` (required): Base elevation (meters)
- `hub_height_m` (required): Hub height above base (meters)
- `rotor_d_m` (required): Rotor diameter (meters)
- `model_name` (optional): WTG model name
  - If the model exists in the database, it will be linked
  - If the model doesn't exist but `rotor_d_m` and `hub_height_m` are provided, a stub model will be created with `ct_status=missing` and flagged
  - **Never invent Ct values** - models without thrust coefficient data will be flagged

**Import Behavior:**
- **All-or-nothing**: If any row has errors, no turbines will be imported. Clear error messages will be shown
- **Duplicate Detection**: Duplicate `local_id` values within the same layout will be rejected

**To Import:**
1. Navigate to the layout detail page
2. Click "Import CSV"
3. Upload your CSV file
4. Review any warnings (e.g., stub models created)

### Running Assessments

#### Assess a Single Layout

1. Navigate to the layout detail page
2. Click "Run Assessment"
3. Select a hub climate from the dropdown
4. Choose IEC edition (Edition 4 or Edition 3)
5. Click "Create and Run Assessment"

The assessment will be created and run for all turbines with role "new_scored". Results will show:
- Overall status per turbine (Pass/Warn/Fail)
- Detailed check results:
  - Extreme Wind
  - Wind Distribution (Rayleigh)
  - Turbulence NTM
  - Shear
  - Inflow Angle
  - Air Density
  - Terrain Complexity

#### Compare Multiple Layouts

1. Navigate to the site detail page
2. Click "Compare Layouts"
3. View a summary table showing:
   - Layout name
   - Turbine count
   - Overall status (worst check across all turbines)
   - Worst check name
   - Quick link to run assessment

This allows you to quickly see which layout configuration performs best at the site.

## Assessment Disclaimer

**This is a screening tool for IEC 61400-1 inspired site suitability assessment. This is NOT a certified IEC assessment.**

The tool performs checks against a user-editable class envelope, not the full IEC 61400-1 standard. Results are indicative and should be used for preliminary screening only. Final site assessments must be performed by qualified engineers following the complete IEC 61400-1 standard.

## Data Model

```
Project
├── Site(s)
│   ├── Layout(s)
│   │   └── Turbine(s)
│   └── HubClimate(s)
│       └── TiBin(s)
└── Assessment(s)
    └── AssessmentTurbine(s)
        └── CheckResult(s)
```

- **One Site has many Layouts**: Test different turbine arrangements
- **Each Layout has many Turbines**: Position-specific turbine data
- **Hub Climate belongs to Site**: Wind conditions shared across layouts
- **Assessments link Turbines and HubClimate**: Results specific to turbine-climate combination

## Testing

Run the test suite:

```bash
pytest
```

Tests cover:
- CSV import for turbines (single layout, multiple layouts, duplicate detection)
- CSV import for wind data (TI bins, empty std_sigma handling)
- Assessment isolation between layouts
- Layout comparison views

## License

See LICENSE file for details.
