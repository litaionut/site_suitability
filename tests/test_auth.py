"""
Tests for authentication on mutating views.
"""
import io
from django.test import TestCase, Client
from django.contrib.auth.models import User
from django.urls import reverse
from projects.models import Project
from sites.models import Site
from turbines.models import Layout, Turbine, WtgModel
from climate.models import HubClimate, TiBin


class AuthenticationTests(TestCase):
    """Test that mutating views require authentication."""
    
    def setUp(self):
        self.client = Client()
        
        # Create a test user
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        
        # Create test data
        self.project = Project.objects.create(name="Test Project")
        self.site = Site.objects.create(
            project=self.project,
            name="Test Site",
            center_lon_deg=10.0,
            center_lat_deg=55.0
        )
        self.layout = Layout.objects.create(site=self.site, name="Test Layout")
        self.wtg_model = WtgModel.objects.create(
            name="TestTurbine",
            rotor_d_m=150.0,
            hub_height_default_m=120.0,
            v_in_mps=3.0,
            v_rated_mps=11.0,
            v_out_mps=25.0,
            ct_status=WtgModel.CT_STATUS_OK
        )
        self.turbine = Turbine.objects.create(
            layout=self.layout,
            local_id='T01',
            role='new_scored',
            x_m=1000.0,
            y_m=2000.0,
            z_base_m=50.0,
            hub_height_m=120.0,
            rotor_d_m=150.0,
            model=self.wtg_model
        )
        self.hub_climate = HubClimate.objects.create(
            site=self.site,
            name="Test Climate",
            period_hours=8760,
            bin_width_mps=1.0,
            rho_kgm3=1.225,
            v50_mps=50.0
        )
    
    def test_turbine_import_requires_auth(self):
        """Test that turbine CSV import requires authentication."""
        csv_content = """local_id,role,x_m,y_m,z_base_m,hub_height_m,rotor_d_m,model_name
T02,new_scored,1500.0,2000.0,55.0,120.0,150.0,TestTurbine"""
        
        csv_file = io.BytesIO(csv_content.encode('utf-8'))
        csv_file.name = 'turbines.csv'
        
        # Anonymous POST should redirect to login
        response = self.client.post(
            reverse('turbines:turbine_import', kwargs={'layout_pk': self.layout.pk}),
            {'csv_file': csv_file}
        )
        
        self.assertEqual(response.status_code, 302)
        self.assertIn('/accounts/login/', response.url)
        
        # No turbines should be created
        self.assertEqual(self.layout.turbines.count(), 1)  # Only the one from setUp
    
    def test_turbine_import_works_with_auth(self):
        """Test that turbine CSV import works when authenticated."""
        self.client.login(username='testuser', password='testpass123')
        
        csv_content = """local_id,role,x_m,y_m,z_base_m,hub_height_m,rotor_d_m,model_name
T02,new_scored,1500.0,2000.0,55.0,120.0,150.0,TestTurbine"""
        
        csv_file = io.BytesIO(csv_content.encode('utf-8'))
        csv_file.name = 'turbines.csv'
        
        response = self.client.post(
            reverse('turbines:turbine_import', kwargs={'layout_pk': self.layout.pk}),
            {'csv_file': csv_file}
        )
        
        self.assertEqual(response.status_code, 302)
        self.assertEqual(self.layout.turbines.count(), 2)
    
    def test_layout_create_requires_auth(self):
        """Test that layout creation requires authentication."""
        # Anonymous POST should redirect to login
        response = self.client.post(
            reverse('turbines:layout_create', kwargs={'site_pk': self.site.pk}),
            {'name': 'New Layout'}
        )
        
        self.assertEqual(response.status_code, 302)
        self.assertIn('/accounts/login/', response.url)
    
    def test_layout_create_works_with_auth(self):
        """Test that layout creation works when authenticated."""
        self.client.login(username='testuser', password='testpass123')
        
        response = self.client.post(
            reverse('turbines:layout_create', kwargs={'site_pk': self.site.pk}),
            {'name': 'New Layout'}
        )
        
        self.assertEqual(response.status_code, 302)
        self.assertEqual(Layout.objects.filter(site=self.site).count(), 2)
    
    def test_turbine_create_requires_auth(self):
        """Test that turbine creation requires authentication."""
        # Anonymous POST should redirect to login
        response = self.client.post(
            reverse('turbines:turbine_create', kwargs={'layout_pk': self.layout.pk}),
            {
                'local_id': 'T03',
                'role': 'new_scored',
                'x_m': 2000.0,
                'y_m': 3000.0,
                'z_base_m': 60.0,
                'hub_height_m': 120.0,
                'rotor_d_m': 150.0
            }
        )
        
        self.assertEqual(response.status_code, 302)
        self.assertIn('/accounts/login/', response.url)
    
    def test_turbine_edit_requires_auth(self):
        """Test that turbine edit requires authentication."""
        # Anonymous POST should redirect to login
        response = self.client.post(
            reverse('turbines:turbine_edit', kwargs={'pk': self.turbine.pk}),
            {
                'local_id': 'T01-EDITED',
                'role': 'new_scored',
                'x_m': 1000.0,
                'y_m': 2000.0,
                'z_base_m': 50.0,
                'hub_height_m': 120.0,
                'rotor_d_m': 150.0
            }
        )
        
        self.assertEqual(response.status_code, 302)
        self.assertIn('/accounts/login/', response.url)
    
    def test_turbine_delete_requires_auth(self):
        """Test that turbine deletion requires authentication."""
        turbine_pk = self.turbine.pk
        
        # Anonymous POST should redirect to login
        response = self.client.post(
            reverse('turbines:turbine_delete', kwargs={'pk': turbine_pk})
        )
        
        self.assertEqual(response.status_code, 302)
        self.assertIn('/accounts/login/', response.url)
        
        # Turbine should still exist
        self.assertTrue(Turbine.objects.filter(pk=turbine_pk).exists())
    
    def test_climate_import_requires_auth(self):
        """Test that climate CSV import requires authentication."""
        csv_content = """v_center_mps,hours,mean_sigma_mps,std_sigma_mps
5.0,100.0,0.5,0.15
6.0,150.0,0.6,0.18"""
        
        csv_file = io.BytesIO(csv_content.encode('utf-8'))
        csv_file.name = 'wind.csv'
        
        # Anonymous POST should redirect to login
        response = self.client.post(
            reverse('climate:ti_bin_import', kwargs={'hub_climate_pk': self.hub_climate.pk}),
            {'csv_file': csv_file, 'replace_existing': 'on'}
        )
        
        self.assertEqual(response.status_code, 302)
        self.assertIn('/accounts/login/', response.url)
        
        # No bins should be created
        self.assertEqual(self.hub_climate.ti_bins.count(), 0)
    
    def test_climate_import_works_with_auth(self):
        """Test that climate CSV import works when authenticated."""
        self.client.login(username='testuser', password='testpass123')
        
        csv_content = """v_center_mps,hours,mean_sigma_mps,std_sigma_mps
5.0,100.0,0.5,0.15
6.0,150.0,0.6,0.18"""
        
        csv_file = io.BytesIO(csv_content.encode('utf-8'))
        csv_file.name = 'wind.csv'
        
        response = self.client.post(
            reverse('climate:ti_bin_import', kwargs={'hub_climate_pk': self.hub_climate.pk}),
            {'csv_file': csv_file, 'replace_existing': 'on'}
        )
        
        self.assertEqual(response.status_code, 302)
        self.assertEqual(self.hub_climate.ti_bins.count(), 2)
    
    def test_hub_climate_create_requires_auth(self):
        """Test that hub climate creation requires authentication."""
        # Anonymous POST should redirect to login
        response = self.client.post(
            reverse('climate:create', kwargs={'site_pk': self.site.pk}),
            {
                'name': 'New Climate',
                'period_hours': 8760,
                'bin_width_mps': 1.0,
                'rho_kgm3': 1.225,
                'v50_mps': 50.0
            }
        )
        
        self.assertEqual(response.status_code, 302)
        self.assertIn('/accounts/login/', response.url)
    
    def test_hub_climate_edit_requires_auth(self):
        """Test that hub climate edit requires authentication."""
        # Anonymous POST should redirect to login
        response = self.client.post(
            reverse('climate:edit', kwargs={'pk': self.hub_climate.pk}),
            {
                'name': 'Edited Climate',
                'period_hours': 8760,
                'bin_width_mps': 1.0,
                'rho_kgm3': 1.225,
                'v50_mps': 50.0
            }
        )
        
        self.assertEqual(response.status_code, 302)
        self.assertIn('/accounts/login/', response.url)
    
    def test_assessment_setup_requires_auth(self):
        """Test that assessment setup requires authentication."""
        # Anonymous POST should redirect to login
        response = self.client.post(
            reverse('assessments:layout_setup', kwargs={'layout_pk': self.layout.pk}),
            {
                'hub_climate_id': self.hub_climate.pk,
                'edition': 'ed4'
            }
        )
        
        self.assertEqual(response.status_code, 302)
        self.assertIn('/accounts/login/', response.url)
    
    def test_ingest_upload_requires_auth(self):
        """Test that ingest upload requires authentication."""
        # Create a minimal JSON file
        json_content = b'{"site": {"name": "Test"}}'
        json_file = io.BytesIO(json_content)
        json_file.name = 'test.json'
        
        # Anonymous POST should return 403 or redirect
        response = self.client.post(
            reverse('ingest:upload'),
            {'file': json_file}
        )
        
        # For JSON endpoints, it might return 403 instead of redirect
        self.assertIn(response.status_code, [302, 403])
    
    def test_read_only_views_remain_accessible(self):
        """Test that read-only views remain accessible without auth."""
        # Layout detail (GET) should be accessible
        response = self.client.get(
            reverse('turbines:layout_detail', kwargs={'pk': self.layout.pk})
        )
        
        self.assertEqual(response.status_code, 200)
        
        # Hub climate detail (GET) should be accessible
        response = self.client.get(
            reverse('climate:detail', kwargs={'pk': self.hub_climate.pk})
        )
        
        self.assertEqual(response.status_code, 200)
