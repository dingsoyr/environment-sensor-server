from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from app.database import connect_database
from app.main import create_app


def make_request_payload() -> dict:
    return {
        "api_version": 1,
        "device_id": "sensor-d8cbb0",
        "firmware_version": "0.1.0",
        "config_version": 2,
        "status": {
            "rssi_dbm": -61,
            "battery_voltage": 3.92,
            "battery_percent": 74,
        },
        "measurements": [
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


def create_client(database_path: Path, monkeypatch) -> TestClient:
    monkeypatch.setattr("app.measurement_ingestion.time.time", lambda: 1_786_303_653)
    app = create_app(database_path)
    return TestClient(app)


def test_valid_post_returns_response_and_persists_measurements(
    tmp_path: Path, monkeypatch
) -> None:
    database_path = tmp_path / "environment.db"

    with create_client(database_path, monkeypatch) as client:
        response = client.post("/api/v1/measurements", json=make_request_payload())

    assert response.status_code == 200
    assert response.json() == {
        "api_version": 1,
        "acknowledged_through": 722,
        "server_time": 1_786_303_653,
        "config_version": 2,
    }
    assert "configuration" not in response.json()

    with connect_database(database_path) as connection:
        measurement_rows = connection.execute(
            "SELECT sequence, measured_at FROM measurements WHERE device_id = ? ORDER BY sequence",
            ("sensor-d8cbb0",),
        ).fetchall()

    assert measurement_rows == [(721, 1_786_300_052), (722, 1_786_303_652)]


def test_response_uses_server_stored_config_version(tmp_path: Path, monkeypatch) -> None:
    database_path = tmp_path / "environment.db"

    with create_client(database_path, monkeypatch) as client:
        with connect_database(database_path) as connection:
            connection.execute(
                """
                INSERT INTO devices (device_id, config_version, reported_config_version)
                VALUES (?, ?, ?)
                """,
                ("sensor-d8cbb0", 5, 5),
            )

        response = client.post("/api/v1/measurements", json=make_request_payload())

    assert response.status_code == 200
    assert response.json()["config_version"] == 5
    assert "configuration" not in response.json()


def test_newer_server_config_with_device_name_returns_configuration(
    tmp_path: Path, monkeypatch
) -> None:
    database_path = tmp_path / "environment.db"

    with create_client(database_path, monkeypatch) as client:
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
                ("sensor-d8cbb0", "Outdoor sensor", 5, 2, 1800),
            )

        response = client.post("/api/v1/measurements", json=make_request_payload())

    assert response.status_code == 200
    assert response.json() == {
        "api_version": 1,
        "acknowledged_through": 722,
        "server_time": 1_786_303_653,
        "config_version": 5,
        "configuration": {
            "device_name": "Outdoor sensor",
            "measurement_interval_seconds": 1800,
        },
    }


def test_stale_device_report_keeps_server_config_and_updates_reported_version(
    tmp_path: Path, monkeypatch
) -> None:
    database_path = tmp_path / "environment.db"

    with create_client(database_path, monkeypatch) as client:
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
                ("sensor-d8cbb0", "Outdoor sensor", 4, 3, 1800),
            )

        payload = make_request_payload()
        payload["config_version"] = 3

        response = client.post("/api/v1/measurements", json=payload)

    assert response.status_code == 200
    assert response.json() == {
        "api_version": 1,
        "acknowledged_through": 722,
        "server_time": 1_786_303_653,
        "config_version": 4,
        "configuration": {
            "device_name": "Outdoor sensor",
            "measurement_interval_seconds": 1800,
        },
    }

    with connect_database(database_path) as connection:
        config_versions = connection.execute(
            "SELECT config_version, reported_config_version FROM devices WHERE device_id = ?",
            ("sensor-d8cbb0",),
        ).fetchone()

    assert config_versions == (4, 3)


def test_reported_config_version_updates_after_device_reports_newer_config(
    tmp_path: Path, monkeypatch
) -> None:
    database_path = tmp_path / "environment.db"

    with create_client(database_path, monkeypatch) as client:
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
                ("sensor-d8cbb0", "Outdoor sensor", 4, 3, 1800),
            )

        payload = make_request_payload()
        payload["config_version"] = 4

        response = client.post("/api/v1/measurements", json=payload)

    assert response.status_code == 200
    assert response.json() == {
        "api_version": 1,
        "acknowledged_through": 722,
        "server_time": 1_786_303_653,
        "config_version": 4,
    }

    with connect_database(database_path) as connection:
        config_versions = connection.execute(
            "SELECT config_version, reported_config_version FROM devices WHERE device_id = ?",
            ("sensor-d8cbb0",),
        ).fetchone()

    assert config_versions == (4, 4)


def test_repeated_identical_post_is_idempotent(tmp_path: Path, monkeypatch) -> None:
    database_path = tmp_path / "environment.db"
    payload = make_request_payload()

    with create_client(database_path, monkeypatch) as client:
        first_response = client.post("/api/v1/measurements", json=payload)
        second_response = client.post("/api/v1/measurements", json=payload)

    assert first_response.status_code == 200
    assert second_response.status_code == 200
    assert first_response.json()["acknowledged_through"] == 722
    assert second_response.json()["acknowledged_through"] == 722

    with connect_database(database_path) as connection:
        measurement_count = connection.execute(
            "SELECT COUNT(*) FROM measurements WHERE device_id = ?",
            ("sensor-d8cbb0",),
        ).fetchone()[0]

    assert measurement_count == 2


def test_request_without_battery_fields_succeeds(tmp_path: Path, monkeypatch) -> None:
    database_path = tmp_path / "environment.db"
    payload = make_request_payload()
    payload["status"] = {"rssi_dbm": -61}

    with create_client(database_path, monkeypatch) as client:
        response = client.post("/api/v1/measurements", json=payload)

    assert response.status_code == 200

    with connect_database(database_path) as connection:
        battery_row = connection.execute(
            "SELECT battery_voltage, battery_percent FROM devices WHERE device_id = ?",
            ("sensor-d8cbb0",),
        ).fetchone()

    assert battery_row == (None, None)


def test_invalid_api_version_is_rejected(tmp_path: Path, monkeypatch) -> None:
    database_path = tmp_path / "environment.db"
    payload = make_request_payload()
    payload["api_version"] = 2

    with create_client(database_path, monkeypatch) as client:
        response = client.post("/api/v1/measurements", json=payload)

    assert response.status_code == 422


def test_empty_measurements_is_rejected(tmp_path: Path, monkeypatch) -> None:
    database_path = tmp_path / "environment.db"
    payload = make_request_payload()
    payload["measurements"] = []

    with create_client(database_path, monkeypatch) as client:
        response = client.post("/api/v1/measurements", json=payload)

    assert response.status_code == 422


def test_database_failure_returns_non_success_and_no_acknowledgement(
    tmp_path: Path, monkeypatch
) -> None:
    database_path = tmp_path / "environment.db"

    with create_client(database_path, monkeypatch) as client:
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

        response = client.post("/api/v1/measurements", json=make_request_payload())

    assert response.status_code == 500
    assert response.json() == {"detail": "Internal Server Error"}

    with connect_database(database_path) as connection:
        device_count = connection.execute(
            "SELECT COUNT(*) FROM devices WHERE device_id = ?",
            ("sensor-d8cbb0",),
        ).fetchone()[0]
        measurement_count = connection.execute(
            "SELECT COUNT(*) FROM measurements WHERE device_id = ?",
            ("sensor-d8cbb0",),
        ).fetchone()[0]

    assert device_count == 0
    assert measurement_count == 0