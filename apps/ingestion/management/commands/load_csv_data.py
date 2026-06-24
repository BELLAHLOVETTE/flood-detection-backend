# apps/ingestion/management/commands/load_csv_data.py
"""
Management command to load GEE-exported CSV data into the database.

Usage:
    python manage.py load_csv_data --rainfall data/maga_chirps_daily_2015_2024.csv
    python manage.py load_csv_data --lagoon   data/maga_lagoon_monthly_2015_2024.csv
    python manage.py load_csv_data --all
"""
import csv
import os
from datetime import datetime, date
from django.core.management.base import BaseCommand, CommandError
from django.conf import settings
from apps.predictions.models import RainfallReading, WaterLevelReading


class Command(BaseCommand):
    help = 'Load GEE-exported CSV data into the database'

    def add_arguments(self, parser):
        parser.add_argument(
            '--rainfall',
            type=str,
            help='Path to CHIRPS rainfall CSV file',
        )
        parser.add_argument(
            '--lagoon',
            type=str,
            help='Path to lagoon water level CSV file',
        )
        parser.add_argument(
            '--all',
            action='store_true',
            help='Load both CSV files using default paths in backend/data/',
        )

    def handle(self, *args, **options):

        if options['all']:
            # Use default file paths
            base_dir = settings.BASE_DIR / 'data'
            rainfall_path = base_dir / 'maga_chirps_daily_2000_2025.csv'
            lagoon_path   = base_dir / 'maga_lagoon_monthly_2015_2024.csv'

            if rainfall_path.exists():
                self._load_rainfall(str(rainfall_path))
            else:
                self.stdout.write(self.style.WARNING(
                    f'Rainfall CSV not found at {rainfall_path}'
                ))

            if lagoon_path.exists():
                self._load_lagoon(str(lagoon_path))
            else:
                self.stdout.write(self.style.WARNING(
                    f'Lagoon CSV not found at {lagoon_path}'
                ))

        elif options['rainfall']:
            self._load_rainfall(options['rainfall'])

        elif options['lagoon']:
            self._load_lagoon(options['lagoon'])

        else:
            raise CommandError(
                'Please specify --rainfall, --lagoon, or --all\n'
                'Example: python manage.py load_csv_data --all'
            )

    def _load_rainfall(self, filepath):
        """
        Load CHIRPS daily rainfall CSV into RainfallReading model.

        Expected CSV columns:
        date, rainfall_mm (or precipitation), year, month, doy
        """
        self.stdout.write(f'Loading rainfall data from {filepath}...')

        if not os.path.exists(filepath):
            raise CommandError(f'File not found: {filepath}')

        created_count = 0
        skipped_count = 0
        error_count   = 0

        with open(filepath, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)

            # Print the column names so we can see what GEE exported
            self.stdout.write(f'CSV columns: {reader.fieldnames}')

            rows = list(reader)
            total = len(rows)
            self.stdout.write(f'Total rows to process: {total}')

            for i, row in enumerate(rows):
                try:
                    # Handle different possible column names from GEE
                    date_str = (
                        row.get('date') or
                        row.get('Date') or
                        row.get('system:index', '')
                    ).strip()

                    if not date_str or date_str == 'null':
                        skipped_count += 1
                        continue

                    # Parse date — GEE exports as YYYY-MM-dd
                    try:
                        reading_date = datetime.strptime(
                            date_str[:10], '%Y-%m-%d'
                        ).date()
                    except ValueError:
                        skipped_count += 1
                        continue

                    # Get rainfall value — could be called different things
                    rainfall_raw = (
                        row.get('rainfall_mm') or
                        row.get('precipitation') or
                        row.get('mean') or
                        '0'
                    )

                    try:
                        rainfall_mm = float(rainfall_raw) if rainfall_raw and rainfall_raw != 'null' else 0.0
                    except (ValueError, TypeError):
                        rainfall_mm = 0.0

                    # Create or update the record
                    obj, created = RainfallReading.objects.update_or_create(
                        date=reading_date,
                        defaults={
                            'rainfall_mm':    round(rainfall_mm, 2),
                            'cumulative_7d':  0.0,  # will calculate after
                            'cumulative_30d': 0.0,  # will calculate after
                            'source':         'CHIRPS',
                        }
                    )

                    if created:
                        created_count += 1
                    else:
                        skipped_count += 1

                    # Progress update every 500 rows
                    if (i + 1) % 500 == 0:
                        self.stdout.write(f'  Processed {i+1}/{total}...')

                except Exception as e:
                    error_count += 1
                    if error_count <= 5:
                        self.stdout.write(
                            self.style.WARNING(f'  Row {i} error: {e} | Row data: {row}')
                        )

        self.stdout.write(self.style.SUCCESS(
            f'\nRainfall loading complete!'
            f'\n  Created: {created_count} new records'
            f'\n  Updated: {skipped_count} existing records'
            f'\n  Errors:  {error_count} rows'
        ))

        # Now calculate cumulative values
        self._calculate_cumulative_rainfall()

    def _calculate_cumulative_rainfall(self):
        """
        After loading all readings, calculate 7-day and 30-day
        cumulative rainfall for each date.
        """
        self.stdout.write('Calculating cumulative rainfall values...')

        readings = RainfallReading.objects.order_by('date')
        total    = readings.count()

        for i, reading in enumerate(readings):
            # 7-day cumulative: sum of rainfall from 7 days before this date
            from django.db.models import Sum

            seven_day_start  = reading.date - __import__('datetime').timedelta(days=7)
            thirty_day_start = reading.date - __import__('datetime').timedelta(days=30)

            cumul_7d = RainfallReading.objects.filter(
                date__gte=seven_day_start,
                date__lte=reading.date
            ).aggregate(total=Sum('rainfall_mm'))['total'] or 0.0

            cumul_30d = RainfallReading.objects.filter(
                date__gte=thirty_day_start,
                date__lte=reading.date
            ).aggregate(total=Sum('rainfall_mm'))['total'] or 0.0

            reading.cumulative_7d  = round(float(cumul_7d), 2)
            reading.cumulative_30d = round(float(cumul_30d), 2)
            reading.save(update_fields=['cumulative_7d', 'cumulative_30d'])

            if (i + 1) % 500 == 0:
                self.stdout.write(f'  Calculated cumulative for {i+1}/{total}...')

        self.stdout.write(self.style.SUCCESS('Cumulative values calculated!'))

    def _load_lagoon(self, filepath):
        """
        Load JRC lagoon water level CSV into WaterLevelReading model.

        Expected CSV columns:
        date, water_area_m2 (or water), year, month
        """
        self.stdout.write(f'Loading lagoon data from {filepath}...')

        if not os.path.exists(filepath):
            raise CommandError(f'File not found: {filepath}')

        created_count = 0
        skipped_count = 0
        error_count   = 0

        BASELINE_KM2 = 38.0  # Lake Maga historical baseline

        with open(filepath, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)

            self.stdout.write(f'CSV columns: {reader.fieldnames}')

            rows  = list(reader)
            total = len(rows)
            self.stdout.write(f'Total rows to process: {total}')

            for i, row in enumerate(rows):
                try:
                    # Get date — GEE exports lagoon as YYYY-MM format
                    date_str = (
                        row.get('date') or
                        row.get('Date') or
                        ''
                    ).strip()

                    if not date_str or date_str == 'null':
                        skipped_count += 1
                        continue

                    # Parse YYYY-MM format — use first day of month
                    try:
                        if len(date_str) == 7:
                            # Format: YYYY-MM
                            reading_date = datetime.strptime(
                                date_str, '%Y-%m'
                            ).date()
                        else:
                            # Format: YYYY-MM-DD
                            reading_date = datetime.strptime(
                                date_str[:10], '%Y-%m-%d'
                            ).date()
                    except ValueError:
                        skipped_count += 1
                        continue

                    # Get water area value
                    water_raw = (
                        row.get('water_area_m2') or
                        row.get('water') or
                        row.get('water_km2') or
                        row.get('mean') or
                        '0'
                    )

                    try:
                        water_raw_float = float(water_raw) if water_raw and water_raw != 'null' else 0.0
                    except (ValueError, TypeError):
                        water_raw_float = 0.0

                    # Convert m² to km² if the value is very large
                    # GEE exports water area in m², we store in km²
                    if water_raw_float > 10000:
                        water_km2 = water_raw_float / 1_000_000
                    else:
                        water_km2 = water_raw_float

                    water_km2 = round(water_km2, 2)

                    # Calculate change from baseline
                    if BASELINE_KM2 > 0:
                        change_pct = round(
                            ((water_km2 - BASELINE_KM2) / BASELINE_KM2) * 100, 1
                        )
                    else:
                        change_pct = 0.0

                    obj, created = WaterLevelReading.objects.update_or_create(
                        date=reading_date,
                        defaults={
                            'water_area_km2':    water_km2,
                            'baseline_area_km2': BASELINE_KM2,
                            'change_percent':    change_pct,
                            'source':            'JRC',
                        }
                    )

                    if created:
                        created_count += 1
                    else:
                        skipped_count += 1

                    if (i + 1) % 100 == 0:
                        self.stdout.write(f'  Processed {i+1}/{total}...')

                except Exception as e:
                    error_count += 1
                    if error_count <= 5:
                        self.stdout.write(
                            self.style.WARNING(f'  Row {i} error: {e} | Row: {row}')
                        )

        self.stdout.write(self.style.SUCCESS(
            f'\nLagoon loading complete!'
            f'\n  Created: {created_count} new records'
            f'\n  Updated: {skipped_count} existing records'
            f'\n  Errors:  {error_count} rows'
        ))