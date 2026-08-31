"""
Tests for turbine CSV import and layout functionality.
"""
import io
from django.test import TestCase, Client
from django.urls import reverse
from projects.models import Project
from sites.models import Site
from turbines.models import Layout, Turbine, WtgModel
from climate.models import HubClimate, TiBin


class TurbineCSVImportTests(TestCase):
    """Test CSV import functionality for turbines."""
    
    def setUp(self):
        self.client = Client()
        
        # Create and login a test user
        from django.contrib.auth.models import User
        self.user = User.objects.create_user(username='testuser', password='testpass')
        self.client.login(username='testuser', password='testpass')
        
        self.project = Project.objects.create(name="Test Project")
        self.site = Site.objects.create(
            project=self.project,
            name="Test Site",
            center_lon_deg=10.0,
            center_lat_deg=55.0
        )
        self.layout_a = Layout.objects.create(site=self.site, name="Layout A")
        self.layout_b = Layout.objects.create(site=self.site, name="Layout B")
        
        # Create a WTG model
        self.wtg_model = WtgModel.objects.create(
            name="TestTurbine3000",
            rotor_d_m=150.0,
            hub_height_default_m=120.0,
            v_in_mps=3.0,
            v_rated_mps=11.0,
            v_out_mps=25.0,
            ct_status=WtgModel.CT_STATUS_OK
        )
    
    def test_import_turbines_csv_two_turbines(self):
        """Test importing 2 turbines via CSV."""
        csv_content = """local_id,role,x_m,y_m,z_base_m,hub_height_m,rotor_d_m,model_name
T01,new_scored,1000.0,2000.0,50.0,120.0,150.0,TestTurbine3000
T02,new_scored,1500.0,2000.0,55.0,120.0,150.0,TestTurbine3000"""
        
        csv_file = io.BytesIO(csv_content.encode('utf-8'))
        csv_file.name = 'turbines.csv'
        
        response = self.client.post(
            reverse('turbines:turbine_import', kwargs={'layout_pk': self.layout_a.pk}),
            {'csv_file': csv_file}
        )
        
        self.assertEqual(response.status_code, 302)  # Redirect after success
        self.assertEqual(self.layout_a.turbines.count(), 2)
        
        t01 = self.layout_a.turbines.get(local_id='T01')
        self.assertEqual(t01.x_m, 1000.0)
        self.assertEqual(t01.role, 'new_scored')
        self.assertEqual(t01.model, self.wtg_model)
    
    def test_import_turbines_different_layouts(self):
        """Test importing turbines to two different layouts on same site."""
        # Layout A
        csv_a = """local_id,role,x_m,y_m,z_base_m,hub_height_m,rotor_d_m,model_name
TA1,new_scored,1000.0,2000.0,50.0,120.0,150.0,TestTurbine3000
TA2,new_scored,1500.0,2000.0,55.0,120.0,150.0,TestTurbine3000"""
        
        csv_file_a = io.BytesIO(csv_a.encode('utf-8'))
        csv_file_a.name = 'turbines_a.csv'
        
        self.client.post(
            reverse('turbines:turbine_import', kwargs={'layout_pk': self.layout_a.pk}),
            {'csv_file': csv_file_a}
        )
        
        # Layout B with different positions
        csv_b = """local_id,role,x_m,y_m,z_base_m,hub_height_m,rotor_d_m,model_name
TB1,new_scored,2000.0,3000.0,60.0,120.0,150.0,TestTurbine3000
TB2,new_scored,2500.0,3000.0,65.0,120.0,150.0,TestTurbine3000"""
        
        csv_file_b = io.BytesIO(csv_b.encode('utf-8'))
        csv_file_b.name = 'turbines_b.csv'
        
        self.client.post(
            reverse('turbines:turbine_import', kwargs={'layout_pk': self.layout_b.pk}),
            {'csv_file': csv_file_b}
        )
        
        self.assertEqual(self.layout_a.turbines.count(), 2)
        self.assertEqual(self.layout_b.turbines.count(), 2)
        
        # Check positions are different
        ta1 = self.layout_a.turbines.get(local_id='TA1')
        tb1 = self.layout_b.turbines.get(local_id='TB1')
        self.assertNotEqual(ta1.x_m, tb1.x_m)
        self.assertNotEqual(ta1.y_m, tb1.y_m)
    
    def test_duplicate_local_id_rejected(self):
        """Test that duplicate local_id in same layout is rejected."""
        # First import
        csv1 = """local_id,role,x_m,y_m,z_base_m,hub_height_m,rotor_d_m,model_name
T01,new_scored,1000.0,2000.0,50.0,120.0,150.0,TestTurbine3000"""
        
        csv_file1 = io.BytesIO(csv1.encode('utf-8'))
        csv_file1.name = 'turbines1.csv'
        
        self.client.post(
            reverse('turbines:turbine_import', kwargs={'layout_pk': self.layout_a.pk}),
            {'csv_file': csv_file1}
        )
        
        self.assertEqual(self.layout_a.turbines.count(), 1)
        
        # Try to import duplicate local_id
        csv2 = """local_id,role,x_m,y_m,z_base_m,hub_height_m,rotor_d_m,model_name
T01,new_scored,1500.0,2500.0,55.0,120.0,150.0,TestTurbine3000"""
        
        csv_file2 = io.BytesIO(csv2.encode('utf-8'))
        csv_file2.name = 'turbines2.csv'
        
        response = self.client.post(
            reverse('turbines:turbine_import', kwargs={'layout_pk': self.layout_a.pk}),
            {'csv_file': csv_file2}
        )
        
        # Should still have only 1 turbine (all-or-nothing)
        self.assertEqual(self.layout_a.turbines.count(), 1)
    
    def test_stub_model_creation(self):
        """Test that stub WTG model is created when model_name is unknown."""
        csv_content = """local_id,role,x_m,y_m,z_base_m,hub_height_m,rotor_d_m,model_name
T01,new_scored,1000.0,2000.0,50.0,120.0,150.0,UnknownModel999"""
        
        csv_file = io.BytesIO(csv_content.encode('utf-8'))
        csv_file.name = 'turbines.csv'
        
        initial_model_count = WtgModel.objects.count()
        
        response = self.client.post(
            reverse('turbines:turbine_import', kwargs={'layout_pk': self.layout_a.pk}),
            {'csv_file': csv_file}
        )
        
        self.assertEqual(WtgModel.objects.count(), initial_model_count + 1)
        
        new_model = WtgModel.objects.get(name='UnknownModel999')
        self.assertEqual(new_model.ct_status, WtgModel.CT_STATUS_MISSING)
        self.assertEqual(new_model.rotor_d_m, 150.0)
        self.assertEqual(new_model.hub_height_default_m, 120.0)


class WindCSVImportTests(TestCase):
    """Test CSV import functionality for wind data."""
    
    def setUp(self):
        self.client = Client()
        
        # Create and login a test user
        from django.contrib.auth.models import User
        self.user = User.objects.create_user(username='testuser', password='testpass')
        self.client.login(username='testuser', password='testpass')
        
        self.project = Project.objects.create(name="Test Project")
        self.site = Site.objects.create(
            project=self.project,
            name="Test Site",
            center_lon_deg=10.0,
            center_lat_deg=55.0
        )
        self.hub_climate = HubClimate.objects.create(
            site=self.site,
            name="Test Climate",
            period_hours=8760,
            bin_width_mps=1.0,
            rho_kgm3=1.225,
            v50_mps=50.0
        )
    
    def test_import_wind_csv_creates_tibins(self):
        """Test that wind CSV import creates TI bins."""
        csv_content = """v_center_mps,hours,mean_sigma_mps,std_sigma_mps
5.0,100.0,0.5,0.15
6.0,150.0,0.6,0.18
7.0,200.0,0.7,0.20"""
        
        csv_file = io.BytesIO(csv_content.encode('utf-8'))
        csv_file.name = 'wind.csv'
        
        response = self.client.post(
            reverse('climate:ti_bin_import', kwargs={'hub_climate_pk': self.hub_climate.pk}),
            {'csv_file': csv_file, 'replace_existing': 'on'}
        )
        
        self.assertEqual(response.status_code, 302)
        self.assertEqual(self.hub_climate.ti_bins.count(), 3)
        
        bin_5 = self.hub_climate.ti_bins.get(v_center_mps=5.0)
        self.assertEqual(bin_5.hours, 100.0)
        self.assertEqual(bin_5.mean_sigma_mps, 0.5)
        self.assertEqual(bin_5.std_sigma_mps, 0.15)
    
    def test_import_wind_csv_empty_std_sigma(self):
        """Test that empty std_sigma_mps is allowed."""
        csv_content = """v_center_mps,hours,mean_sigma_mps,std_sigma_mps
5.0,100.0,0.5,
6.0,150.0,0.6,0.18"""
        
        csv_file = io.BytesIO(csv_content.encode('utf-8'))
        csv_file.name = 'wind.csv'
        
        response = self.client.post(
            reverse('climate:ti_bin_import', kwargs={'hub_climate_pk': self.hub_climate.pk}),
            {'csv_file': csv_file, 'replace_existing': 'on'}
        )
        
        self.assertEqual(self.hub_climate.ti_bins.count(), 2)
        
        bin_5 = self.hub_climate.ti_bins.get(v_center_mps=5.0)
        self.assertIsNone(bin_5.std_sigma_mps)


class LayoutAssessmentTests(TestCase):
    """Test running assessments on layouts."""
    
    def setUp(self):
        self.client = Client()
        self.project = Project.objects.create(name="Test Project")
        
        # Create class envelope
        from projects.models import ClassEnvelope
        ClassEnvelope.objects.create(project=self.project)
        
        self.site = Site.objects.create(
            project=self.project,
            name="Test Site",
            center_lon_deg=10.0,
            center_lat_deg=55.0,
            default_complexity='simple'
        )
        
        self.layout_a = Layout.objects.create(site=self.site, name="Layout A")
        self.layout_b = Layout.objects.create(site=self.site, name="Layout B")
        
        self.wtg_model = WtgModel.objects.create(
            name="TestTurbine3000",
            rotor_d_m=150.0,
            hub_height_default_m=120.0,
            v_in_mps=3.0,
            v_rated_mps=11.0,
            v_out_mps=25.0,
            default_speed_class='II',
            default_ti_category='B',
            ct_status=WtgModel.CT_STATUS_OK
        )
        
        # Add turbines to layout A
        Turbine.objects.create(
            layout=self.layout_a,
            local_id='TA1',
            role='new_scored',
            x_m=1000.0,
            y_m=2000.0,
            z_base_m=50.0,
            hub_height_m=120.0,
            rotor_d_m=150.0,
            model=self.wtg_model
        )
        
        # Add turbines to layout B
        Turbine.objects.create(
            layout=self.layout_b,
            local_id='TB1',
            role='new_scored',
            x_m=2000.0,
            y_m=3000.0,
            z_base_m=60.0,
            hub_height_m=120.0,
            rotor_d_m=150.0,
            model=self.wtg_model
        )
        
        # Create hub climate
        self.hub_climate = HubClimate.objects.create(
            site=self.site,
            name="Test Climate",
            period_hours=8760,
            bin_width_mps=1.0,
            rho_kgm3=1.225,
            v50_mps=42.0,
            shear_alpha=0.15,
            inflow_angle_deg=0.0
        )
        
        # Add TI bins
        for v in range(4, 26):
            TiBin.objects.create(
                hub_climate=self.hub_climate,
                v_center_mps=float(v),
                hours=100.0,
                mean_sigma_mps=0.5,
                std_sigma_mps=0.15
            )
    
    def test_run_assessment_layout_a_only(self):
        """Test running assessment on layout A does not affect layout B."""
        from assessments.models import Assessment, AssessmentTurbine
        
        # Create assessment for layout A
        assessment = Assessment.objects.create(
            project=self.project,
            site=self.site,
            name="Assessment A",
            edition='ed4',
            class_envelope_snapshot={
                'vref_ii': 42.5,
                'iref_b': 0.14,
                'vave_over_vref': 0.2
            }
        )
        
        turbine_a = self.layout_a.turbines.first()
        at_a = AssessmentTurbine.objects.create(
            assessment=assessment,
            turbine=turbine_a,
            hub_climate=self.hub_climate,
            resolved_vref_mps=42.5,
            resolved_iref=0.14,
            resolved_vave_mps=8.5,
            cct=1.0,
            apply_density_to_v50=False,
            wohler_exponents=[4, 10]
        )
        
        # Run assessment
        from assessments.services import run_assessment_for_turbine
        run_assessment_for_turbine(at_a)
        
        # Check that layout B turbines have no assessments
        turbine_b = self.layout_b.turbines.first()
        self.assertEqual(turbine_b.assessmentturbine_set.count(), 0)


class CompareLayoutsTests(TestCase):
    """Test layout comparison view."""
    
    def setUp(self):
        self.client = Client()
        self.project = Project.objects.create(name="Test Project")
        self.site = Site.objects.create(
            project=self.project,
            name="Test Site",
            center_lon_deg=10.0,
            center_lat_deg=55.0
        )
        self.layout_a = Layout.objects.create(site=self.site, name="Layout A")
        self.layout_b = Layout.objects.create(site=self.site, name="Layout B")
    
    def test_compare_view_shows_two_layouts(self):
        """Test that compare view shows both layouts."""
        response = self.client.get(
            reverse('sites:compare', kwargs={'pk': self.site.pk})
        )
        
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Layout A")
        self.assertContains(response, "Layout B")
