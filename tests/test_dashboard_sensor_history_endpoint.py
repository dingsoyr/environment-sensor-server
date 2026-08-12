from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.database import connect_database
from app.main import create_app


def create_client(database_path: Path, monkeypatch, *, now: int) -> TestClient:
    monkeypatch.setattr("app.main.time.time", lambda: now)
    app = create_app(database_path)
    return TestClient(app)


def insert_device(
    database_path: Path,
    *,
    device_id: str,
    device_name: str | None = "Sensor",
) -> None:
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
            (device_id, device_name, 3, 3, 3600),
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


def test_dashboard_sensor_history_24h_returns_windowed_points_in_order(
    tmp_path: Path,
    monkeypatch,
) -> None:
    database_path = tmp_path / "environment.db"
    now = 2_000_000

    with create_client(database_path, monkeypatch, now=now) as client:
        insert_device(database_path, device_id="sensor-a")
        insert_measurement(
            database_path,
            device_id="sensor-a",
            sequence=1,
            measured_at=now - 86_401,
            timestamp_valid=True,
            temperature_c=10.0,
            humidity_percent=50.0,
            pressure_hpa=1000.0,
        )
        insert_measurement(
            database_path,
            device_id="sensor-a",
            sequence=2,
            measured_at=now - 86_400,
            timestamp_valid=False,
            temperature_c=11.0,
            humidity_percent=51.0,
            pressure_hpa=1001.0,
        )
        insert_measurement(
            database_path,
            device_id="sensor-a",
            sequence=5,
            measured_at=now - 100,
            timestamp_valid=True,
            temperature_c=12.0,
            humidity_percent=52.0,
            pressure_hpa=1002.0,
        )
        insert_measurement(
            database_path,
            device_id="sensor-a",
            sequence=3,
            measured_at=now - 100,
            timestamp_valid=True,
            temperature_c=13.0,
            humidity_percent=53.0,
            pressure_hpa=1003.0,
        )
        insert_measurement(
            database_path,
            device_id="sensor-a",
            sequence=6,
            measured_at=now - 1,
            timestamp_valid=True,
            temperature_c=14.0,
            humidity_percent=54.0,
            pressure_hpa=1004.0,
        )
        insert_measurement(
            database_path,
            device_id="sensor-a",
            sequence=7,
            measured_at=now,
            timestamp_valid=True,
            temperature_c=15.0,
            humidity_percent=55.0,
            pressure_hpa=1005.0,
        )

        response = client.get("/api/dashboard/sensors/sensor-a/history?period=24h")

    assert response.status_code == 200
    assert response.json() == {
        "device_id": "sensor-a",
        "period": "24h",
        "from": now - 86_400,
        "to": now,
        "points": [
            {
                "sequence": 2,
                "measured_at": now - 86_400,
                "timestamp_valid": False,
                "temperature_c": 11.0,
                "humidity_percent": 51.0,
                "pressure_hpa": 1001.0,
            },
            {
                "sequence": 3,
                "measured_at": now - 100,
                "timestamp_valid": True,
                "temperature_c": 13.0,
                "humidity_percent": 53.0,
                "pressure_hpa": 1003.0,
            },
            {
                "sequence": 5,
                "measured_at": now - 100,
                "timestamp_valid": True,
                "temperature_c": 12.0,
                "humidity_percent": 52.0,
                "pressure_hpa": 1002.0,
            },
            {
                "sequence": 6,
                "measured_at": now - 1,
                "timestamp_valid": True,
                "temperature_c": 14.0,
                "humidity_percent": 54.0,
                "pressure_hpa": 1004.0,
            },
        ],
    }


def test_dashboard_sensor_history_returns_empty_points_for_known_device_without_matches(
    tmp_path: Path,
    monkeypatch,
) -> None:
    database_path = tmp_path / "environment.db"
    now = 2_000_000

    with create_client(database_path, monkeypatch, now=now) as client:
        insert_device(database_path, device_id="sensor-a")
        insert_measurement(
            database_path,
            device_id="sensor-a",
            sequence=1,
            measured_at=now - 86_401,
            timestamp_valid=True,
            temperature_c=10.0,
            humidity_percent=50.0,
            pressure_hpa=1000.0,
        )

        response = client.get("/api/dashboard/sensors/sensor-a/history?period=24h")

    assert response.status_code == 200
    assert response.json() == {
        "device_id": "sensor-a",
        "period": "24h",
        "from": now - 86_400,
        "to": now,
        "points": [],
    }


def test_dashboard_sensor_history_returns_not_found_for_unknown_device(
    tmp_path: Path,
    monkeypatch,
) -> None:
    database_path = tmp_path / "environment.db"

    with create_client(database_path, monkeypatch, now=2_000_000) as client:
        response = client.get("/api/dashboard/sensors/missing/history?period=24h")

    assert response.status_code == 404
    assert response.json() == {"detail": "Not Found"}


def test_dashboard_sensor_history_requires_period(tmp_path: Path, monkeypatch) -> None:
    database_path = tmp_path / "environment.db"

    with create_client(database_path, monkeypatch, now=2_000_000) as client:
        insert_device(database_path, device_id="sensor-a")
        response = client.get("/api/dashboard/sensors/sensor-a/history")

    assert response.status_code == 422


def test_dashboard_sensor_history_rejects_invalid_period(
    tmp_path: Path,
    monkeypatch,
) -> None:
    database_path = tmp_path / "environment.db"

    with create_client(database_path, monkeypatch, now=2_000_000) as client:
        insert_device(database_path, device_id="sensor-a")
        response = client.get("/api/dashboard/sensors/sensor-a/history?period=12h")

    assert response.status_code == 422


def test_dashboard_sensor_history_rejects_1y_period(
    tmp_path: Path,
    monkeypatch,
) -> None:
    database_path = tmp_path / "environment.db"

    with create_client(database_path, monkeypatch, now=2_000_000) as client:
        insert_device(database_path, device_id="sensor-a")
        response = client.get("/api/dashboard/sensors/sensor-a/history?period=1y")

    assert response.status_code == 422


@pytest.mark.parametrize(
    ("period", "expected_span"),
    [("7d", 7 * 24 * 60 * 60), ("30d", 30 * 24 * 60 * 60)],
)
def test_dashboard_sensor_history_period_mappings(
    tmp_path: Path,
    monkeypatch,
    period: str,
    expected_span: int,
) -> None:
    database_path = tmp_path / "environment.db"
    now = 2_000_000

    with create_client(database_path, monkeypatch, now=now) as client:
        insert_device(database_path, device_id="sensor-a")

        response = client.get(f"/api/dashboard/sensors/sensor-a/history?period={period}")

    assert response.status_code == 200
    assert response.json() == {
        "device_id": "sensor-a",
        "period": period,
        "from": now - expected_span,
        "to": now,
        "points": [],
    }