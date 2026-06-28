"""
Generate a current RiskAssessment by running the active ML model
against the most recent rainfall and water data.

Usage:
    python manage.py generate_risk_assessment
    python manage.py generate_risk_assessment --demo-date 2025-09-15
"""
import pickle
from datetime import datetime

from django.core.management.base import BaseCommand
from django.utils import timezone

from apps.predictions.models import (
    RiskAssessment, RainfallReading, WaterLevelReading, MLModel,
)
from ml.feature_engineering import engineer_features


class Command(BaseCommand):
    help = 'Generate a flood risk assessment from the latest data'

    def add_arguments(self, parser):
        parser.add_argument(
            '--demo-date', type=str, default=None,
            help='Assess as if it were this date (YYYY-MM-DD), for demos',
        )

    def handle(self, *args, **opts):
        # Pick the assessment date
        if opts['demo_date']:
            assess_date = datetime.strptime(opts['demo_date'], '%Y-%m-%d').date()
        else:
            latest_rain = RainfallReading.objects.order_by('-date').first()
            assess_date = latest_rain.date if latest_rain else timezone.now().date()

        self.stdout.write(f'Assessing for date: {assess_date}')

        # Most recent rainfall on/before the assessment date
        rain = (RainfallReading.objects
                .filter(date__lte=assess_date)
                .order_by('-date')
                .first())
        if not rain:
            self.stdout.write(self.style.ERROR('No rainfall data found.'))
            return

        water = WaterLevelReading.get_latest()
        water_km2 = water.water_area_km2 if water else 38.0

        # Load active model
        model_rec = MLModel.get_active()
        if not model_rec or not model_rec.file_path:
            self.stdout.write(self.style.ERROR('No active ML model registered.'))
            return

        with open(model_rec.file_path, 'rb') as f:
            pipeline = pickle.load(f)

        # Build features and predict
        features = engineer_features({
            'rainfall_1d':    rain.rainfall_mm,
            'rainfall_7d':    rain.cumulative_7d,
            'rainfall_30d':   rain.cumulative_30d,
            'sar_ratio':      0.0,
            'water_area_km2': water_km2,
            'ndwi_mean':      0.0,
            'date':           assess_date.isoformat(),
        })

        probability = float(pipeline.predict_proba(features)[0][1])

        risk_level = (
            'critical' if probability >= 0.80 else
            'high'     if probability >= 0.60 else
            'medium'   if probability >= 0.30 else
            'low'
        )

        # Carry forward the previous level if one exists
        prev = RiskAssessment.objects.order_by('-assessed_at').first()
        previous_level = prev.risk_level if prev else risk_level

        assessment = RiskAssessment.objects.create(
            assessed_at         = timezone.now(),
            probability         = round(probability, 4),
            risk_level          = risk_level,
            previous_risk_level = previous_level,
            model_version       = model_rec.version,
            feature_vector      = {},
            is_manual_override  = False,
        )

        self.stdout.write(self.style.SUCCESS(
            f'Created assessment: {risk_level} ({probability:.1%}) '
            f'using {model_rec.version}'
        ))