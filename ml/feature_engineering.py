# ml/feature_engineering.py
"""
Feature engineering for the flood prediction model.

CRITICAL RULE: This file is used at BOTH training time and inference time.
Never change FEATURE_NAMES without retraining the model.
"""
import numpy as np
import pandas as pd
from datetime import datetime

# ── THE CANONICAL FEATURE LIST ────────────────────────────────────────────────
# The order here MUST match what the model was trained on.
# Never change this list without retraining.
FEATURE_NAMES = [
    'rainfall_1d',       # Daily rainfall in mm
    'rainfall_7d',       # 7-day cumulative rainfall in mm
    'rainfall_30d',      # 30-day cumulative rainfall in mm
    'sar_ratio',         # SAR backscatter change ratio (negative = water)
    'water_area_km2',    # Lake Maga current water area in km²
    'ndwi_mean',         # Mean NDWI value (positive = water)
    'doy',               # Day of year (1-365) — raw
    'doy_sin',           # Sine encoding of day of year — captures seasonality
    'doy_cos',           # Cosine encoding of day of year — captures seasonality
    'rainfall_7d_ratio', # 7d rainfall / 30d rainfall — intensity signal
    'water_anomaly',     # (current - baseline) / baseline — lake fill level
]

# Historical constants for Maga region
BASELINE_WATER_KM2 = 38.0  # Calibrated from actual JRC water_area_m2 data (2015-2021 average)  # Lake Maga historical mean area
MEAN_30D_RAINFALL_MM  = 85.0    # Mean 30-day cumulative (July-October)
STD_30D_RAINFALL_MM   = 42.0    # Standard deviation


def engineer_features(raw: dict) -> np.ndarray:
    """
    Convert raw GEE or database readings into an ML feature vector.

    Args:
        raw: dict containing:
            - rainfall_1d:    float, mm/day
            - rainfall_7d:    float, cumulative mm over 7 days
            - rainfall_30d:   float, cumulative mm over 30 days
            - sar_ratio:      float, SAR backscatter change ratio
            - water_area_km2: float, Lake Maga area in km²
            - ndwi_mean:      float, mean NDWI
            - date:           str, ISO format YYYY-MM-DD

    Returns:
        numpy array of shape (1, 11) — one row, 11 features
    """
    # Parse date to get day of year
    date_str = raw.get('date', datetime.now().strftime('%Y-%m-%d'))
    try:
        parsed_date = datetime.fromisoformat(str(date_str)[:10])
    except (ValueError, TypeError):
        parsed_date = datetime.now()

    doy = parsed_date.timetuple().tm_yday  # 1 to 365

    # Get raw values with safe defaults
    rainfall_1d    = float(raw.get('rainfall_1d', 0.0) or 0.0)
    rainfall_7d    = float(raw.get('rainfall_7d', 0.0) or 0.0)
    rainfall_30d   = float(raw.get('rainfall_30d', 0.0) or 0.0)
    sar_ratio      = float(raw.get('sar_ratio', 0.0) or 0.0)
    water_area_km2 = float(raw.get('water_area_km2', BASELINE_WATER_KM2) or BASELINE_WATER_KM2)
    ndwi_mean      = float(raw.get('ndwi_mean', 0.0) or 0.0)

    # Computed features
    doy_sin = np.sin(2 * np.pi * doy / 365)
    doy_cos = np.cos(2 * np.pi * doy / 365)

    # Rainfall intensity: how much of the 30-day total fell in the last 7 days
    rainfall_7d_ratio = rainfall_7d / max(rainfall_30d, 1.0)

    # Water anomaly: how much above/below the baseline is the lake?
    water_anomaly = (water_area_km2 - BASELINE_WATER_KM2) / BASELINE_WATER_KM2

    # Build feature dict in EXACT order of FEATURE_NAMES
    features = {
        'rainfall_1d':       rainfall_1d,
        'rainfall_7d':       rainfall_7d,
        'rainfall_30d':      rainfall_30d,
        'sar_ratio':         sar_ratio,
        'water_area_km2':    water_area_km2,
        'ndwi_mean':         ndwi_mean,
        'doy':               float(doy),
        'doy_sin':           float(doy_sin),
        'doy_cos':           float(doy_cos),
        'rainfall_7d_ratio': float(rainfall_7d_ratio),
        'water_anomaly':     float(water_anomaly),
    }

    # Return as numpy array in the correct order
    return np.array(
        [[features[k] for k in FEATURE_NAMES]],
        dtype=np.float32
    )


def prepare_training_dataframe(
    rainfall_qs,
    water_qs,
    flood_events_qs
) -> pd.DataFrame:
    """
    Build the training dataset from Django querysets.
    Merges rainfall readings with water level readings,
    then labels each row as flood (1) or no flood (0)
    based on known historical flood events.

    Args:
        rainfall_qs:     RainfallReading queryset
        water_qs:        WaterLevelReading queryset
        flood_events_qs: FloodEvent queryset

    Returns:
        DataFrame with FEATURE_NAMES columns + 'label' column
    """
    # Convert querysets to DataFrames
    rainfall_data = list(rainfall_qs.values(
        'date', 'rainfall_mm', 'cumulative_7d', 'cumulative_30d'
    ))
    water_data = list(water_qs.values(
        'date', 'water_area_km2'
    ))
    flood_data = list(flood_events_qs.values(
        'event_date', 'end_date'
    ))

    if not rainfall_data:
        raise ValueError(
            'No rainfall data found in database. '
            'Run: python manage.py load_csv_data --all'
        )

    # Build rainfall DataFrame
    rain_df = pd.DataFrame(rainfall_data)
    rain_df['date'] = pd.to_datetime(rain_df['date'])

    # Build water level DataFrame
    if water_data:
        water_df = pd.DataFrame(water_data)
        water_df['date'] = pd.to_datetime(water_df['date'])
        # Resample monthly water data to daily by forward-filling
        water_df = water_df.set_index('date').resample('D').ffill().reset_index()
    else:
        # No water data — use baseline
        water_df = rain_df[['date']].copy()
        water_df['water_area_km2'] = BASELINE_WATER_KM2

    # Merge rainfall and water data on date
    merged = pd.merge(rain_df, water_df, on='date', how='left')
    merged['water_area_km2'] = merged['water_area_km2'].fillna(BASELINE_WATER_KM2)

    # Add placeholder columns for SAR and NDWI
    # (these come from GEE in real inference — use 0 for training)
    merged['sar_ratio']  = 0.0
    merged['ndwi_mean']  = 0.0

    # Label each row — 1 if the date falls inside a flood event window
    merged['label'] = 0
    for event in flood_data:
        start = pd.to_datetime(event['event_date'])
        end   = pd.to_datetime(event['end_date']) if event['end_date'] else start

        mask = (merged['date'] >= start) & (merged['date'] <= end)
        merged.loc[mask, 'label'] = 1

    # Engineer all features for each row
    feature_rows = []
    for _, row in merged.iterrows():
        feat = engineer_features({
            'rainfall_1d':    row['rainfall_mm'],
            'rainfall_7d':    row['cumulative_7d'],
            'rainfall_30d':   row['cumulative_30d'],
            'sar_ratio':      row['sar_ratio'],
            'water_area_km2': row['water_area_km2'],
            'ndwi_mean':      row['ndwi_mean'],
            'date':           row['date'].strftime('%Y-%m-%d'),
        })
        feature_rows.append(feat[0])

    # Build final feature DataFrame
    feature_df = pd.DataFrame(feature_rows, columns=FEATURE_NAMES)
    feature_df['label'] = merged['label'].values
    feature_df['date']  = merged['date'].values

    return feature_df