"""
Tests for HTML report rendering.
"""
from django.test import TestCase, Client
from django.contrib.auth.models import User
from django.urls import reverse
from projects.models import Project, ClassEnvelope
from sites.models import Site
from turbines.models import Layout, Turbine, WtgModel, CtCurvePoint
from climate.models import HubClimate, TiBin
from assessments.models import Assessment, AssessmentTurbine
from assessments.services import run_assessment_for_turbine


class ReportRenderingTests(TestCase):
    """Test that assessment report HTML renders correctly with all required elements."""
    
    def setUp(self):
        self.client = Client()
        
        # Create and login test user
        self.user = User.objects.create_user(username='testuser', password='testpass')
        self.client.login(username='testuser', password='testpass')
        
        # Create project and class envelope
        self.project = Project.objects.create(name="Test Project")
        self.class_envelope = ClassEnvelope.objects.create(
            project=self.project,
            vref_ii=42.5,
            iref_b=0.14,
            vave_over_vref=0.2
        )
        
        # Create site
        self.site = Site.objects.create(
            project=self.project,
            name="Test Site",
            center_lon_deg=10.0,
            center_lat_deg=55.0,
            default_complexity='simple'
        )
        
        # Create layout
        self.layout = Layout.objects.create(site=self.site, name="Test Layout")
        
        # Create WTG model with Ct curve
        self.wtg_model = WtgModel.objects.create(
            name="TestTurbine",
            rotor_d_m=120.0,
            hub_height_default_m=100.0,
            v_in_mps=3.0,
            v_rated_mps=11.0,
            v_out_mps=25.0,
            default_speed_class='II',
            default_ti_category='B',
            ct_status=WtgModel.CT_STATUS_OK
        )
        
        # Add Ct curve points
        CtCurvePoint.objects.create(wtg_model=self.wtg_model, v_mps=3.0, ct=0.80)
        CtCurvePoint.objects.create(wtg_model=self.wtg_model, v_mps=11.0, ct=0.75)
        CtCurvePoint.objects.create(wtg_model=self.wtg_model, v_mps=25.0, ct=0.05)
        
        # Create turbines
        self.turbine1 = Turbine.objects.create(
            layout=self.layout,
            local_id='T01',
            role='new_scored',
            x_m=0.0,
            y_m=0.0,
            z_base_m=50.0,
            hub_height_m=100.0,
            rotor_d_m=120.0,
            model=self.wtg_model
        )
        
        self.turbine2 = Turbine.objects.create(
            layout=self.layout,
            local_id='T02',
            role='new_scored',
            x_m=960.0,  # 8D spacing
            y_m=0.0,
            z_base_m=50.0,
            hub_height_m=100.0,
            rotor_d_m=120.0,
            model=self.wtg_model
        )
        
        # Create hub climate with TI bins
        self.hub_climate = HubClimate.objects.create(
            site=self.site,
            name="Test Climate",
            period_hours=8760,
            bin_width_mps=1.0,
            rho_kgm3=1.225,
            v50_mps=40.0,
            shear_alpha=0.15,
            inflow_angle_deg=0.0
        )
        
        # Add TI bins covering the speed window
        for v in range(4, 21):
            TiBin.objects.create(
                hub_climate=self.hub_climate,
                v_center_mps=float(v),
                hours=100.0,
                mean_sigma_mps=0.5,
                std_sigma_mps=0.15
            )
        
        # Create assessment
        self.assessment = Assessment.objects.create(
            project=self.project,
            site=self.site,
            name="Test Assessment",
            edition='ed4',
            class_envelope_snapshot={
                'vref_ii': 42.5,
                'iref_b': 0.14,
                'vave_over_vref': 0.2,
                'class_envelope_django_defaults': True
            }
        )
        
        # Create assessment turbine
        self.assessment_turbine = AssessmentTurbine.objects.create(
            assessment=self.assessment,
            turbine=self.turbine1,
            hub_climate=self.hub_climate,
            resolved_vref_mps=42.5,
            resolved_iref=0.14,
            resolved_vave_mps=8.5,
            cct=1.0,
            apply_density_to_v50=False,
            wohler_exponents=[4, 10]
        )
        
        # Run assessment to generate check results
        run_assessment_for_turbine(self.assessment_turbine)
    
    def test_report_renders_successfully(self):
        """Test that report renders without TemplateSyntaxError."""
        response = self.client.get(
            reverse('assessments:report', kwargs={'pk': self.assessment.pk})
        )
        
        # Should return 200, not TemplateSyntaxError
        self.assertEqual(response.status_code, 200)
    
    def test_report_contains_speed_window(self):
        """Test that report shows speed window [V_lo, V_hi]."""
        response = self.client.get(
            reverse('assessments:report', kwargs={'pk': self.assessment.pk})
        )
        
        self.assertEqual(response.status_code, 200)
        content = response.content.decode('utf-8')
        
        # Should show speed window
        self.assertIn('Speed Window:', content)
        # Ed4: [Vave, 2*Vave] = [8.5, 17.0]
        self.assertIn('[8.50, 17.00]', content)
        self.assertIn('Ed4: [Vave, 2*Vave]', content)
    
    def test_report_contains_per_bin_ti_table(self):
        """Test that report shows per-bin TI table headers."""
        response = self.client.get(
            reverse('assessments:report', kwargs={'pk': self.assessment.pk})
        )
        
        self.assertEqual(response.status_code, 200)
        content = response.content.decode('utf-8')
        
        # Per-bin TI table headers
        self.assertIn('Per-Bin Turbulence Intensity (NTM Check)', content)
        self.assertIn('σ90 (m/s)', content)
        self.assertIn('σ_site (m/s)', content)
        self.assertIn('σ_NTM (m/s)', content)
        self.assertIn('TI_site', content)
        self.assertIn('TI_NTM', content)
    
    def test_report_contains_distribution_overlay(self):
        """Test that report shows distribution overlay table."""
        response = self.client.get(
            reverse('assessments:report', kwargs={'pk': self.assessment.pk})
        )
        
        self.assertEqual(response.status_code, 200)
        content = response.content.decode('utf-8')
        
        # Distribution overlay table
        self.assertIn('Distribution Overlay (Rayleigh Check)', content)
        self.assertIn('p_site', content)
        self.assertIn('p_Rayleigh', content)
    
    def test_report_contains_ieff_per_bin_table(self):
        """Test that report shows Ieff per-bin table if Ieff check ran."""
        response = self.client.get(
            reverse('assessments:report', kwargs={'pk': self.assessment.pk})
        )
        
        self.assertEqual(response.status_code, 200)
        content = response.content.decode('utf-8')
        
        # Ieff per-bin table (should be present after running assessment with neighbors)
        self.assertIn('Effective Turbulence per Bin (Ieff Check)', content)
        self.assertIn('σ_c (m/s)', content)
        self.assertIn('σ_eff (m/s)', content)
        self.assertIn('I_eff', content)
        self.assertIn('I_NTM', content)
        self.assertIn('R(10):', content)
        self.assertIn('R(4) (diagnostic):', content)
    
    def test_report_contains_class_envelope_caption(self):
        """Test that report shows 'Class envelope (editable)' caption."""
        response = self.client.get(
            reverse('assessments:report', kwargs={'pk': self.assessment.pk})
        )
        
        self.assertEqual(response.status_code, 200)
        content = response.content.decode('utf-8')
        
        # Class envelope caption
        self.assertIn('Class envelope (editable)', content)
        # Should mention product defaults when flag is True
        self.assertIn('product defaults', content)
        # Should NOT say "IEC Table 1"
        self.assertNotIn('IEC Table 1', content)
    
    def test_report_contains_screening_disclaimer(self):
        """Test that report shows prominent screening disclaimer."""
        response = self.client.get(
            reverse('assessments:report', kwargs={'pk': self.assessment.pk})
        )
        
        self.assertEqual(response.status_code, 200)
        content = response.content.decode('utf-8')
        
        # Screening disclaimer
        self.assertIn('SCREENING DISCLAIMER', content)
        self.assertIn('NOT a certified IEC 61400-1 assessment', content)
        # Should appear at least twice (top and bottom)
        self.assertGreaterEqual(content.count('SCREENING DISCLAIMER'), 2)
