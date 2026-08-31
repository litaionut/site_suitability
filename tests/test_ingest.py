"""
Tests for site package ingest functionality.
"""
import json
import pytest
from django.test import TestCase, Client
from django.core.cache import cache
from io import BytesIO

from projects.models import Project, ClassEnvelope
from sites.models import Site
from turbines.models import Layout, Turbine, WtgModel, PowerCurvePoint, CtCurvePoint
from climate.models import HubClimate, TiBin, SectorWeibull
from assessments.services import run_assessment
from ingest.parsers import parse_file, ParseError
from ingest.serializers import SitePackageSerializer


@pytest.mark.django_db
class TestIngestRoundTrip(TestCase):
    """Test round-trip of example site package."""

    def setUp(self):
        self.client = Client()
        cache.clear()

    def test_example_site_package_round_trip(self):
        """
        Test 1: Round-trip example_site_package.json
        Synthetic Ridge: 9E 45N, T01 at 0,0 new_scored, E01 at 0,960 existing_wake_source,
        N123-120 with golden Ct, HubClimate GOLDEN_PASS_T1 climate V50=40, rho=1.225, alpha=0.2, inflow=3.
        After commit, objects exist and Slice 0+1 assessment can run.
        """
        # Load example package
        with open('docs/ingest/example_site_package.json', 'r') as f:
            package_data = json.load(f)

        # Validate
        serializer = SitePackageSerializer(package_data)
        is_valid = serializer.validate()
        self.assertTrue(is_valid, f"Validation failed with gaps: {serializer.get_gaps()}")

        # Simulate file upload and commit
        with open('docs/ingest/example_site_package.json', 'rb') as f:
            parsed_package = parse_file(f, 'example_site_package.json')

        # Commit via API simulation
        from ingest.views import commit_package
        from django.http import HttpRequest
        from unittest.mock import Mock

        # Store in cache
        session_id = 'test-session-123'
        cache_key = f'ingest_package_{session_id}'
        cache.set(cache_key, parsed_package, timeout=3600)

        # Create mock request
        request = Mock(spec=HttpRequest)
        request.method = 'POST'

        # Commit
        response = commit_package(request, session_id)
        response_data = json.loads(response.content)

        self.assertEqual(response_data['status'], 'success')
        self.assertEqual(response_data['turbine_count'], 2)

        # Verify objects exist
        project = Project.objects.get(name='Synthetic Ridge Wind Farm')
        self.assertIsNotNone(project)

        class_envelope = ClassEnvelope.objects.get(project=project)
        self.assertEqual(class_envelope.vref_ii, 42.5)
        self.assertEqual(class_envelope.iref_b, 0.14)

        site = Site.objects.get(project=project)
        self.assertEqual(site.center_lon_deg, 45.0)
        self.assertEqual(site.center_lat_deg, 9.0)
        self.assertEqual(site.default_complexity, 'simple')

        layout = Layout.objects.get(site=site)
        self.assertEqual(layout.turbines.count(), 2)

        # Verify T01 turbine
        t01 = Turbine.objects.get(layout=layout, local_id='T01')
        self.assertEqual(t01.role, 'new_scored')
        self.assertEqual(t01.x_m, 0.0)
        self.assertEqual(t01.y_m, 0.0)
        self.assertEqual(t01.hub_height_m, 120.0)
        self.assertEqual(t01.rotor_d_m, 120.0)

        # Verify E01 turbine (existing wake source at 0, 960)
        e01 = Turbine.objects.get(layout=layout, local_id='E01')
        self.assertEqual(e01.role, 'existing_wake_source')
        self.assertEqual(e01.x_m, 0.0)
        self.assertEqual(e01.y_m, 960.0)  # 8D spacing (960m / 120m = 8D)

        # Verify WtgModel N123-120 with Ct curve
        wtg_model = WtgModel.objects.get(name='N123-120')
        self.assertEqual(wtg_model.rotor_d_m, 120.0)
        self.assertEqual(wtg_model.v_in_mps, 3.0)
        self.assertEqual(wtg_model.v_rated_mps, 12.0)
        self.assertEqual(wtg_model.v_out_mps, 25.0)
        self.assertEqual(wtg_model.default_speed_class, 'II')
        self.assertEqual(wtg_model.default_ti_category, 'B')

        # Verify Ct curve exists
        ct_points = CtCurvePoint.objects.filter(wtg_model=wtg_model).order_by('v_mps')
        self.assertGreater(ct_points.count(), 0)
        self.assertIn(wtg_model.ct_status, ['ok', 'suspect'])  # Should not be 'missing'

        # Verify power curve
        power_points = PowerCurvePoint.objects.filter(wtg_model=wtg_model)
        self.assertGreater(power_points.count(), 0)

        # Verify HubClimate GOLDEN_PASS_T1
        hub_climate = HubClimate.objects.get(site=site, name='GOLDEN_PASS_T1')
        self.assertEqual(hub_climate.v50_mps, 40.0)
        self.assertEqual(hub_climate.rho_kgm3, 1.225)
        self.assertEqual(hub_climate.shear_alpha, 0.2)
        self.assertEqual(hub_climate.inflow_angle_deg, 3.0)

        # Verify TI bins
        ti_bins = TiBin.objects.filter(hub_climate=hub_climate)
        self.assertEqual(ti_bins.count(), 25)  # 25 bins from 1-25 m/s

        # Run Slice 0+1 assessment
        try:
            result = run_assessment(
                project=project,
                site=site,
                layout=layout,
                hub_climate=hub_climate,
                complexity=site.default_complexity
            )
            self.assertIsNotNone(result)
            self.assertIn('overall', result)
            # Assessment should complete without errors
        except Exception as e:
            self.fail(f"Assessment failed: {e}")


@pytest.mark.django_db
class TestMissingCtHandling(TestCase):
    """Test missing Ct curve handling."""

    def setUp(self):
        cache.clear()

    def test_missing_ct_stays_empty(self):
        """
        Test 2: Missing Ct stays empty
        - Upload site package with WtgModel having empty ct_curve
        - Verify gap added: severity=flag, code=ct_missing
        - Commit package
        - Verify ct_status = "missing" on WtgModel
        - Verify NO 7/V rows in CtCurvePoint table for that model
        """
        package_data = {
            'package_version': 'site-package-v1',
            'project': {'name': 'Missing Ct Test'},
            'site': {
                'name': 'Test Site',
                'center_lon_deg': 10.0,
                'center_lat_deg': 50.0,
                'default_complexity': 'simple'
            },
            'class_envelope': {},
            'layout': {
                'name': 'Test Layout',
                'turbines': [{
                    'local_id': 'T01',
                    'role': 'new_scored',
                    'x_m': 0.0,
                    'y_m': 0.0,
                    'z_base_m': 100.0,
                    'hub_height_m': 120.0,
                    'rotor_d_m': 120.0,
                    'model_name': 'TestModel-Missing-Ct'
                }]
            },
            'wtg_models': [{
                'name': 'TestModel-Missing-Ct',
                'rotor_d_m': 120.0,
                'hub_height_default_m': 120.0,
                'v_in_mps': 3.0,
                'v_rated_mps': 12.0,
                'v_out_mps': 25.0,
                'default_speed_class': 'II',
                'default_ti_category': 'B',
                'power_curve': [
                    {'v_mps': 3.0, 'p_kw': 0.0},
                    {'v_mps': 12.0, 'p_kw': 3000.0},
                    {'v_mps': 25.0, 'p_kw': 3000.0}
                ],
                'ct_curve': []  # Empty Ct curve
            }],
            'hub_climates': [{
                'name': 'Test Climate',
                'turbine_local_id': None,
                'period_hours': 8760.0,
                'bin_width_mps': 1.0,
                'rho_kgm3': 1.225,
                'v50_mps': 40.0,
                'ti_bins': [
                    {'v_center_mps': 10.0, 'hours': 1000.0, 'mean_sigma_mps': 1.0, 'std_sigma_mps': 0.2}
                ],
                'sector_weibull': []
            }],
            'gaps': []
        }

        # Validate
        serializer = SitePackageSerializer(package_data)
        is_valid = serializer.validate()
        gaps = serializer.get_gaps()

        # Check for ct_missing gap
        ct_gaps = [g for g in gaps if g['code'] == 'ct_missing']
        self.assertEqual(len(ct_gaps), 1)
        self.assertEqual(ct_gaps[0]['severity'], 'flag')

        # Commit is still allowed (flag, not run_blocker)
        self.assertTrue(is_valid)

        # Commit to database
        session_id = 'test-missing-ct'
        cache_key = f'ingest_package_{session_id}'
        cache.set(cache_key, package_data, timeout=3600)

        from ingest.views import commit_package
        from unittest.mock import Mock
        from django.http import HttpRequest

        request = Mock(spec=HttpRequest)
        request.method = 'POST'

        response = commit_package(request, session_id)
        response_data = json.loads(response.content)

        self.assertEqual(response_data['status'], 'success')

        # Verify model has ct_status = 'missing'
        wtg_model = WtgModel.objects.get(name='TestModel-Missing-Ct')
        self.assertEqual(wtg_model.ct_status, 'missing')

        # Verify NO Ct curve points exist
        ct_points = CtCurvePoint.objects.filter(wtg_model=wtg_model)
        self.assertEqual(ct_points.count(), 0)

        # Verify no 7/V fallback points were created
        # (Slice 1 calc handles fallback internally, not in DB)


@pytest.mark.django_db
class TestDuplicateLocalId(TestCase):
    """Test duplicate local_id rejection."""

    def setUp(self):
        cache.clear()

    def test_duplicate_local_id_rejected(self):
        """
        Test 3: Duplicate local_id rejected on commit
        - Create site package with duplicate local_id in layout
        - Attempt commit
        - Verify gap added: severity=run_blocker, code=duplicate_local_id
        - Verify commit fails
        - Verify NO objects persisted (rollback)
        """
        package_data = {
            'package_version': 'site-package-v1',
            'project': {'name': 'Duplicate ID Test'},
            'site': {
                'name': 'Test Site',
                'center_lon_deg': 10.0,
                'center_lat_deg': 50.0,
                'default_complexity': 'simple'
            },
            'class_envelope': {},
            'layout': {
                'name': 'Test Layout',
                'turbines': [
                    {
                        'local_id': 'T01',
                        'role': 'new_scored',
                        'x_m': 0.0,
                        'y_m': 0.0,
                        'z_base_m': 100.0,
                        'hub_height_m': 120.0,
                        'rotor_d_m': 120.0,
                        'model_name': 'TestModel'
                    },
                    {
                        'local_id': 'T01',  # DUPLICATE
                        'role': 'new_scored',
                        'x_m': 100.0,
                        'y_m': 100.0,
                        'z_base_m': 100.0,
                        'hub_height_m': 120.0,
                        'rotor_d_m': 120.0,
                        'model_name': 'TestModel'
                    }
                ]
            },
            'wtg_models': [{
                'name': 'TestModel',
                'rotor_d_m': 120.0,
                'hub_height_default_m': 120.0,
                'v_in_mps': 3.0,
                'v_rated_mps': 12.0,
                'v_out_mps': 25.0,
                'power_curve': [
                    {'v_mps': 3.0, 'p_kw': 0.0},
                    {'v_mps': 12.0, 'p_kw': 3000.0}
                ],
                'ct_curve': []
            }],
            'hub_climates': [{
                'name': 'Test Climate',
                'turbine_local_id': None,
                'period_hours': 8760.0,
                'bin_width_mps': 1.0,
                'rho_kgm3': 1.225,
                'v50_mps': 40.0,
                'ti_bins': [
                    {'v_center_mps': 10.0, 'hours': 1000.0, 'mean_sigma_mps': 1.0, 'std_sigma_mps': 0.2}
                ],
                'sector_weibull': []
            }],
            'gaps': []
        }

        # Validate
        serializer = SitePackageSerializer(package_data)
        is_valid = serializer.validate()
        gaps = serializer.get_gaps()

        # Check for duplicate_local_id gap
        dup_gaps = [g for g in gaps if g['code'] == 'duplicate_local_id']
        self.assertEqual(len(dup_gaps), 1)
        self.assertEqual(dup_gaps[0]['severity'], 'run_blocker')
        self.assertFalse(is_valid)

        # Attempt commit (should fail)
        session_id = 'test-duplicate-id'
        cache_key = f'ingest_package_{session_id}'
        cache.set(cache_key, package_data, timeout=3600)

        from ingest.views import commit_package
        from unittest.mock import Mock
        from django.http import HttpRequest

        request = Mock(spec=HttpRequest)
        request.method = 'POST'

        response = commit_package(request, session_id)
        response_data = json.loads(response.content)

        self.assertEqual(response_data['status'], 'error')
        self.assertIn('run_blocker', response_data['message'])

        # Verify NO objects were persisted
        self.assertEqual(Project.objects.filter(name='Duplicate ID Test').count(), 0)
        self.assertEqual(Turbine.objects.filter(local_id='T01').count(), 0)


@pytest.mark.django_db
class TestExistingGoldens(TestCase):
    """Verify existing Slice 0 and Slice 1 golden tests remain valid."""

    def test_existing_goldens_unchanged(self):
        """
        Test 4: Existing Slice 0 and Slice 1 goldens stay green
        Ensure no regressions from ingest changes.
        This test imports and runs existing golden tests to verify they still pass.
        """
        # Import existing golden tests
        from tests.test_engine import TestAssessmentEngine
        from tests.test_slice1_ieff import TestSlice1IeffCalculation

        # Run Slice 0 golden tests
        slice0_test = TestAssessmentEngine()
        slice0_test.setUp()

        try:
            slice0_test.test_golden_pass_t1()
            slice0_test.test_golden_fail_t1()
        except Exception as e:
            self.fail(f"Slice 0 golden tests failed: {e}")

        # Run Slice 1 golden tests
        slice1_test = TestSlice1IeffCalculation()
        slice1_test.setUp()

        try:
            slice1_test.test_golden_ieff_pass()
            slice1_test.test_golden_ieff_fail()
        except Exception as e:
            self.fail(f"Slice 1 golden tests failed: {e}")


@pytest.mark.django_db
class TestParserRejection(TestCase):
    """Test rejected file formats."""

    def test_rejected_formats(self):
        """Test that rejected formats are properly rejected."""
        rejected_files = [
            'test.map',
            'test.lib',
            'test.shp',
            'test.tif',
            'wasp_file.txt',
            'flowres_data.csv',
            'load_response.xlsx'
        ]

        for filename in rejected_files:
            with self.subTest(filename=filename):
                fake_file = BytesIO(b'fake content')
                with self.assertRaises(ParseError):
                    parse_file(fake_file, filename)
