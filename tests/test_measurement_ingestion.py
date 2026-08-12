from __future__ import annotations

import sqlite3
from pathlib import Path

from app.api_v1_models import MeasurementUploadRequest
from app.database import connect_database, initialize_database
from app.measurement_ingestion import ingest_measurement_upload


def make_request(
    *,
    device_id: str = "sensor-a",
    firmware_version: str = "0.1.0",
    config_version: int = 2,
    rssi_dbm: int = -61,
    battery_voltage: float | None = 3.92,
    battery_percent: int | None = 74,
    measurements: list[dict] | None = None,
) -> MeasurementUploadRequest:
    status: dict[str, object] = {"rssi_dbm": rssi_dbm}
    if battery_voltage is not None:
        status["battery_voltage"] = battery_voltage
    if battery_percent is not None:
        status["battery_percent"] = battery_percent

    payload = {
        "api_version": 1,
        "device_id": device_id,
        "firmware_version": firmware_version,
        "config_version": config_version,
        "status": status,
        "measurements": measurements
        or [
            {
                "sequence": 721,
                "measured_at": 1_786_300_052,
                "timestamp_valid": True,
                "temperature_c": 19.01,
                "humidity_percent": 53.49,
                "pressure_hpa": 990.79,
            },
            {
                "sequence": 722,
                "measured_at": 1_786_303_652,
                "timestamp_valid": True,
                "temperature_c": 18.94,
                "humidity_percent": 53.80,
                "pressure_hpa": 990.83,
            },
        ],
    }
    return MeasurementUploadRequest.model_validate(payload)


def test_first_upload_creates_device_and_measurements(
    tmp_path: Path, monkeypatch
) -> None:
    database_path = tmp_path / "environment.db"
    initialize_database(database_path)
    monkeypatch.setattr("app.measurement_ingestion.time.time", lambda: 1_786_303_653)

    result = ingest_measurement_upload(make_request(), database_path)

    assert result.acknowledged_through == 722
    assert result.server_time == 1_786_303_653
    assert result.config_version == 2

    with connect_database(database_path) as connection:
        device_row = connection.execute(
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
            WHERE device_id = ?
            """,
            ("sensor-a",),
        ).fetchone()
        measurement_rows = connection.execute(
            "SELECT sequence, measured_at FROM measurements WHERE device_id = ? ORDER BY sequence",
            ("sensor-a",),
        ).fetchall()

    assert device_row == (
        "sensor-a",
        None,
        "0.1.0",
        2,
        2,
        3600,
        1_786_303_653,
        -61,
        3.92,
        74,
    )
    assert measurement_rows == [(721, 1_786_300_052), (722, 1_786_303_652)]


def test_device_status_is_updated_on_later_upload(tmp_path: Path, monkeypatch) -> None:
    database_path = tmp_path / "environment.db"
    initialize_database(database_path)
    monkeypatch.setattr("app.measurement_ingestion.time.time", lambda: 1_786_303_653)
    ingest_measurement_upload(make_request(), database_path)
    monkeypatch.setattr("app.measurement_ingestion.time.time", lambda: 1_786_307_253)

    ingest_measurement_upload(
        make_request(
            firmware_version="0.2.0",
            config_version=3,
            rssi_dbm=-58,
            battery_voltage=3.87,
            battery_percent=68,
            measurements=[
                {
                    "sequence": 723,
                    "measured_at": 1_786_307_252,
                    "timestamp_valid": True,
                    "temperature_c": 18.71,
                    "humidity_percent": 54.12,
                    "pressure_hpa": 990.25,
                }
            ],
        ),
        database_path,
    )

    with connect_database(database_path) as connection:
        device_row = connection.execute(
            """
            SELECT
                firmware_version,
                config_version,
                reported_config_version,
                last_seen_at,
                rssi_dbm,
                battery_voltage,
                battery_percent
            FROM devices
            WHERE device_id = ?
            """,
            ("sensor-a",),
        ).fetchone()

    assert device_row == ("0.2.0", 2, 3, 1_786_307_253, -58, 3.87, 68)


def test_existing_device_keeps_server_owned_config_version(
    tmp_path: Path, monkeypatch
) -> None:
    database_path = tmp_path / "environment.db"
    initialize_database(database_path)
    monkeypatch.setattr("app.measurement_ingestion.time.time", lambda: 1_786_303_653)

    first_result = ingest_measurement_upload(
        make_request(config_version=2),
        database_path,
    )

    with connect_database(database_path) as connection:
        connection.execute(
            "UPDATE devices SET config_version = ? WHERE device_id = ?",
            (3, "sensor-a"),
        )

    monkeypatch.setattr("app.measurement_ingestion.time.time", lambda: 1_786_307_253)
    second_result = ingest_measurement_upload(
        make_request(
            config_version=2,
            firmware_version="0.2.0",
            measurements=[
                {
                    "sequence": 723,
                    "measured_at": 1_786_307_252,
                    "timestamp_valid": True,
                    "temperature_c": 18.71,
                    "humidity_percent": 54.12,
                    "pressure_hpa": 990.25,
                }
            ],
        ),
        database_path,
    )

    with connect_database(database_path) as connection:
        config_versions = connection.execute(
            "SELECT config_version, reported_config_version FROM devices WHERE device_id = ?",
            ("sensor-a",),
        ).fetchone()

    assert first_result.config_version == 2
    assert config_versions == (3, 2)
    assert second_result.config_version == 3


def test_reported_config_version_catches_up_after_device_applies_new_config(
    tmp_path: Path, monkeypatch
) -> None:
    database_path = tmp_path / "environment.db"
    initialize_database(database_path)
    monkeypatch.setattr("app.measurement_ingestion.time.time", lambda: 1_786_303_653)

    ingest_measurement_upload(make_request(config_version=3), database_path)

    with connect_database(database_path) as connection:
        connection.execute(
            "UPDATE devices SET config_version = ? WHERE device_id = ?",
            (4, "sensor-a"),
        )

    monkeypatch.setattr("app.measurement_ingestion.time.time", lambda: 1_786_307_253)
    stale_result = ingest_measurement_upload(
        make_request(
            config_version=3,
            measurements=[
                {
                    "sequence": 723,
                    "measured_at": 1_786_307_252,
                    "timestamp_valid": True,
                    "temperature_c": 18.71,
                    "humidity_percent": 54.12,
                    "pressure_hpa": 990.25,
                }
            ],
        ),
        database_path,
    )

    monkeypatch.setattr("app.measurement_ingestion.time.time", lambda: 1_786_310_853)
    updated_result = ingest_measurement_upload(
        make_request(
            config_version=4,
            measurements=[
                {
                    "sequence": 724,
                    "measured_at": 1_786_310_852,
                    "timestamp_valid": True,
                    "temperature_c": 18.52,
                    "humidity_percent": 54.33,
                    "pressure_hpa": 990.11,
                }
            ],
        ),
        database_path,
    )

    with connect_database(database_path) as connection:
        config_versions = connection.execute(
            "SELECT config_version, reported_config_version FROM devices WHERE device_id = ?",
            ("sensor-a",),
        ).fetchone()

    assert stale_result.config_version == 4
    assert updated_result.config_version == 4
    assert config_versions == (4, 4)


def test_server_managed_device_fields_are_not_overwritten(tmp_path: Path, monkeypatch) -> None:
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
                measurement_interval_seconds
            )
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            ("sensor-a", "Outdoor sensor", "0.0.1", 1, 1, 1800),
        )
    monkeypatch.setattr("app.measurement_ingestion.time.time", lambda: 1_786_303_653)

    ingest_measurement_upload(make_request(), database_path)

    with connect_database(database_path) as connection:
        device_row = connection.execute(
            "SELECT device_name, measurement_interval_seconds FROM devices WHERE device_id = ?",
            ("sensor-a",),
        ).fetchone()

    assert device_row == ("Outdoor sensor", 1800)


def test_repeated_identical_upload_creates_no_duplicates(tmp_path: Path, monkeypatch) -> None:
    database_path = tmp_path / "environment.db"
    initialize_database(database_path)
    monkeypatch.setattr("app.measurement_ingestion.time.time", lambda: 1_786_303_653)
    request = make_request()

    first_result = ingest_measurement_upload(request, database_path)
    second_result = ingest_measurement_upload(request, database_path)

    with connect_database(database_path) as connection:
        measurement_count = connection.execute(
            "SELECT COUNT(*) FROM measurements WHERE device_id = ?",
            ("sensor-a",),
        ).fetchone()[0]

    assert first_result.acknowledged_through == 722
    assert second_result.acknowledged_through == 722
    assert measurement_count == 2


def test_duplicate_sequence_does_not_overwrite_original_measurement(
    tmp_path: Path, monkeypatch
) -> None:
    database_path = tmp_path / "environment.db"
    initialize_database(database_path)
    monkeypatch.setattr("app.measurement_ingestion.time.time", lambda: 1_786_303_653)
    ingest_measurement_upload(
        make_request(
            measurements=[
                {
                    "sequence": 721,
                    "measured_at": 1_786_300_052,
                    "timestamp_valid": True,
                    "temperature_c": 19.01,
                    "humidity_percent": 53.49,
                    "pressure_hpa": 990.79,
                }
            ]
        ),
        database_path,
    )

    ingest_measurement_upload(
        make_request(
            measurements=[
                {
                    "sequence": 721,
                    "measured_at": 1_786_399_999,
                    "timestamp_valid": False,
                    "temperature_c": -5.0,
                    "humidity_percent": 10.0,
                    "pressure_hpa": 800.0,
                }
            ]
        ),
        database_path,
    )

    with connect_database(database_path) as connection:
        measurement_row = connection.execute(
            """
            SELECT measured_at, timestamp_valid, temperature_c, humidity_percent, pressure_hpa
            FROM measurements
            WHERE device_id = ? AND sequence = ?
            """,
            ("sensor-a", 721),
        ).fetchone()

    assert measurement_row == (1_786_300_052, 1, 19.01, 53.49, 990.79)


def test_unsorted_measurements_are_acknowledged_contiguously(
    tmp_path: Path, monkeypatch
) -> None:
    database_path = tmp_path / "environment.db"
    initialize_database(database_path)
    monkeypatch.setattr("app.measurement_ingestion.time.time", lambda: 1_786_303_653)

    result = ingest_measurement_upload(
        make_request(
            measurements=[
                {
                    "sequence": 723,
                    "measured_at": 1_786_307_252,
                    "timestamp_valid": True,
                    "temperature_c": 18.71,
                    "humidity_percent": 54.12,
                    "pressure_hpa": 990.25,
                },
                {
                    "sequence": 721,
                    "measured_at": 1_786_300_052,
                    "timestamp_valid": True,
                    "temperature_c": 19.01,
                    "humidity_percent": 53.49,
                    "pressure_hpa": 990.79,
                },
                {
                    "sequence": 722,
                    "measured_at": 1_786_303_652,
                    "timestamp_valid": True,
                    "temperature_c": 18.94,
                    "humidity_percent": 53.80,
                    "pressure_hpa": 990.83,
                },
            ]
        ),
        database_path,
    )

    assert result.acknowledged_through == 723


def test_sequence_gap_does_not_acknowledge_across_gap(tmp_path: Path, monkeypatch) -> None:
    database_path = tmp_path / "environment.db"
    initialize_database(database_path)
    monkeypatch.setattr("app.measurement_ingestion.time.time", lambda: 1_786_303_653)

    result = ingest_measurement_upload(
        make_request(
            measurements=[
                {
                    "sequence": 721,
                    "measured_at": 1_786_300_052,
                    "timestamp_valid": True,
                    "temperature_c": 19.01,
                    "humidity_percent": 53.49,
                    "pressure_hpa": 990.79,
                },
                {
                    "sequence": 723,
                    "measured_at": 1_786_307_252,
                    "timestamp_valid": True,
                    "temperature_c": 18.71,
                    "humidity_percent": 54.12,
                    "pressure_hpa": 990.25,
                },
            ]
        ),
        database_path,
    )

    assert result.acknowledged_through == 721


def test_same_sequence_numbers_for_different_devices_are_independent(
    tmp_path: Path, monkeypatch
) -> None:
    database_path = tmp_path / "environment.db"
    initialize_database(database_path)
    monkeypatch.setattr("app.measurement_ingestion.time.time", lambda: 1_786_303_653)

    ingest_measurement_upload(make_request(device_id="sensor-a"), database_path)
    ingest_measurement_upload(make_request(device_id="sensor-b"), database_path)

    with connect_database(database_path) as connection:
        sequence_count = connection.execute(
            "SELECT COUNT(*) FROM measurements WHERE sequence = ?",
            (721,),
        ).fetchone()[0]

    assert sequence_count == 2


def test_battery_fields_may_be_absent(tmp_path: Path, monkeypatch) -> None:
    database_path = tmp_path / "environment.db"
    initialize_database(database_path)
    monkeypatch.setattr("app.measurement_ingestion.time.time", lambda: 1_786_303_653)

    ingest_measurement_upload(
        make_request(battery_voltage=None, battery_percent=None),
        database_path,
    )

    with connect_database(database_path) as connection:
        battery_row = connection.execute(
            "SELECT battery_voltage, battery_percent FROM devices WHERE device_id = ?",
            ("sensor-a",),
        ).fetchone()

    assert battery_row == (None, None)


def test_ingestion_is_atomic_on_non_duplicate_database_failure(
    tmp_path: Path, monkeypatch
) -> None:
    database_path = tmp_path / "environment.db"
    initialize_database(database_path)
    monkeypatch.setattr("app.measurement_ingestion.time.time", lambda: 1_786_303_653)

    with connect_database(database_path) as connection:
        connection.execute(
            """
            CREATE TRIGGER reject_sequence_722
            BEFORE INSERT ON measurements
            WHEN NEW.sequence = 722
            BEGIN
                SELECT RAISE(ABORT, 'sequence 722 rejected');
            END;
            """
        )

    try:
        ingest_measurement_upload(make_request(), database_path)
    except sqlite3.IntegrityError as error:
        assert str(error) == "sequence 722 rejected"
    else:
        raise AssertionError("expected ingestion to fail")

    with connect_database(database_path) as connection:
        device_count = connection.execute(
            "SELECT COUNT(*) FROM devices WHERE device_id = ?",
            ("sensor-a",),
        ).fetchone()[0]
        measurement_count = connection.execute(
            "SELECT COUNT(*) FROM measurements WHERE device_id = ?",
            ("sensor-a",),
        ).fetchone()[0]

    assert device_count == 0
    assert measurement_count == 0