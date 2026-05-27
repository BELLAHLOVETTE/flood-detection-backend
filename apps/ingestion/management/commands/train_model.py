# apps/ingestion/management/commands/train_model.py
"""
Management command to train the flood prediction ML model.

Usage:
    python manage.py train_model
"""
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = 'Train the Random Forest flood prediction model'

    def handle(self, *args, **options):
        self.stdout.write('Starting model training...\n')

        try:
            from ml.train_random_forest import train
            metadata = train(verbose=True)

            if metadata:
                self.stdout.write(self.style.SUCCESS(
                    f"\nModel training successful!"
                    f"\nVersion:  {metadata.get('version')}"
                    f"\nF1 Score: {metadata.get('f1_score')}"
                    f"\nAUC-ROC:  {metadata.get('auc_roc')}"
                ))
            else:
                self.stdout.write(self.style.WARNING(
                    'Training completed but no metadata returned. '
                    'Check that you have enough data.'
                ))

        except Exception as e:
            self.stdout.write(self.style.ERROR(f'Training failed: {e}'))
            raise