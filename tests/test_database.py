import sqlite3
from dataclasses import asdict
from pathlib import Path

from app.database import (
    connect_database,
    initialize_database,
    list_dashboard_sensor_history_by_day,
    list_dashboard_sensors,
)


UTC_DAY_SECONDS = 24 * 60 * 60


def insert_device(database_path: Path, device_id: str) -> None:
    with connect_database(database_path) as connection:
        connection.execute(
            "INSERT INTO devices (device_id) VALUES (?)",
            (device_id,),
        )


def insert_measurement(database_path: Path, device_id: str, sequence: int) -> None:
    with connect_database(database_path) as connection:
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
            (device_id, sequence, 1_786_300_052, 1, 19.01, 53.49, 990.79),
        )


def insert_history_measurement(
    database_path: Path,
    *,
    device_id: str,
    sequence: int,
    measured_at: int,
    timestamp_valid: bool,
    temperature_c: float,
    humidity_percent: float,
    pressure_hpa: float,
) -> None:
    with connect_database(database_path) as connection:
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
            (
                device_id,
                sequence,
                measured_at,
                int(timestamp_valid),
                temperature_c,
                humidity_percent,
                pressure_hpa,
            ),
        )


def test_initialize_database_creates_schema(tmp_path: Path) -> None:
    database_path = tmp_path / "environment.db"

    initialize_database(database_path)

    with connect_database(database_path) as connection:
        table_names = {
            row[0]
            for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table'"
            )
        }
        device_columns = {
            row[1]: row[4]
            for row in connection.execute("PRAGMA table_info(devices)")
        }

    assert "devices" in table_names
    assert "measurements" in table_names
    assert "config_version" in device_columns
    assert "reported_config_version" in device_columns
    assert device_columns["reported_config_version"] == "0"


def test_initialize_database_is_idempotent(tmp_path: Path) -> None:
    database_path = tmp_path / "environment.db"

    initialize_database(database_path)
    initialize_database(database_path)

    with connect_database(database_path) as connection:
        table_count = connection.execute(
            "SELECT COUNT(*) FROM sqlite_master WHERE type = 'table' AND name IN ('devices', 'measurements')"
        ).fetchone()[0]

    assert table_count == 2


def test_initialize_database_creates_history_lookup_index(tmp_path: Path) -> None:
    database_path = tmp_path / "environment.db"

    initialize_database(database_path)

    with connect_database(database_path) as connection:
        indexes = {
            row[1]: row[2]
            for row in connection.execute("PRAGMA index_list(measurements)")
        }
        indexed_columns = [
            row[2]
            for row in connection.execute(
                "PRAGMA index_info(idx_measurements_device_measured_at)"
            )
        ]

    assert indexes["idx_measurements_device_measured_at"] == 0
    assert indexed_columns == ["device_id", "measured_at"]


def test_measurements_are_unique_per_device_and_sequence(tmp_path: Path) -> None:
    database_path = tmp_path / "environment.db"
    initialize_database(database_path)
    insert_device(database_path, "sensor-a")

    insert_measurement(database_path, "sensor-a", 721)

    with connect_database(database_path) as connection:
        try:
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
                ("sensor-a", 721, 1_786_303_652, 1, 18.94, 53.80, 990.83),
            )
        except sqlite3.IntegrityError:
            pass
        else:
            raise AssertionError("expected duplicate device measurement insert to fail")


def test_sequence_number_may_repeat_for_different_devices(tmp_path: Path) -> None:
    database_path = tmp_path / "environment.db"
    initialize_database(database_path)
    insert_device(database_path, "sensor-a")
    insert_device(database_path, "sensor-b")

    insert_measurement(database_path, "sensor-a", 721)
    insert_measurement(database_path, "sensor-b", 721)

    with connect_database(database_path) as connection:
        measurement_count = connection.execute(
            "SELECT COUNT(*) FROM measurements WHERE sequence = 721"
        ).fetchone()[0]

    assert measurement_count == 2


def test_measurement_requires_existing_device(tmp_path: Path) -> None:
    database_path = tmp_path / "environment.db"
    initialize_database(database_path)

    with connect_database(database_path) as connection:
        try:
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
                ("missing-device", 721, 1_786_300_052, 1, 19.01, 53.49, 990.79),
            )
        except sqlite3.IntegrityError:
            pass
        else:
            raise AssertionError("expected missing device insert to fail")


def test_reported_config_version_must_not_be_negative(tmp_path: Path) -> None:
    database_path = tmp_path / "environment.db"
    initialize_database(database_path)

    with connect_database(database_path) as connection:
        try:
            connection.execute(
                """
                INSERT INTO devices (device_id, reported_config_version)
                VALUES (?, ?)
                """,
                ("sensor-a", -1),
            )
        except sqlite3.IntegrityError:
            pass
        else:
            raise AssertionError("expected negative reported_config_version insert to fail")


def test_list_dashboard_sensors_returns_latest_measurement_by_highest_sequence(
    tmp_path: Path,
) -> None:
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
            ("sensor-a", "Alpha", "0.1.0", 3, 3, 3600, 123, -70, None, None),
        )
        connection.executemany(
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
            [
                ("sensor-a", 10, 1_000, 1, 21.5, 45.0, 1013.1),
                ("sensor-a", 11, 900, 0, 19.25, 55.0, 1012.8),
            ],
        )

    sensors = list_dashboard_sensors(database_path)

    assert len(sensors) == 1
    assert sensors[0].config_sync_state == "synced"
    assert sensors[0].latest_measurement is not None
    assert sensors[0].latest_measurement.sequence == 11
    assert sensors[0].latest_measurement.measured_at == 900
    assert sensors[0].latest_measurement.timestamp_valid is False


def test_list_dashboard_sensors_returns_null_latest_measurement_for_device_without_history(
    tmp_path: Path,
) -> None:
    database_path = tmp_path / "environment.db"
    initialize_database(database_path)

    with connect_database(database_path) as connection:
        connection.execute(
            """
            INSERT INTO devices (
                device_id,
                device_name,
                config_version,
                reported_config_version,
                measurement_interval_seconds
            )
            VALUES (?, ?, ?, ?, ?)
            """,
            ("sensor-a", "Alpha", 2, 1, 1800),
        )

    sensors = list_dashboard_sensors(database_path)

    assert len(sensors) == 1
    assert sensors[0].config_sync_state == "waiting_for_sensor"
    assert sensors[0].latest_measurement is None


def test_list_dashboard_sensor_history_by_day_aggregates_by_utc_day_and_respects_half_open_range(
    tmp_path: Path,
) -> None:
    database_path = tmp_path / "environment.db"
    initialize_database(database_path)
    insert_device(database_path, "sensor-a")

    day_zero = 1_704_067_200
    history_from = day_zero + (12 * 60 * 60)
    history_to = day_zero + (31 * UTC_DAY_SECONDS) + 1

    insert_history_measurement(
        database_path,
        device_id="sensor-a",
        sequence=1,
        measured_at=day_zero + (11 * 60 * 60),
        timestamp_valid=True,
        temperature_c=1.0,
        humidity_percent=10.0,
        pressure_hpa=1000.0,
    )
    insert_history_measurement(
        database_path,
        device_id="sensor-a",
        sequence=2,
        measured_at=history_from,
        timestamp_valid=True,
        temperature_c=10.0,
        humidity_percent=20.0,
        pressure_hpa=1001.0,
    )
    insert_history_measurement(
        database_path,
        device_id="sensor-a",
        sequence=3,
        measured_at=day_zero + (2 * UTC_DAY_SECONDS) + (1 * 60 * 60),
        timestamp_valid=False,
        temperature_c=30.0,
        humidity_percent=40.0,
        pressure_hpa=1003.0,
    )
    insert_history_measurement(
        database_path,
        device_id="sensor-a",
        sequence=4,
        measured_at=day_zero + (2 * UTC_DAY_SECONDS) + (23 * 60 * 60),
        timestamp_valid=True,
        temperature_c=50.0,
        humidity_percent=60.0,
        pressure_hpa=1005.0,
    )
    insert_history_measurement(
        database_path,
        device_id="sensor-a",
        sequence=5,
        measured_at=history_to,
        timestamp_valid=True,
        temperature_c=99.0,
        humidity_percent=99.0,
        pressure_hpa=1099.0,
    )

    points = list_dashboard_sensor_history_by_day(
        "sensor-a",
        measured_from=history_from,
        measured_to=history_to,
        database_path=database_path,
    )

    assert [asdict(point) for point in points] == [
        {
            "period_start": day_zero,
            "sample_count": 1,
            "temperature_min_c": 10.0,
            "temperature_avg_c": 10.0,
            "temperature_max_c": 10.0,
            "humidity_min_percent": 20.0,
            "humidity_avg_percent": 20.0,
            "humidity_max_percent": 20.0,
            "pressure_min_hpa": 1001.0,
            "pressure_avg_hpa": 1001.0,
            "pressure_max_hpa": 1001.0,
        },
        {
            "period_start": day_zero + (2 * UTC_DAY_SECONDS),
            "sample_count": 2,
            "temperature_min_c": 30.0,
            "temperature_avg_c": 40.0,
            "temperature_max_c": 50.0,
            "humidity_min_percent": 40.0,
            "humidity_avg_percent": 50.0,
            "humidity_max_percent": 60.0,
            "pressure_min_hpa": 1003.0,
            "pressure_avg_hpa": 1004.0,
            "pressure_max_hpa": 1005.0,
        },
    ]