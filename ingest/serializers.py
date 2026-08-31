"""
site-package-v1 JSON serializers for validation and conversion.
"""
import json
from typing import Dict, List, Any, Optional


class Gap:
    """Validation gap with severity level."""
    SEVERITY_RUN_BLOCKER = 'run_blocker'
    SEVERITY_FLAG = 'flag'
    SEVERITY_STORE_ONLY_MISSING = 'store_only_missing'
    SEVERITY_UNMAPPED_COLUMN = 'unmapped_column'
    SEVERITY_INVALID = 'invalid'

    def __init__(self, severity: str, path: str, code: str, message: str, source_hint: str = ''):
        self.severity = severity
        self.path = path
        self.code = code
        self.message = message
        self.source_hint = source_hint

    def to_dict(self) -> Dict[str, str]:
        return {
            'severity': self.severity,
            'path': self.path,
            'code': self.code,
            'message': self.message,
            'source_hint': self.source_hint
        }


class SitePackageSerializer:
    """Validates and serializes site-package-v1 JSON format."""

    def __init__(self, data: Dict[str, Any]):
        self.data = data
        self.gaps: List[Gap] = []

    def validate(self) -> bool:
        """
        Validate site package structure and data.
        Returns True if no run_blocker gaps, False otherwise.
        """
        self._validate_version()
        self._validate_project()
        self._validate_site()
        self._validate_class_envelope()
        self._validate_layout()
        self._validate_wtg_models()
        self._validate_hub_climates()

        # Check for run_blocker gaps
        return not any(g.severity == Gap.SEVERITY_RUN_BLOCKER for g in self.gaps)

    def _validate_version(self):
        """Validate package version (schema_id or package_version alias)."""
        version = self.data.get('schema_id') or self.data.get('package_version')
        if version != 'site-package-v1':
            self.gaps.append(Gap(
                Gap.SEVERITY_RUN_BLOCKER,
                'schema_id',
                'invalid_version',
                f'Schema ID must be "site-package-v1", got "{version}"',
                ''
            ))

    def _validate_project(self):
        """Validate project data."""
        if 'project' not in self.data:
            self.gaps.append(Gap(
                Gap.SEVERITY_RUN_BLOCKER,
                'project',
                'missing_project',
                'Project data is required',
                ''
            ))
            return

        project = self.data['project']
        if not project.get('name'):
            self.gaps.append(Gap(
                Gap.SEVERITY_RUN_BLOCKER,
                'project.name',
                'missing_name',
                'Project name is required',
                ''
            ))

    def _validate_site(self):
        """Validate site data."""
        if 'site' not in self.data:
            self.gaps.append(Gap(
                Gap.SEVERITY_RUN_BLOCKER,
                'site',
                'missing_site',
                'Site data is required',
                ''
            ))
            return

        site = self.data['site']
        if not site.get('name'):
            self.gaps.append(Gap(
                Gap.SEVERITY_RUN_BLOCKER,
                'site.name',
                'missing_name',
                'Site name is required',
                ''
            ))

        # Validate coordinates
        if site.get('center_lon_deg') is None:
            self.gaps.append(Gap(
                Gap.SEVERITY_RUN_BLOCKER,
                'site.center_lon_deg',
                'missing_coordinates',
                'Site longitude is required',
                ''
            ))
        if site.get('center_lat_deg') is None:
            self.gaps.append(Gap(
                Gap.SEVERITY_RUN_BLOCKER,
                'site.center_lat_deg',
                'missing_coordinates',
                'Site latitude is required',
                ''
            ))

    def _validate_class_envelope(self):
        """Validate class envelope data (optional with defaults)."""
        class_env = self.data.get('class_envelope')
        if class_env is None or not class_env:
            self.gaps.append(Gap(
                Gap.SEVERITY_FLAG,
                'class_envelope',
                'class_envelope_django_defaults',
                'Class envelope null, using Django defaults',
                ''
            ))

    def _validate_layout(self):
        """Validate layout and turbines."""
        if 'layout' not in self.data:
            self.gaps.append(Gap(
                Gap.SEVERITY_RUN_BLOCKER,
                'layout',
                'missing_layout',
                'Layout data is required',
                ''
            ))
            return

        layout = self.data['layout']
        if not layout.get('name'):
            self.gaps.append(Gap(
                Gap.SEVERITY_FLAG,
                'layout.name',
                'missing_name',
                'Layout name not provided, will use default',
                ''
            ))

        turbines = layout.get('turbines', [])
        if not turbines:
            self.gaps.append(Gap(
                Gap.SEVERITY_RUN_BLOCKER,
                'layout.turbines',
                'no_turbines',
                'Layout has no turbines',
                ''
            ))
            return

        # Check for duplicate local_id
        local_ids = [t.get('local_id') for t in turbines if t.get('local_id')]
        if len(local_ids) != len(set(local_ids)):
            duplicates = [lid for lid in set(local_ids) if local_ids.count(lid) > 1]
            self.gaps.append(Gap(
                Gap.SEVERITY_RUN_BLOCKER,
                'layout.turbines',
                'duplicate_local_id',
                f'Duplicate turbine IDs found: {", ".join(duplicates)}',
                ''
            ))

        # Validate each turbine
        for idx, turbine in enumerate(turbines):
            self._validate_turbine(turbine, idx)

    def _validate_turbine(self, turbine: Dict[str, Any], idx: int):
        """Validate individual turbine data."""
        path_prefix = f'layout.turbines[{idx}]'

        required_fields = ['local_id', 'x_m', 'y_m', 'z_base_m', 'hub_height_m', 'rotor_d_m', 'model_name']
        for field in required_fields:
            if turbine.get(field) is None:
                self.gaps.append(Gap(
                    Gap.SEVERITY_RUN_BLOCKER,
                    f'{path_prefix}.{field}',
                    f'missing_{field}',
                    f'Turbine {turbine.get("local_id", f"#{idx}")} missing {field}',
                    ''
                ))

        # Validate role
        role = turbine.get('role', 'new_scored')
        valid_roles = ['new_scored', 'existing_wake_source']
        if role not in valid_roles:
            self.gaps.append(Gap(
                Gap.SEVERITY_INVALID,
                f'{path_prefix}.role',
                'invalid_role',
                f'Turbine {turbine.get("local_id")} has invalid role "{role}", must be one of: {", ".join(valid_roles)}',
                ''
            ))

    def _validate_wtg_models(self):
        """Validate WTG models."""
        if 'wtg_models' not in self.data:
            self.gaps.append(Gap(
                Gap.SEVERITY_RUN_BLOCKER,
                'wtg_models',
                'missing_wtg_models',
                'WTG models data is required',
                ''
            ))
            return

        models = self.data['wtg_models']
        if not models:
            self.gaps.append(Gap(
                Gap.SEVERITY_RUN_BLOCKER,
                'wtg_models',
                'no_wtg_models',
                'At least one WTG model is required',
                ''
            ))
            return

        for idx, model in enumerate(models):
            self._validate_wtg_model(model, idx)

    def _validate_wtg_model(self, model: Dict[str, Any], idx: int):
        """Validate individual WTG model."""
        path_prefix = f'wtg_models[{idx}]'

        required_fields = ['name', 'rotor_d_m', 'hub_height_default_m', 'v_in_mps', 'v_rated_mps', 'v_out_mps']
        for field in required_fields:
            if model.get(field) is None:
                self.gaps.append(Gap(
                    Gap.SEVERITY_RUN_BLOCKER,
                    f'{path_prefix}.{field}',
                    f'missing_{field}',
                    f'WTG model {model.get("name", f"#{idx}")} missing {field}',
                    ''
                ))

        # Validate speed class
        speed_class = model.get('default_speed_class')
        if speed_class:
            valid_classes = ['I', 'II', 'III', 'S']
            if speed_class not in valid_classes:
                self.gaps.append(Gap(
                    Gap.SEVERITY_INVALID,
                    f'{path_prefix}.default_speed_class',
                    'invalid_class',
                    f'Invalid speed class "{speed_class}", must be one of: {", ".join(valid_classes)}',
                    ''
                ))
        else:
            # Flag when defaulting speed class
            self.gaps.append(Gap(
                Gap.SEVERITY_FLAG,
                f'{path_prefix}.default_speed_class',
                'speed_class_defaulted',
                f'Speed class not specified for model {model.get("name")}, will use Django default (II)',
                ''
            ))

        # Validate TI category
        ti_category = model.get('default_ti_category')
        if ti_category:
            valid_categories = ['A+', 'A', 'B', 'C', 'S']
            if ti_category not in valid_categories:
                self.gaps.append(Gap(
                    Gap.SEVERITY_INVALID,
                    f'{path_prefix}.default_ti_category',
                    'invalid_class',
                    f'Invalid TI category "{ti_category}", must be one of: {", ".join(valid_categories)}',
                    ''
                ))
        else:
            # Flag when defaulting TI category
            self.gaps.append(Gap(
                Gap.SEVERITY_FLAG,
                f'{path_prefix}.default_ti_category',
                'ti_category_defaulted',
                f'TI category not specified for model {model.get("name")}, will use Django default (B)',
                ''
            ))

        # Check Ct curve
        ct_curve = model.get('ct_curve', [])
        if not ct_curve:
            self.gaps.append(Gap(
                Gap.SEVERITY_FLAG,
                f'{path_prefix}.ct_curve',
                'ct_missing',
                f'Ct curve is empty for model {model.get("name")}',
                ''
            ))

        # Validate power curve - missing is store_only not run_blocker
        power_curve = model.get('power_curve', [])
        if not power_curve:
            self.gaps.append(Gap(
                Gap.SEVERITY_STORE_ONLY_MISSING,
                f'{path_prefix}.power_curve',
                'missing_power_curve',
                f'Power curve missing for model {model.get("name")}',
                ''
            ))

    def _validate_hub_climates(self):
        """Validate hub climate data."""
        if 'hub_climates' not in self.data:
            self.gaps.append(Gap(
                Gap.SEVERITY_RUN_BLOCKER,
                'hub_climates',
                'missing_hub_climates',
                'Hub climate data is required',
                ''
            ))
            return

        climates = self.data['hub_climates']
        if not climates:
            self.gaps.append(Gap(
                Gap.SEVERITY_RUN_BLOCKER,
                'hub_climates',
                'no_hub_climates',
                'At least one hub climate is required',
                ''
            ))
            return

        for idx, climate in enumerate(climates):
            self._validate_hub_climate(climate, idx)

    def _validate_hub_climate(self, climate: Dict[str, Any], idx: int):
        """Validate individual hub climate."""
        path_prefix = f'hub_climates[{idx}]'

        required_fields = ['name', 'bin_width_mps', 'rho_kgm3', 'v50_mps']
        for field in required_fields:
            if climate.get(field) is None:
                self.gaps.append(Gap(
                    Gap.SEVERITY_RUN_BLOCKER,
                    f'{path_prefix}.{field}',
                    f'missing_{field}',
                    f'Hub climate {climate.get("name", f"#{idx}")} missing {field}',
                    ''
                ))

        # Validate TI bins
        ti_bins = climate.get('ti_bins', [])
        if not ti_bins:
            self.gaps.append(Gap(
                Gap.SEVERITY_RUN_BLOCKER,
                f'{path_prefix}.ti_bins',
                'no_ti_bins',
                f'Hub climate {climate.get("name")} has no TI bins',
                ''
            ))

    def get_gaps(self) -> List[Dict[str, str]]:
        """Return list of gaps as dictionaries."""
        return [g.to_dict() for g in self.gaps]

    def to_dict(self) -> Dict[str, Any]:
        """Return validated data with gaps."""
        return {
            'package': self.data,
            'gaps': self.get_gaps()
        }
