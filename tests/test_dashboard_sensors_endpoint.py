from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from app.database import connect_database
from app.main import create_app


def create_client(database_path: Path) -> TestClient:
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
    rssi_dbm: int | None = -77,
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


def test_dashboard_sensors_empty_database_returns_empty_array(tmp_path: Path) -> None:
    database_path = tmp_path / "environment.db"

    with create_client(database_path) as client:
        response = client.get("/api/dashboard/sensors")

    assert response.status_code == 200
    assert response.json() == {"sensors": []}


def test_dashboard_sensors_returns_sensor_fields_with_synced_state(
    tmp_path: Path,
) -> None:
    database_path = tmp_path / "environment.db"

    with create_client(database_path) as client:
        insert_device(
            database_path,
            device_id="sensor-d8cbb0",
            device_name="Utesensor nord",
            firmware_version="0.1.0-dev",
            config_version=3,
            reported_config_version=3,
            measurement_interval_seconds=3600,
            last_seen_at=1_786_484_296,
            rssi_dbm=-77,
            battery_voltage=None,
            battery_percent=None,
        )
        insert_measurement(
            database_path,
            device_id="sensor-d8cbb0",
            sequence=1301,
            measured_at=1_786_484_295,
            timestamp_valid=True,
            temperature_c=21.78,
            humidity_percent=45.73,
            pressure_hpa=1013.10,
        )

        response = client.get("/api/dashboard/sensors")

    assert response.status_code == 200
    assert response.json() == {
        "sensors": [
            {
                "device_id": "sensor-d8cbb0",
                "device_name": "Utesensor nord",
                "firmware_version": "0.1.0-dev",
                "last_seen_at": 1_786_484_296,
                "rssi_dbm": -77,
                "battery_voltage": None,
                "battery_percent": None,
                "measurement_interval_seconds": 3600,
                "config_version": 3,
                "reported_config_version": 3,
                "config_sync_state": "synced",
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


def test_dashboard_sensors_uses_highest_sequence_for_latest_measurement(
    tmp_path: Path,
) -> None:
    database_path = tmp_path / "environment.db"

    with create_client(database_path) as client:
        insert_device(
            database_path,
            device_id="sensor-a",
            device_name="Alpha",
        )
        insert_measurement(
            database_path,
            device_id="sensor-a",
            sequence=10,
            measured_at=1_786_484_999,
            timestamp_valid=True,
            temperature_c=20.1,
            humidity_percent=40.0,
            pressure_hpa=1012.0,
        )
        insert_measurement(
            database_path,
            device_id="sensor-a",
            sequence=11,
            measured_at=1_786_484_100,
            timestamp_valid=False,
            temperature_c=19.4,
            humidity_percent=44.0,
            pressure_hpa=1011.5,
        )

        response = client.get("/api/dashboard/sensors")

    assert response.status_code == 200
    latest_measurement = response.json()["sensors"][0]["latest_measurement"]
    assert latest_measurement == {
        "sequence": 11,
        "measured_at": 1_786_484_100,
        "timestamp_valid": False,
        "temperature_c": 19.4,
        "humidity_percent": 44.0,
        "pressure_hpa": 1011.5,
    }


def test_dashboard_sensors_returns_null_latest_measurement_when_absent(
    tmp_path: Path,
) -> None:
    database_path = tmp_path / "environment.db"

    with create_client(database_path) as client:
        insert_device(
            database_path,
            device_id="sensor-a",
            device_name="Alpha",
        )

        response = client.get("/api/dashboard/sensors")

    assert response.status_code == 200
    assert response.json()["sensors"][0]["latest_measurement"] is None


def test_dashboard_sensors_returns_waiting_for_sensor_state(tmp_path: Path) -> None:
    database_path = tmp_path / "environment.db"

    with create_client(database_path) as client:
        insert_device(
            database_path,
            device_id="sensor-a",
            device_name="Alpha",
            config_version=4,
            reported_config_version=3,
            battery_voltage=3.87,
            battery_percent=68,
        )

        response = client.get("/api/dashboard/sensors")

    assert response.status_code == 200
    sensor = response.json()["sensors"][0]
    assert sensor["config_sync_state"] == "waiting_for_sensor"
    assert sensor["battery_voltage"] == 3.87
    assert sensor["battery_percent"] == 68


def test_dashboard_sensors_returns_deterministic_name_and_device_id_order(
    tmp_path: Path,
) -> None:
    database_path = tmp_path / "environment.db"

    with create_client(database_path) as client:
        insert_device(database_path, device_id="sensor-b", device_name="Alpha")
        insert_device(database_path, device_id="sensor-a", device_name="Alpha")
        insert_device(database_path, device_id="sensor-c", device_name="Bravo")

        response = client.get("/api/dashboard/sensors")

    assert response.status_code == 200
    assert [sensor["device_id"] for sensor in response.json()["sensors"]] == [
        "sensor-a",
        "sensor-b",
        "sensor-c",
    ]


def test_dashboard_sensors_returns_device_ahead_state_when_reported_config_exceeds_server(
    tmp_path: Path,
) -> None:
    database_path = tmp_path / "environment.db"

    with create_client(database_path) as client:
        insert_device(
            database_path,
            device_id="sensor-a",
            device_name="Alpha",
            config_version=3,
            reported_config_version=4,
        )

        response = client.get("/api/dashboard/sensors")

    assert response.status_code == 200
    assert response.json()["sensors"][0]["config_sync_state"] == "device_ahead"
    assert response.json()["sensors"][0]["config_version"] == 3
    assert response.json()["sensors"][0]["reported_config_version"] == 4