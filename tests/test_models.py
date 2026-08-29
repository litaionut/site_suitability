"""
Tests for Django models.
"""
import pytest
from django.test import TestCase
from projects.models import Project, ClassEnvelope
from sites.models import Site
from turbines.models import WtgModel, CtCurvePoint, Layout, Turbine
from climate.models import HubClimate, TiBin


@pytest.mark.django_db
class TestProject(TestCase):
    """Test Project model."""
    
    def test_create_project(self):
        """Test creating a project."""
        project = Project.objects.create(
            name="Test Wind Farm",
            notes="Test project notes"
        )
        assert project.uuid is not None
        assert project.name == "Test Wind Farm"
        assert str(project) == "Test Wind Farm"


@pytest.mark.django_db
class TestClassEnvelope(TestCase):
    """Test ClassEnvelope model."""
    
    def test_class_envelope_defaults(self):
        """Test ClassEnvelope has correct defaults."""
        project = Project.objects.create(name="Test Project")
        envelope = ClassEnvelope.objects.create(project=project)
        
        assert envelope.vref_i == 50.0
        assert envelope.vref_ii == 42.5
        assert envelope.vref_iii == 37.5
        assert envelope.iref_a_plus == 0.18
        assert envelope.iref_a == 0.16
        assert envelope.iref_b == 0.14
        assert envelope.iref_c == 0.12
        assert envelope.vave_over_vref == 0.2
    
    def test_get_vref(self):
        """Test get_vref method."""
        project = Project.objects.create(name="Test Project")
        envelope = ClassEnvelope.objects.create(project=project)
        
        assert envelope.get_vref('I') == 50.0
        assert envelope.get_vref('II') == 42.5
        assert envelope.get_vref('III') == 37.5
        assert envelope.get_vref('S') is None
    
    def test_get_iref(self):
        """Test get_iref method."""
        project = Project.objects.create(name="Test Project")
        envelope = ClassEnvelope.objects.create(project=project)
        
        assert envelope.get_iref('A+') == 0.18
        assert envelope.get_iref('A') == 0.16
        assert envelope.get_iref('B') == 0.14
        assert envelope.get_iref('C') == 0.12
        assert envelope.get_iref('S') is None


@pytest.mark.django_db
class TestSite(TestCase):
    """Test Site model."""
    
    def test_crs_calculation_northern_hemisphere(self):
        """Test CRS calculation for northern hemisphere site."""
        project = Project.objects.create(name="Test Project")
        site = Site.objects.create(
            project=project,
            name="Northern Site",
            center_lon_deg=-95.0,
            center_lat_deg=45.0
        )
        
        # Zone = floor((-95 + 180) / 6) + 1 = floor(85/6) + 1 = 14 + 1 = 15
        assert site.utm_zone == 15
        assert site.utm_north is True
        # EPSG = 32600 + 15 = 32615
        assert site.crs_epsg == 32615
    
    def test_crs_calculation_southern_hemisphere(self):
        """Test CRS calculation for southern hemisphere site."""
        project = Project.objects.create(name="Test Project")
        site = Site.objects.create(
            project=project,
            name="Southern Site",
            center_lon_deg=25.0,
            center_lat_deg=-30.0
        )
        
        # Zone = floor((25 + 180) / 6) + 1 = floor(205/6) + 1 = 34 + 1 = 35
        assert site.utm_zone == 35
        assert site.utm_north is False
        # EPSG = 32700 + 35 = 32735
        assert site.crs_epsg == 32735


@pytest.mark.django_db
class TestWtgModel(TestCase):
    """Test WtgModel."""
    
    def test_ct_status_missing_when_no_points(self):
        """Test Ct status is missing when no Ct points exist."""
        wtg = WtgModel.objects.create(
            name="Test Turbine",
            rotor_d_m=120,
            hub_height_default_m=90,
            v_in_mps=3,
            v_rated_mps=12,
            v_out_mps=25
        )
        
        wtg.update_ct_status()
        assert wtg.ct_status == WtgModel.CT_STATUS_MISSING
    
    def test_ct_status_suspect_out_of_range(self):
        """Test Ct status is suspect for values outside [0, 1.2]."""
        wtg = WtgModel.objects.create(
            name="Test Turbine",
            rotor_d_m=120,
            hub_height_default_m=90,
            v_in_mps=3,
            v_rated_mps=12,
            v_out_mps=25
        )
        
        CtCurvePoint.objects.create(wtg_model=wtg, v_mps=5, ct=1.5)
        CtCurvePoint.objects.create(wtg_model=wtg, v_mps=10, ct=0.8)
        
        wtg.update_ct_status()
        assert wtg.ct_status == WtgModel.CT_STATUS_SUSPECT
    
    def test_ct_status_suspect_large_gap(self):
        """Test Ct status is suspect for gaps > 1.5 m/s."""
        wtg = WtgModel.objects.create(
            name="Test Turbine",
            rotor_d_m=120,
            hub_height_default_m=90,
            v_in_mps=3,
            v_rated_mps=12,
            v_out_mps=25
        )
        
        CtCurvePoint.objects.create(wtg_model=wtg, v_mps=5, ct=0.8)
        CtCurvePoint.objects.create(wtg_model=wtg, v_mps=8, ct=0.9)
        
        wtg.update_ct_status()
        assert wtg.ct_status == WtgModel.CT_STATUS_SUSPECT
    
    def test_ct_status_ok(self):
        """Test Ct status is OK for valid curve."""
        wtg = WtgModel.objects.create(
            name="Test Turbine",
            rotor_d_m=120,
            hub_height_default_m=90,
            v_in_mps=3,
            v_rated_mps=12,
            v_out_mps=25
        )
        
        for v in range(3, 26):
            CtCurvePoint.objects.create(wtg_model=wtg, v_mps=v, ct=0.8)
        
        wtg.update_ct_status()
        assert wtg.ct_status == WtgModel.CT_STATUS_OK


@pytest.mark.django_db
class TestTurbine(TestCase):
    """Test Turbine model."""
    
    def test_turbine_role_new_scored_default(self):
        """Test turbine defaults to new_scored role."""
        project = Project.objects.create(name="Test Project")
        site = Site.objects.create(
            project=project,
            name="Test Site",
            center_lon_deg=0,
            center_lat_deg=0
        )
        layout = Layout.objects.create(site=site, name="Layout 1")
        turbine = Turbine.objects.create(
            layout=layout,
            local_id="T01",
            x_m=1000,
            y_m=2000,
            z_base_m=100,
            hub_height_m=90,
            rotor_d_m=120
        )
        
        assert turbine.role == Turbine.ROLE_NEW_SCORED
    
    def test_get_speed_class_override(self):
        """Test speed class override works."""
        project = Project.objects.create(name="Test Project")
        site = Site.objects.create(
            project=project,
            name="Test Site",
            center_lon_deg=0,
            center_lat_deg=0
        )
        layout = Layout.objects.create(site=site, name="Layout 1")
        wtg = WtgModel.objects.create(
            name="Test WTG",
            rotor_d_m=120,
            hub_height_default_m=90,
            v_in_mps=3,
            v_rated_mps=12,
            v_out_mps=25,
            default_speed_class='II'
        )
        turbine = Turbine.objects.create(
            layout=layout,
            local_id="T01",
            x_m=1000,
            y_m=2000,
            z_base_m=100,
            hub_height_m=90,
            rotor_d_m=120,
            model=wtg,
            speed_class_override='I'
        )
        
        assert turbine.get_speed_class() == 'I'
    
    def test_get_speed_class_from_model(self):
        """Test speed class from model when no override."""
        project = Project.objects.create(name="Test Project")
        site = Site.objects.create(
            project=project,
            name="Test Site",
            center_lon_deg=0,
            center_lat_deg=0
        )
        layout = Layout.objects.create(site=site, name="Layout 1")
        wtg = WtgModel.objects.create(
            name="Test WTG",
            rotor_d_m=120,
            hub_height_default_m=90,
            v_in_mps=3,
            v_rated_mps=12,
            v_out_mps=25,
            default_speed_class='III'
        )
        turbine = Turbine.objects.create(
            layout=layout,
            local_id="T01",
            x_m=1000,
            y_m=2000,
            z_base_m=100,
            hub_height_m=90,
            rotor_d_m=120,
            model=wtg
        )
        
        assert turbine.get_speed_class() == 'III'


@pytest.mark.django_db
class TestHubClimate(TestCase):
    """Test HubClimate model."""
    
    def test_create_hub_climate(self):
        """Test creating hub climate."""
        project = Project.objects.create(name="Test Project")
        site = Site.objects.create(
            project=project,
            name="Test Site",
            center_lon_deg=0,
            center_lat_deg=0
        )
        hub_climate = HubClimate.objects.create(
            site=site,
            name="Test Climate",
            bin_width_mps=1.0,
            v50_mps=40.0
        )
        
        assert hub_climate.period_hours == 8760
        assert hub_climate.rho_kgm3 == 1.225
        assert str(hub_climate) == "Test Climate (Test Site)"
