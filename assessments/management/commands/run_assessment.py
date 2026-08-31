"""
Management command to run an assessment.
"""
from django.core.management.base import BaseCommand
from assessments.models import Assessment
from assessments.services import run_assessment_for_turbine


class Command(BaseCommand):
    help = 'Run site suitability assessment'

    def add_arguments(self, parser):
        parser.add_argument('assessment_id', type=int, help='Assessment ID to run')

    def handle(self, *args, **options):
        assessment_id = options['assessment_id']
        
        try:
            assessment = Assessment.objects.get(pk=assessment_id)
        except Assessment.DoesNotExist:
            self.stderr.write(self.style.ERROR(f'Assessment {assessment_id} does not exist'))
            return
        
        self.stdout.write(f'Running assessment: {assessment.name}')
        
        assessment_turbines = assessment.assessment_turbines.all()
        
        if not assessment_turbines.exists():
            self.stderr.write(self.style.ERROR('No turbines to assess'))
            return
        
        for assessment_turbine in assessment_turbines:
            self.stdout.write(f'  Assessing turbine: {assessment_turbine.turbine.local_id}')
            try:
                result = run_assessment_for_turbine(assessment_turbine)
                self.stdout.write(self.style.SUCCESS(f'    Status: {result["overall"]}'))
            except Exception as e:
                self.stderr.write(self.style.ERROR(f'    Error: {e}'))
        
        self.stdout.write(self.style.SUCCESS(f'Assessment complete. Overall status: {assessment.overall_status}'))
