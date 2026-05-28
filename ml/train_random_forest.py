# ml/train_random_forest.py
"""
Train the Random Forest flood prediction model.

Run from the backend/ directory with venv active:
    python manage.py train_model

Or directly:
    python -c "import django; django.setup(); from ml.train_random_forest import train; train()"
"""
import json
import logging
import os
import pickle
from datetime import datetime

import django
from django.utils import timezone
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import (
    classification_report,
    f1_score,
    roc_auc_score,
    confusion_matrix,
)
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

logger = logging.getLogger(__name__)

# Where trained models are saved
MODELS_DIR = os.path.join(os.path.dirname(__file__), 'models')


def train(verbose: bool = True) -> dict:
    """
    Full training pipeline.

    1. Load data from Django database
    2. Engineer features
    3. Split into train/test (temporal split — no shuffle)
    4. Train Random Forest pipeline
    5. Evaluate on test set
    6. Save model to disk
    7. Register model in database

    Returns:
        dict with model metadata and performance metrics
    """
    os.makedirs(MODELS_DIR, exist_ok=True)

    if verbose:
        print('\n' + '='*60)
        print('FLOOD-WATCH CAMEROON — ML MODEL TRAINING')
        print('='*60)

    # ── 1. LOAD DATA ─────────────────────────────────────────────
    print('\n[1/7] Loading data from database...')

    from apps.predictions.models import RainfallReading, WaterLevelReading
    from apps.floods.models import FloodEvent
    from ml.feature_engineering import prepare_training_dataframe, FEATURE_NAMES

    rainfall_qs     = RainfallReading.objects.all()
    water_qs        = WaterLevelReading.objects.all()
    flood_events_qs = FloodEvent.objects.filter(is_confirmed=True)

    print(f'   Rainfall readings:  {rainfall_qs.count()}')
    print(f'   Water readings:     {water_qs.count()}')
    print(f'   Flood events:       {flood_events_qs.count()}')

    if rainfall_qs.count() < 100:
        print('\nERROR: Not enough rainfall data!')
        print('Run: python manage.py load_csv_data --all')
        return {}

    # ── 2. FEATURE ENGINEERING ───────────────────────────────────
    print('\n[2/7] Engineering features...')
    df = prepare_training_dataframe(rainfall_qs, water_qs, flood_events_qs)

    flood_count    = df['label'].sum()
    no_flood_count = len(df) - flood_count

    print(f'   Total samples:  {len(df)}')
    print(f'   Flood days:     {flood_count} ({flood_count/len(df)*100:.1f}%)')
    print(f'   No-flood days:  {no_flood_count} ({no_flood_count/len(df)*100:.1f}%)')

    if flood_count == 0:
        print('\nWARNING: No flood events found in training data!')
        print('Make sure flood events are added in the admin panel')
        print('with dates that overlap with your rainfall data (2015-2024)')

    # ── 3. TRAIN / TEST SPLIT ────────────────────────────────────
    print('\n[3/7] Splitting data (temporal split — no shuffle)...')

    # Sort by date to preserve time order
    df = df.sort_values('date').reset_index(drop=True)

    X = df[FEATURE_NAMES].values
    y = df['label'].values

    # 80% train, 20% test — NO shuffle (must preserve temporal order)
    split_idx = int(len(X) * 0.80)
    X_train, X_test = X[:split_idx], X[split_idx:]
    y_train, y_test = y[:split_idx], y[split_idx:]

    print(f'   Training samples: {len(X_train)}')
    print(f'   Testing samples:  {len(X_test)}')
    print(f'   Test flood days:  {y_test.sum()}')

    # ── 4. TRAIN MODEL ───────────────────────────────────────────
    print('\n[4/7] Training Random Forest...')
    print('   (This may take 1-3 minutes...)')

    pipeline = Pipeline([
        ('scaler', StandardScaler()),
        ('clf', RandomForestClassifier(
            n_estimators  = 300,
            max_depth     = 12,
            min_samples_leaf = 3,
            class_weight  = 'balanced',  # handles imbalanced flood/no-flood
            random_state  = 42,
            n_jobs        = -1,           # use all CPU cores
        ))
    ])

    pipeline.fit(X_train, y_train)
    print('   Training complete!')

    # ── 5. EVALUATE ──────────────────────────────────────────────
    print('\n[5/7] Evaluating model...')

    y_pred = pipeline.predict(X_test)
    y_prob = pipeline.predict_proba(X_test)[:, 1]

    f1  = f1_score(y_test, y_pred, zero_division=0)
    auc = roc_auc_score(y_test, y_prob) if y_test.sum() > 0 else 0.0

    print(f'\n   F1 Score:  {f1:.4f}')
    print(f'   AUC-ROC:   {auc:.4f}')
    print(f'\n   Classification Report:')
    print(classification_report(y_test, y_pred,
                                 target_names=['No Flood', 'Flood'],
                                 zero_division=0))

    # Feature importances
    rf           = pipeline.named_steps['clf']
    importances  = dict(zip(FEATURE_NAMES, rf.feature_importances_))
    top_features = sorted(importances.items(), key=lambda x: -x[1])[:5]
    print('   Top 5 most important features:')
    for name, importance in top_features:
        print(f'   {name:25s}: {importance:.4f}')

    # ── 6. SAVE MODEL ────────────────────────────────────────────
    print('\n[6/7] Saving model...')

    version    = f'rf-v{timezone.now().strftime("%Y%m%d-%H%M")}'
    model_path = os.path.join(MODELS_DIR, f'{version}.pkl')

    with open(model_path, 'wb') as f:
        pickle.dump(pipeline, f)

    metadata = {
        'version':          version,
        'model_type':       'random_forest',
        'f1_score':         round(f1, 4),
        'auc_roc':          round(auc, 4),
        'training_samples': len(X_train),
        'test_samples':     len(X_test),
        'flood_samples':    int(flood_count),
        'feature_names':    FEATURE_NAMES,
        'hyperparameters': {
            'n_estimators':     300,
            'max_depth':        12,
            'min_samples_leaf': 3,
            'class_weight':     'balanced',
        },
        'trained_at':  timezone.now().isoformat(),
        'model_path':  model_path,
    }

    # Save metadata as JSON
    meta_path = os.path.join(MODELS_DIR, f'{version}_metadata.json')
    with open(meta_path, 'w') as f:
        json.dump(metadata, f, indent=2)

    print(f'   Model saved to: {model_path}')

    # ── 7. REGISTER IN DATABASE ──────────────────────────────────
    print('\n[7/7] Registering model in database...')

    from apps.predictions.models import MLModel

    # Deactivate any existing active models
    MLModel.objects.filter(is_active=True).update(is_active=False)

    # Create new model record
    ml_model = MLModel.objects.create(
        version          = version,
        model_type       = 'random_forest',
        file_path        = model_path,
        is_active        = True,
        f1_score         = round(f1, 4),
        auc_roc          = round(auc, 4),
        training_samples = len(X_train),
        feature_names    = FEATURE_NAMES,
        hyperparameters  = metadata['hyperparameters'],
        trained_at       = timezone.now(),
    )

    print(f'   Model registered: {version} (active=True)')

    print('\n' + '='*60)
    print('TRAINING COMPLETE!')
    print(f'F1 Score: {f1:.4f} | AUC-ROC: {auc:.4f}')
    print(f'Model version: {version}')
    print('='*60 + '\n')

    return metadata