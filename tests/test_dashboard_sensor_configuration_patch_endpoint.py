from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.database import connect_database
from app.main import create_app


def create_client(
    database_path: Path,
    monkeypatch=None,
    *,
    server_time: int | None = None,
) -> TestClient:
    if monkeypatch is not None and server_time is not None:
        monkeypatch.setattr("app.measurement_ingestion.time.time", lambda: server_time)

    app = create_app(database_path)
    return TestClient(app)


def insert_device(
    database_path: Path,
    *,
    device_id: str,
    device_name: str | None,
    firmware_version: str | None = "0.1.0-dev",
    config_version: int = 3,
    reported_config_version: int = 3,
    measurement_interval_seconds: int = 3600,
    last_seen_at: int | None = 1_786_484_296,
    rssi_dbm: int | None = -83,
    battery_voltage: float | None = None,
    battery_percent: int | None = None,
) -> None:
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
            (
                device_id,
                device_name,
                firmware_version,
                config_version,
                reported_config_version,
                measurement_interval_seconds,
                last_seen_at,
                rssi_dbm,
                battery_voltage,
                battery_percent,
            ),
        )


def insert_measurement(
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


def make_measurement_upload_payload(*, config_version: int) -> dict:
    return {
        "api_version": 1,
        "device_id": "sensor-d8cbb0",
        "firmware_version": "0.1.0",
        "config_version": config_version,
        "status": {
            "rssi_dbm": -61,
        },
        "measurements": [
            {
                "sequence": 721,
                "measured_at": 1_786_300_052,
                "timestamp_valid": True,
                "temperature_c": 19.01,
                "humidity_percent": 53.49,
                "pressure_hpa": 990.79,
                "battery_voltage": 3.92,
                "battery_percent": 74,
            }
        ],
    }


def test_patch_configuration_updates_device_name_independently(tmp_path: Path) -> None:
    database_path = tmp_path / "environment.db"

    with create_client(database_path) as client:
        insert_device(
            database_path,
            device_id="sensor-d8cbb0",
            device_name="Outdoor sensor",
            config_version=3,
            reported_config_version=3,
            measurement_interval_seconds=3600,
        )

        response = client.patch(
            "/api/dashboard/sensors/sensor-d8cbb0/configuration",
            json={"device_name": "Utesensor nord"},
        )

    assert response.status_code == 200
    assert response.json() == {
        "device_id": "sensor-d8cbb0",
        "device_name": "Utesensor nord",
        "measurement_interval_seconds": 3600,
        "config_version": 4,
        "reported_config_version": 3,
        "config_sync_state": "waiting_for_sensor",
    }


def test_patch_configuration_updates_measurement_interval_independently(
    tmp_path: Path,
) -> None:
    database_path = tmp_path / "environment.db"

    with create_client(database_path) as client:
        insert_device(
            database_path,
            device_id="sensor-d8cbb0",
            device_name="Outdoor sensor",
            config_version=3,
            reported_config_version=3,
            measurement_interval_seconds=3600,
        )

        response = client.patch(
            "/api/dashboard/sensors/sensor-d8cbb0/configuration",
            json={"measurement_interval_seconds": 1800},
        )

    assert response.status_code == 200
    assert response.json() == {
        "device_id": "sensor-d8cbb0",
        "device_name": "Outdoor sensor",
        "measurement_interval_seconds": 1800,
        "config_version": 4,
        "reported_config_version": 3,
        "config_sync_state": "waiting_for_sensor",
    }


def test_patch_configuration_updates_both_fields_atomically(tmp_path: Path) -> None:
    database_path = tmp_path / "environment.db"

    with create_client(database_path) as client:
        insert_device(
            database_path,
            device_id="sensor-d8cbb0",
            device_name="Outdoor sensor",
            config_version=3,
            reported_config_version=3,
            measurement_interval_seconds=3600,
        )

        response = client.patch(
            "/api/dashboard/sensors/sensor-d8cbb0/configuration",
            json={
                "device_name": "Utesensor nord",
                "measurement_interval_seconds": 1800,
            },
        )

    assert response.status_code == 200
    assert response.json() == {
        "device_id": "sensor-d8cbb0",
        "device_name": "Utesensor nord",
        "measurement_interval_seconds": 1800,
        "config_version": 4,
        "reported_config_version": 3,
        "config_sync_state": "waiting_for_sensor",
    }

    with connect_database(database_path) as connection:
        stored_row = connection.execute(
            """
            SELECT device_name, measurement_interval_seconds, config_version, reported_config_version
            FROM devices
            WHERE device_id = ?
            """,
            ("sensor-d8cbb0",),
        ).fetchone()

    assert stored_row == ("Utesensor nord", 1800, 4, 3)


def test_patch_configuration_no_op_keeps_config_version_unchanged(tmp_path: Path) -> None:
    database_path = tmp_path / "environment.db"

    with create_client(database_path) as client:
        insert_device(
            database_path,
            device_id="sensor-d8cbb0",
            device_name="Outdoor sensor",
            config_version=3,
            reported_config_version=3,
            measurement_interval_seconds=3600,
        )

        response = client.patch(
            "/api/dashboard/sensors/sensor-d8cbb0/configuration",
            json={
                "device_name": "  Outdoor sensor  ",
                "measurement_interval_seconds": 3600,
            },
        )

    assert response.status_code == 200
    assert response.json() == {
        "device_id": "sensor-d8cbb0",
        "device_name": "Outdoor sensor",
        "measurement_interval_seconds": 3600,
        "config_version": 3,
        "reported_config_version": 3,
        "config_sync_state": "synced",
    }


def test_patch_configuration_preserves_reported_version_when_device_is_ahead(
    tmp_path: Path,
) -> None:
    database_path = tmp_path / "environment.db"

    with create_client(database_path) as client:
        insert_device(
            database_path,
            device_id="sensor-d8cbb0",
            device_name="Outdoor sensor",
            config_version=3,
            reported_config_version=6,
            measurement_interval_seconds=3600,
        )

        response = client.patch(
            "/api/dashboard/sensors/sensor-d8cbb0/configuration",
            json={"measurement_interval_seconds": 1800},
        )

    assert response.status_code == 200
    assert response.json() == {
        "device_id": "sensor-d8cbb0",
        "device_name": "Outdoor sensor",
        "measurement_interval_seconds": 1800,
        "config_version": 4,
        "reported_config_version": 6,
        "config_sync_state": "device_ahead",
    }


@pytest.mark.parametrize(
    "payload",
    [
        {"device_name": "   "},
        {"measurement_interval_seconds": 0},
        {"measurement_interval_seconds": -1},
        {"device_name": None},
        {"measurement_interval_seconds": None},
        {},
    ],
)
def test_patch_configuration_rejects_invalid_payloads(
    tmp_path: Path,
    payload: dict,
) -> None:
    database_path = tmp_path / "environment.db"

    with create_client(database_path) as client:
        insert_device(
            database_path,
            device_id="sensor-d8cbb0",
            device_name="Outdoor sensor",
        )
        response = client.patch(
            "/api/dashboard/sensors/sensor-d8cbb0/configuration",
            json=payload,
        )

    assert response.status_code == 422


def test_patch_configuration_returns_not_found_for_unknown_device(tmp_path: Path) -> None:
    database_path = tmp_path / "environment.db"

    with create_client(database_path) as client:
        response = client.patch(
            "/api/dashboard/sensors/missing-device/configuration",
            json={"device_name": "Outdoor sensor"},
        )

    assert response.status_code == 404
    assert response.json() == {"detail": "Not Found"}


def test_dashboard_get_endpoints_remain_unchanged_after_patch(tmp_path: Path) -> None:
    database_path = tmp_path / "environment.db"

    with create_client(database_path) as client:
        insert_device(
            database_path,
            device_id="sensor-d8cbb0",
            device_name="Outdoor sensor",
            config_version=3,
            reported_config_version=3,
            measurement_interval_seconds=3600,
        )
        insert_measurement(
            database_path,
            device_id="sensor-d8cbb0",
            sequence=1301,
            measured_at=1_786_484_295,
            timestamp_valid=True,
            temperature_c=21.78,
            humidity_percent=45.73,
            pressure_hpa=1013.1,
        )

        patch_response = client.patch(
            "/api/dashboard/sensors/sensor-d8cbb0/configuration",
            json={"measurement_interval_seconds": 1800},
        )
        detail_response = client.get("/api/dashboard/sensors/sensor-d8cbb0")
        list_response = client.get("/api/dashboard/sensors")

    assert patch_response.status_code == 200
    assert detail_response.status_code == 200
    assert list_response.status_code == 200
    assert detail_response.json() == {
        "device_id": "sensor-d8cbb0",
        "device_name": "Outdoor sensor",
        "firmware_version": "0.1.0-dev",
        "last_seen_at": 1_786_484_296,
        "contact_state": "delayed",
        "rssi_dbm": -83,
        "battery_voltage": None,
        "battery_percent": None,
        "configuration": {
            "measurement_interval_seconds": 1800,
            "config_version": 4,
            "reported_config_version": 3,
            "config_sync_state": "waiting_for_sensor",
        },
        "latest_measurement": {
            "sequence": 1301,
            "measured_at": 1_786_484_295,
            "timestamp_valid": True,
            "temperature_c": 21.78,
            "humidity_percent": 45.73,
            "pressure_hpa": 1013.1,
        },
    }
    assert list_response.json() == {
        "sensors": [
            {
                "device_id": "sensor-d8cbb0",
                "device_name": "Outdoor sensor",
                "firmware_version": "0.1.0-dev",
                "last_seen_at": 1_786_484_296,
                "contact_state": "delayed",
                "rssi_dbm": -83,
                "battery_voltage": None,
                "battery_percent": None,
                "measurement_interval_seconds": 1800,
                "config_version": 4,
                "reported_config_version": 3,
                "config_sync_state": "waiting_for_sensor",
                "latest_measurement": {
                    "sequence": 1301,
                    "measured_at": 1_786_484_295,
                    "timestamp_valid": True,
                    "temperature_c": 21.78,
                    "humidity_percent": 45.73,
                    "pressure_hpa": 1013.1,
                },
            }
        ]
    }


def test_patch_configuration_syncs_through_existing_api_v1_delivery(
    tmp_path: Path,
    monkeypatch,
) -> None:
    database_path = tmp_path / "environment.db"

    with create_client(database_path, monkeypatch, server_time=1_786_303_653) as client:
        insert_device(
            database_path,
            device_id="sensor-d8cbb0",
            device_name="Outdoor sensor",
            firmware_version="0.1.0-dev",
            config_version=3,
            reported_config_version=3,
            measurement_interval_seconds=3600,
        )

        patch_response = client.patch(
            "/api/dashboard/sensors/sensor-d8cbb0/configuration",
            json={
                "device_name": "Utesensor nord",
                "measurement_interval_seconds": 1800,
            },
        )
        first_upload_response = client.post(
            "/api/v1/measurements",
            json=make_measurement_upload_payload(config_version=3),
        )

        second_payload = make_measurement_upload_payload(config_version=4)
        second_payload["measurements"][0]["sequence"] = 722
        second_payload["measurements"][0]["measured_at"] = 1_786_303_652

        second_upload_response = client.post(
            "/api/v1/measurements",
            json=second_payload,
        )
        detail_response = client.get("/api/dashboard/sensors/sensor-d8cbb0")

    assert patch_response.status_code == 200
    assert patch_response.json() == {
        "device_id": "sensor-d8cbb0",
        "device_name": "Utesensor nord",
        "measurement_interval_seconds": 1800,
        "config_version": 4,
        "reported_config_version": 3,
        "config_sync_state": "waiting_for_sensor",
    }
    assert first_upload_response.status_code == 200
    assert first_upload_response.json() == {
        "api_version": 1,
        "acknowledged_through": 721,
        "server_time": 1_786_303_653,
        "config_version": 4,
        "configuration": {
            "device_name": "Utesensor nord",
            "measurement_interval_seconds": 1800,
        },
    }
    assert second_upload_response.status_code == 200
    assert second_upload_response.json() == {
        "api_version": 1,
        "acknowledged_through": 722,
        "server_time": 1_786_303_653,
        "config_version": 4,
    }
    assert detail_response.status_code == 200
    assert detail_response.json()["configuration"] == {
        "measurement_interval_seconds": 1800,
        "config_version": 4,
        "reported_config_version": 4,
        "config_sync_state": "synced",
    }

    with connect_database(database_path) as connection:
        stored_row = connection.execute(
            """
            SELECT device_name, measurement_interval_seconds, config_version, reported_config_version
            FROM devices
            WHERE device_id = ?
            """,
            ("sensor-d8cbb0",),
        ).fetchone()

    assert stored_row == ("Utesensor nord", 1800, 4, 4)