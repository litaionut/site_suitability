"""
Tests for stub WTG model transaction rollback.
"""
import io
from django.test import TestCase, Client
from django.contrib.auth.models import User
from django.urls import reverse
from projects.models import Project
from sites.models import Site
from turbines.models import Layout, Turbine, WtgModel
from unittest.mock import patch


class StubWtgTransactionTests(TestCase):
    """Test that stub WTG creation is in the same transaction as turbine import."""
    
    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(
            username='testuser',
            password='testpass123'
        )
        self.client.login(username='testuser', password='testpass123')
        
        self.project = Project.objects.create(name="Test Project")
        self.site = Site.objects.create(
            project=self.project,
            name="Test Site",
            center_lon_deg=10.0,
            center_lat_deg=55.0
        )
        self.layout = Layout.objects.create(site=self.site, name="Test Layout")
    
    def test_stub_wtg_rolled_back_on_turbine_save_failure(self):
        """Test that stub WTG model is rolled back if turbine save fails."""
        initial_model_count = WtgModel.objects.count()
        
        csv_content = """local_id,role,x_m,y_m,z_base_m,hub_height_m,rotor_d_m,model_name
T01,new_scored,1000.0,2000.0,50.0,120.0,150.0,NewStubModel999"""
        
        csv_file = io.BytesIO(csv_content.encode('utf-8'))
        csv_file.name = 'turbines.csv'
        
        # Mock Turbine.save() to raise an exception after stub creation
        with patch.object(Turbine, 'save', side_effect=Exception('Simulated save failure')):
            response = self.client.post(
                reverse('turbines:turbine_import', kwargs={'layout_pk': self.layout.pk}),
                {'csv_file': csv_file}
            )
        
        # Check that no stub WTG model was created (rolled back)
        self.assertEqual(WtgModel.objects.count(), initial_model_count)
        self.assertFalse(WtgModel.objects.filter(name='NewStubModel999').exists())
        
        # Check that no turbine was created
        self.assertEqual(self.layout.turbines.count(), 0)
    
    def test_stub_wtg_created_successfully_with_turbine(self):
        """Test that stub WTG model is created in the same transaction as turbine."""
        initial_model_count = WtgModel.objects.count()
        
        csv_content = """local_id,role,x_m,y_m,z_base_m,hub_height_m,rotor_d_m,model_name
T01,new_scored,1000.0,2000.0,50.0,120.0,150.0,NewStubModel999"""
        
        csv_file = io.BytesIO(csv_content.encode('utf-8'))
        csv_file.name = 'turbines.csv'
        
        response = self.client.post(
            reverse('turbines:turbine_import', kwargs={'layout_pk': self.layout.pk}),
            {'csv_file': csv_file}
        )
        
        # Check that stub WTG model was created
        self.assertEqual(WtgModel.objects.count(), initial_model_count + 1)
        self.assertTrue(WtgModel.objects.filter(name='NewStubModel999').exists())
        
        # Check that turbine was created with the stub model
        self.assertEqual(self.layout.turbines.count(), 1)
        turbine = self.layout.turbines.first()
        self.assertEqual(turbine.model.name, 'NewStubModel999')
        self.assertEqual(turbine.model.ct_status, WtgModel.CT_STATUS_MISSING)
    
    def test_multiple_turbines_same_stub_model(self):
        """Test that multiple turbines can reference the same stub model."""
        initial_model_count = WtgModel.objects.count()
        
        csv_content = """local_id,role,x_m,y_m,z_base_m,hub_height_m,rotor_d_m,model_name
T01,new_scored,1000.0,2000.0,50.0,120.0,150.0,StubModel123
T02,new_scored,1500.0,2000.0,55.0,120.0,150.0,StubModel123"""
        
        csv_file = io.BytesIO(csv_content.encode('utf-8'))
        csv_file.name = 'turbines.csv'
        
        response = self.client.post(
            reverse('turbines:turbine_import', kwargs={'layout_pk': self.layout.pk}),
            {'csv_file': csv_file}
        )
        
        # Check that only ONE stub WTG model was created
        self.assertEqual(WtgModel.objects.count(), initial_model_count + 1)
        
        # Check that both turbines reference the same model
        self.assertEqual(self.layout.turbines.count(), 2)
        t01 = self.layout.turbines.get(local_id='T01')
        t02 = self.layout.turbines.get(local_id='T02')
        self.assertEqual(t01.model, t02.model)
        self.assertEqual(t01.model.name, 'StubModel123')
