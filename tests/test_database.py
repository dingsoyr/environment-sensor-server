import sqlite3
from pathlib import Path

from app.database import connect_database, initialize_database


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

    assert "devices" in table_names
    assert "measurements" in table_names


def test_initialize_database_is_idempotent(tmp_path: Path) -> None:
    database_path = tmp_path / "environment.db"

    initialize_database(database_path)
    initialize_database(database_path)

    with connect_database(database_path) as connection:
        table_count = connection.execute(
            "SELECT COUNT(*) FROM sqlite_master WHERE type = 'table' AND name IN ('devices', 'measurements')"
        ).fetchone()[0]

    assert table_count == 2


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