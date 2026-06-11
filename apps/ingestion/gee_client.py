def get_rainfall_forecast(days: int = 7) -> list:
    """
    Get 7-day rainfall forecast for Maga region.
    Uses CHIRPS seasonal climatology + recent trend.
    This is the most reliable method for this region.
    Returns list of dicts: {forecast_date, predicted_mm, risk_level, day_offset}
    """
    authenticate_gee()
    maga = ee.Geometry.Rectangle(MAGA_BBOX)

    today = ee.Date(datetime.now().strftime('%Y-%m-%d'))

    # Get recent 14-day average rainfall (trend component)
    recent_start = (datetime.now() - timedelta(days=14)).strftime('%Y-%m-%d')
    recent_end   = datetime.now().strftime('%Y-%m-%d')

    recent_chirps = (ee.ImageCollection('UCSB-CHG/CHIRPS/DAILY')
                     .filterBounds(maga)
                     .filterDate(recent_start, recent_end)
                     .select('precipitation'))

    recent_mean = recent_chirps.mean().reduceRegion(
        reducer=ee.Reducer.mean(),
        geometry=maga,
        scale=5566,
        maxPixels=1e8
    ).getInfo()

    avg_daily_rain = recent_mean.get('precipitation', 5.0) or 5.0

    # Get seasonal average for this time of year (historical)
    current_doy = datetime.now().timetuple().tm_yday
    doy_start   = max(1, current_doy - 15)
    doy_end     = min(365, current_doy + 22)

    historical = (ee.ImageCollection('UCSB-CHG/CHIRPS/DAILY')
                  .filterBounds(maga)
                  .filterDate('2015-01-01', '2025-12-31')
                  .filter(ee.Filter.calendarRange(doy_start, doy_end, 'day_of_year'))
                  .select('precipitation'))

    historical_result = historical.mean().reduceRegion(
        reducer=ee.Reducer.mean(),
        geometry=maga,
        scale=5566,
        maxPixels=1e8
    ).getInfo()

    seasonal_avg = historical_result.get('precipitation', 5.0) or 5.0

    # Build 7-day forecast
    results = []
    for d in range(1, days + 1):
        forecast_date = datetime.now() + timedelta(days=d)

        # Weighted combination with decay for uncertainty
        decay       = 0.95 ** d
        base_rain   = (seasonal_avg * 0.6) + (avg_daily_rain * 0.4)
        pred_mm     = round(max(base_rain * decay, 0.0), 1)

        # Determine risk level
        if pred_mm >= 80:
            risk = 'critical'
        elif pred_mm >= 50:
            risk = 'high'
        elif pred_mm >= 25:
            risk = 'medium'
        else:
            risk = 'low'

        results.append({
            'forecast_date': forecast_date.strftime('%Y-%m-%d'),
            'predicted_mm':  pred_mm,
            'risk_level':    risk,
            'day_offset':    d,
            'source':        'CHIRPS-seasonal',
        })

    logger.info(f'Forecast generated: {len(results)} days, '
                f'seasonal_avg={seasonal_avg:.1f}mm, '
                f'recent_avg={avg_daily_rain:.1f}mm')
    return results