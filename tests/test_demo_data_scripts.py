from __future__ import annotations

from pathlib import Path

from app.database import connect_database, initialize_database


CREATE_SCRIPT_PATH = Path(__file__).resolve().parent.parent / "scripts" / "create_demo_data.sql"
DELETE_SCRIPT_PATH = Path(__file__).resolve().parent.parent / "scripts" / "delete_demo_data.sql"
EXPECTED_MEASUREMENT_COUNT = 730 * 24
EXPECTED_TIMESTAMP_SPAN_SECONDS = (EXPECTED_MEASUREMENT_COUNT - 1) * 3600
HALF_YEAR_HOURS = 24 * 182


def run_sql_script(database_path: Path, script_path: Path) -> None:
    script = script_path.read_text(encoding="utf-8")

    with connect_database(database_path) as connection:
        connection.executescript(script)


def test_demo_data_scripts_create_rerun_and_cleanup(tmp_path: Path) -> None:
    database_path = tmp_path / "environment.db"
    initialize_database(database_path)

    with connect_database(database_path) as connection:
        connection.execute(
            """
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
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            ("sensor-real-001", "Office sensor", "1.2.3", 7, 7, 1800, 1_700_000_000, -58, 3.91, 84),
        )
        connection.execute(
            """
            INSERT INTO measurements (
                device_id,
                sequence,
                measured_at,
                timestamp_valid,
                temperature_c,
                humidity_percent,
                pressure_hpa
            )
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            ("sensor-real-001", 9001, 1_700_000_000, 1, 22.4, 48.0, 1011.4),
        )

    run_sql_script(database_path, CREATE_SCRIPT_PATH)

    with connect_database(database_path) as connection:
        demo_device = connection.execute(
            """
            SELECT
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
            FROM devices
            WHERE device_id = 'sensor-demo-001'
            """
        ).fetchone()
        measurement_stats = connection.execute(
            """
            SELECT
                COUNT(*),
                COUNT(DISTINCT sequence),
                MIN(sequence),
                MAX(sequence),
                MIN(measured_at),
                MAX(measured_at),
                MIN(timestamp_valid),
                MAX(timestamp_valid),
                MIN(temperature_c),
                MAX(temperature_c),
                MIN(humidity_percent),
                MAX(humidity_percent),
                MIN(pressure_hpa),
                MAX(pressure_hpa)
            FROM measurements
            WHERE device_id = 'sensor-demo-001'
            """
        ).fetchone()
        hourly_spacing = connection.execute(
            """
            WITH ordered AS (
                SELECT
                    measured_at,
                    LAG(measured_at) OVER (ORDER BY measured_at, sequence) AS previous_measured_at
                FROM measurements
                WHERE device_id = 'sensor-demo-001'
            )
            SELECT MIN(measured_at - previous_measured_at), MAX(measured_at - previous_measured_at)
            FROM ordered
            WHERE previous_measured_at IS NOT NULL
            """
        ).fetchone()
        seasonal_temperature_windows = connection.execute(
            """
            WITH ordered AS (
                SELECT
                    sequence,
                    temperature_c,
                    ROW_NUMBER() OVER (ORDER BY measured_at, sequence) AS row_number
                FROM measurements
                WHERE device_id = 'sensor-demo-001'
            )
            SELECT
                AVG(CASE WHEN row_number BETWEEN 1 AND ? THEN temperature_c END),
                AVG(CASE WHEN row_number BETWEEN ? AND ? THEN temperature_c END),
                AVG(CASE WHEN row_number BETWEEN ? AND ? THEN temperature_c END),
                AVG(CASE WHEN row_number BETWEEN ? AND ? THEN temperature_c END)
            FROM ordered
            """,
            (
                HALF_YEAR_HOURS,
                HALF_YEAR_HOURS + 1,
                HALF_YEAR_HOURS * 2,
                HALF_YEAR_HOURS * 2 + 1,
                HALF_YEAR_HOURS * 3,
                HALF_YEAR_HOURS * 3 + 1,
                HALF_YEAR_HOURS * 4,
            ),
        ).fetchone()

    assert demo_device is not None
    assert demo_device[0] == "sensor-demo-001"
    assert demo_device[1] == "Demo sensor"
    assert demo_device[2] == "demo-sql-1.0"
    assert demo_device[3] == 1
    assert demo_device[4] == 1
    assert demo_device[5] == 3600
    assert demo_device[6] is not None
    assert demo_device[7] == -67
    assert demo_device[8] == 4.08
    assert demo_device[9] == 96

    assert measurement_stats is not None
    assert measurement_stats[0] == EXPECTED_MEASUREMENT_COUNT
    assert measurement_stats[1] == EXPECTED_MEASUREMENT_COUNT
    assert measurement_stats[2] == 1
    assert measurement_stats[3] == EXPECTED_MEASUREMENT_COUNT
    assert measurement_stats[5] - measurement_stats[4] == EXPECTED_TIMESTAMP_SPAN_SECONDS
    assert measurement_stats[6] == 1
    assert measurement_stats[7] == 1
    assert measurement_stats[8] < measurement_stats[9]
    assert measurement_stats[10] < measurement_stats[11]
    assert measurement_stats[12] < measurement_stats[13]
    assert demo_device[6] == measurement_stats[5]
    assert hourly_spacing == (3600, 3600)

    assert seasonal_temperature_windows is not None
    first_half_year_average = seasonal_temperature_windows[0]
    second_half_year_average = seasonal_temperature_windows[1]
    third_half_year_average = seasonal_temperature_windows[2]
    fourth_half_year_average = seasonal_temperature_windows[3]

    assert first_half_year_average is not None
    assert second_half_year_average is not None
    assert third_half_year_average is not None
    assert fourth_half_year_average is not None
    assert abs(first_half_year_average - second_half_year_average) > 1.0
    assert abs(second_half_year_average - third_half_year_average) > 1.0
    assert abs(third_half_year_average - fourth_half_year_average) > 1.0

    run_sql_script(database_path, CREATE_SCRIPT_PATH)

    with connect_database(database_path) as connection:
        rerun_measurement_stats = connection.execute(
            """
            SELECT
                COUNT(*),
                COUNT(DISTINCT sequence),
                MIN(sequence),
                MAX(sequence)
            FROM measurements
            WHERE device_id = 'sensor-demo-001'
            """
        ).fetchone()
        unrelated_before_cleanup = connection.execute(
            "SELECT COUNT(*) FROM devices WHERE device_id = 'sensor-real-001'"
        ).fetchone()[0]

    assert rerun_measurement_stats == (
        EXPECTED_MEASUREMENT_COUNT,
        EXPECTED_MEASUREMENT_COUNT,
        1,
        EXPECTED_MEASUREMENT_COUNT,
    )
    assert unrelated_before_cleanup == 1

    run_sql_script(database_path, DELETE_SCRIPT_PATH)

    with connect_database(database_path) as connection:
        remaining_demo_devices = connection.execute(
            "SELECT COUNT(*) FROM devices WHERE device_id = 'sensor-demo-001'"
        ).fetchone()[0]
        remaining_demo_measurements = connection.execute(
            "SELECT COUNT(*) FROM measurements WHERE device_id = 'sensor-demo-001'"
        ).fetchone()[0]
        surviving_real_devices = connection.execute(
            "SELECT COUNT(*) FROM devices WHERE device_id = 'sensor-real-001'"
        ).fetchone()[0]
        surviving_real_measurements = connection.execute(
            "SELECT COUNT(*) FROM measurements WHERE device_id = 'sensor-real-001'"
        ).fetchone()[0]

    assert remaining_demo_devices == 0
    assert remaining_demo_measurements == 0
    assert surviving_real_devices == 1
    assert surviving_real_measurements == 1

    run_sql_script(database_path, DELETE_SCRIPT_PATH)

    with connect_database(database_path) as connection:
        remaining_demo_devices_after_second_delete = connection.execute(
            "SELECT COUNT(*) FROM devices WHERE device_id = 'sensor-demo-001'"
        ).fetchone()[0]
        remaining_demo_measurements_after_second_delete = connection.execute(
            "SELECT COUNT(*) FROM measurements WHERE device_id = 'sensor-demo-001'"
        ).fetchone()[0]
        surviving_real_devices_after_second_delete = connection.execute(
            "SELECT COUNT(*) FROM devices WHERE device_id = 'sensor-real-001'"
        ).fetchone()[0]
        surviving_real_measurements_after_second_delete = connection.execute(
            "SELECT COUNT(*) FROM measurements WHERE device_id = 'sensor-real-001'"
        ).fetchone()[0]

    assert remaining_demo_devices_after_second_delete == 0
    assert remaining_demo_measurements_after_second_delete == 0
    assert surviving_real_devices_after_second_delete == 1
    assert surviving_real_measurements_after_second_delete == 1