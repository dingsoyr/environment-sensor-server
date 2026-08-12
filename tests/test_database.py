import sqlite3
from pathlib import Path

from app.database import connect_database, initialize_database, list_dashboard_sensors


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