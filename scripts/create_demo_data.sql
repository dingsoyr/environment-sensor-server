PRAGMA foreign_keys = ON;

BEGIN IMMEDIATE;

INSERT INTO devices (
    device_id,
    device_name,
    firmware_version,
    config_version,
    reported_config_version,
    measurement_interval_seconds,
    last_seen_at,
    rssi_dbm,
    battery_voltage,
    battery_percent
)
SELECT
    'sensor-demo-001',
    'Demo sensor',
    'demo-sql-1.0',
    1,
    1,
    3600,
    CAST(strftime('%s', 'now') AS INTEGER) / 3600 * 3600,
    -67,
    4.08,
    96
WHERE NOT EXISTS (
    SELECT 1
    FROM devices
    WHERE device_id = 'sensor-demo-001'
);

UPDATE devices
SET device_name = 'Demo sensor',
    firmware_version = 'demo-sql-1.0',
    config_version = 1,
    reported_config_version = 1,
    measurement_interval_seconds = 3600,
    last_seen_at = CAST(strftime('%s', 'now') AS INTEGER) / 3600 * 3600,
    rssi_dbm = -67,
    battery_voltage = 4.08,
    battery_percent = 96
WHERE device_id = 'sensor-demo-001';

DELETE FROM measurements
WHERE device_id = 'sensor-demo-001';

WITH RECURSIVE
    parameters AS (
        SELECT
            'sensor-demo-001' AS device_id,
            CAST(strftime('%s', 'now') AS INTEGER) / 3600 * 3600 AS latest_hour,
            17520 AS total_points,
            24 * 365.0 AS seasonal_cycle_hours,
            6.283185307179586 AS tau
    ),
    hours(hour_index) AS (
        SELECT 0
        UNION ALL
        SELECT hour_index + 1
        FROM hours, parameters
        WHERE hour_index + 1 < parameters.total_points
    )
INSERT INTO measurements (
    device_id,
    sequence,
    measured_at,
    timestamp_valid,
    temperature_c,
    humidity_percent,
    pressure_hpa
)
SELECT
    parameters.device_id,
    hours.hour_index + 1,
    parameters.latest_hour - ((parameters.total_points - 1 - hours.hour_index) * 3600),
    1,
    ROUND(
        19.5
        + 5.2 * sin(parameters.tau * (hours.hour_index % 24) / 24.0)
        + 4.1 * sin(parameters.tau * hours.hour_index / parameters.seasonal_cycle_hours)
        + 0.4 * sin(parameters.tau * hours.hour_index / 168.0),
        2
    ),
    ROUND(
        61.0
        - 8.5 * sin(parameters.tau * (hours.hour_index % 24) / 24.0)
        - 3.2 * sin(parameters.tau * hours.hour_index / parameters.seasonal_cycle_hours)
        + 1.8 * sin(parameters.tau * hours.hour_index / 96.0),
        2
    ),
    ROUND(
        1013.2
        + 6.8 * sin(parameters.tau * hours.hour_index / 216.0)
        + 1.9 * sin(parameters.tau * hours.hour_index / 72.0),
        2
    )
FROM parameters
CROSS JOIN hours;

COMMIT;