"""
Management command to import Ct curve from CSV file.

CSV format:
v_mps,ct
3.0,0.82
4.0,0.85
...
"""
import csv
from django.core.management.base import BaseCommand, CommandError
from turbines.models import WtgModel, CtCurvePoint


class Command(BaseCommand):
    help = 'Import Ct curve from CSV file (v_mps,ct)'

    def add_arguments(self, parser):
        parser.add_argument('model_name', type=str, help='WTG model name')
        parser.add_argument('csv_file', type=str, help='Path to CSV file')
        parser.add_argument(
            '--replace',
            action='store_true',
            help='Replace existing Ct curve points'
        )

    def handle(self, *args, **options):
        model_name = options['model_name']
        csv_file = options['csv_file']
        replace = options['replace']

        # Get model
        try:
            wtg_model = WtgModel.objects.get(name=model_name)
        except WtgModel.DoesNotExist:
            raise CommandError(f"WTG model '{model_name}' does not exist")

        # Parse CSV
        ct_points = []
        try:
            with open(csv_file, 'r') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    v_mps = float(row['v_mps'])
                    ct = float(row['ct'])
                    ct_points.append({'v_mps': v_mps, 'ct': ct})
        except FileNotFoundError:
            raise CommandError(f"CSV file '{csv_file}' not found")
        except (KeyError, ValueError) as e:
            raise CommandError(f"Invalid CSV format: {e}")

        if not ct_points:
            raise CommandError("No Ct points found in CSV")

        # Sort by v_mps
        ct_points.sort(key=lambda p: p['v_mps'])

        # Replace or fail if exists
        existing_count = wtg_model.ct_curve_points.count()
        if existing_count > 0 and not replace:
            raise CommandError(
                f"Model '{model_name}' already has {existing_count} Ct points. "
                f"Use --replace to overwrite."
            )

        if replace:
            wtg_model.ct_curve_points.all().delete()
            self.stdout.write(f"Deleted {existing_count} existing Ct points")

        # Create new points
        for pt in ct_points:
            CtCurvePoint.objects.create(
                wtg_model=wtg_model,
                v_mps=pt['v_mps'],
                ct=pt['ct']
            )

        # Update Ct status
        wtg_model.update_ct_status()
        wtg_model.save()

        self.stdout.write(
            self.style.SUCCESS(
                f"Imported {len(ct_points)} Ct points for '{model_name}'. "
                f"Ct status: {wtg_model.ct_status}"
            )
        )
