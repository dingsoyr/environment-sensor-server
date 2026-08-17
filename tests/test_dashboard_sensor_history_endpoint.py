from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.database import connect_database
from app.main import create_app


UTC_DAY_SECONDS = 24 * 60 * 60


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
    battery_voltage: float | None = None,
    battery_percent: int | None = None,
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
                pressure_hpa,
                battery_voltage,
                battery_percent
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                device_id,
                sequence,
                measured_at,
                int(timestamp_valid),
                temperature_c,
                humidity_percent,
                pressure_hpa,
                battery_voltage,
                battery_percent,
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
        "resolution": "raw",
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
                "battery_voltage": None,
                "battery_percent": None,
            },
            {
                "sequence": 3,
                "measured_at": now - 100,
                "timestamp_valid": True,
                "temperature_c": 13.0,
                "humidity_percent": 53.0,
                "pressure_hpa": 1003.0,
                "battery_voltage": None,
                "battery_percent": None,
            },
            {
                "sequence": 5,
                "measured_at": now - 100,
                "timestamp_valid": True,
                "temperature_c": 12.0,
                "humidity_percent": 52.0,
                "pressure_hpa": 1002.0,
                "battery_voltage": None,
                "battery_percent": None,
            },
            {
                "sequence": 6,
                "measured_at": now - 1,
                "timestamp_valid": True,
                "temperature_c": 14.0,
                "humidity_percent": 54.0,
                "pressure_hpa": 1004.0,
                "battery_voltage": None,
                "battery_percent": None,
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
        "resolution": "raw",
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


def test_dashboard_sensor_history_requires_period_or_explicit_range(
    tmp_path: Path,
    monkeypatch,
) -> None:
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
        "resolution": "raw",
        "period": period,
        "from": now - expected_span,
        "to": now,
        "points": [],
    }


def test_dashboard_sensor_history_explicit_range_shorter_than_30_days_returns_raw_points(
    tmp_path: Path,
    monkeypatch,
) -> None:
    database_path = tmp_path / "environment.db"

    with create_client(database_path, monkeypatch, now=2_000_000) as client:
        insert_device(database_path, device_id="sensor-a")
        insert_measurement(
            database_path,
            device_id="sensor-a",
            sequence=10,
            measured_at=1_000,
            timestamp_valid=True,
            temperature_c=21.5,
            humidity_percent=48.0,
            pressure_hpa=1005.5,
        )
        insert_measurement(
            database_path,
            device_id="sensor-a",
            sequence=11,
            measured_at=2_000,
            timestamp_valid=False,
            temperature_c=22.5,
            humidity_percent=49.0,
            pressure_hpa=1006.5,
        )

        response = client.get("/api/dashboard/sensors/sensor-a/history?from=1000&to=2001")

    assert response.status_code == 200
    assert response.json() == {
        "device_id": "sensor-a",
        "resolution": "raw",
        "from": 1_000,
        "to": 2_001,
        "points": [
            {
                "sequence": 10,
                "measured_at": 1_000,
                "timestamp_valid": True,
                "temperature_c": 21.5,
                "humidity_percent": 48.0,
                "pressure_hpa": 1005.5,
                "battery_voltage": None,
                "battery_percent": None,
            },
            {
                "sequence": 11,
                "measured_at": 2_000,
                "timestamp_valid": False,
                "temperature_c": 22.5,
                "humidity_percent": 49.0,
                "pressure_hpa": 1006.5,
                "battery_voltage": None,
                "battery_percent": None,
            },
        ],
    }


def test_dashboard_sensor_history_explicit_range_exactly_30_days_returns_raw_resolution(
    tmp_path: Path,
    monkeypatch,
) -> None:
    database_path = tmp_path / "environment.db"
    range_start = 1_700_000_000
    range_end = range_start + (30 * UTC_DAY_SECONDS)

    with create_client(database_path, monkeypatch, now=2_000_000) as client:
        insert_device(database_path, device_id="sensor-a")

        response = client.get(
            f"/api/dashboard/sensors/sensor-a/history?from={range_start}&to={range_end}"
        )

    assert response.status_code == 200
    assert response.json() == {
        "device_id": "sensor-a",
        "resolution": "raw",
        "from": range_start,
        "to": range_end,
        "points": [],
    }


def test_dashboard_sensor_history_explicit_range_greater_than_30_days_returns_daily_aggregates(
    tmp_path: Path,
    monkeypatch,
) -> None:
    database_path = tmp_path / "environment.db"
    day_zero = 1_704_067_200
    history_from = day_zero + (12 * 60 * 60)
    history_to = day_zero + (32 * UTC_DAY_SECONDS) + (6 * 60 * 60)

    with create_client(database_path, monkeypatch, now=2_000_000) as client:
        insert_device(database_path, device_id="sensor-a")
        insert_measurement(
            database_path,
            device_id="sensor-a",
            sequence=1,
            measured_at=day_zero + (11 * 60 * 60),
            timestamp_valid=True,
            temperature_c=5.0,
            humidity_percent=35.0,
            pressure_hpa=995.0,
        )
        insert_measurement(
            database_path,
            device_id="sensor-a",
            sequence=2,
            measured_at=history_from,
            timestamp_valid=True,
            temperature_c=10.0,
            humidity_percent=40.0,
            pressure_hpa=1000.0,
        )
        insert_measurement(
            database_path,
            device_id="sensor-a",
            sequence=3,
            measured_at=day_zero + (23 * 60 * 60),
            timestamp_valid=True,
            temperature_c=20.0,
            humidity_percent=50.0,
            pressure_hpa=1010.0,
        )
        insert_measurement(
            database_path,
            device_id="sensor-a",
            sequence=4,
            measured_at=day_zero + UTC_DAY_SECONDS + (5 * 60 * 60),
            timestamp_valid=True,
            temperature_c=30.0,
            humidity_percent=60.0,
            pressure_hpa=1020.0,
        )
        insert_measurement(
            database_path,
            device_id="sensor-a",
            sequence=5,
            measured_at=day_zero + UTC_DAY_SECONDS + (18 * 60 * 60),
            timestamp_valid=False,
            temperature_c=40.0,
            humidity_percent=70.0,
            pressure_hpa=1030.0,
        )
        insert_measurement(
            database_path,
            device_id="sensor-a",
            sequence=6,
            measured_at=day_zero + (3 * UTC_DAY_SECONDS) + (2 * 60 * 60),
            timestamp_valid=True,
            temperature_c=50.0,
            humidity_percent=80.0,
            pressure_hpa=1040.0,
        )
        insert_measurement(
            database_path,
            device_id="sensor-a",
            sequence=7,
            measured_at=day_zero + (31 * UTC_DAY_SECONDS) + (5 * 60 * 60),
            timestamp_valid=True,
            temperature_c=60.0,
            humidity_percent=90.0,
            pressure_hpa=1050.0,
        )
        insert_measurement(
            database_path,
            device_id="sensor-a",
            sequence=8,
            measured_at=history_to,
            timestamp_valid=True,
            temperature_c=70.0,
            humidity_percent=95.0,
            pressure_hpa=1060.0,
        )

        response = client.get(
            f"/api/dashboard/sensors/sensor-a/history?from={history_from}&to={history_to}"
        )

    assert response.status_code == 200
    assert response.json() == {
        "device_id": "sensor-a",
        "resolution": "day",
        "from": history_from,
        "to": history_to,
        "points": [
            {
                "period_start": day_zero,
                "sample_count": 2,
                "temperature_min_c": 10.0,
                "temperature_avg_c": 15.0,
                "temperature_max_c": 20.0,
                "humidity_min_percent": 40.0,
                "humidity_avg_percent": 45.0,
                "humidity_max_percent": 50.0,
                "pressure_min_hpa": 1000.0,
                "pressure_avg_hpa": 1005.0,
                "pressure_max_hpa": 1010.0,
                "battery_voltage_min": None,
                "battery_voltage_avg": None,
                "battery_voltage_max": None,
                "battery_percent_min": None,
                "battery_percent_avg": None,
                "battery_percent_max": None,
            },
            {
                "period_start": day_zero + UTC_DAY_SECONDS,
                "sample_count": 2,
                "temperature_min_c": 30.0,
                "temperature_avg_c": 35.0,
                "temperature_max_c": 40.0,
                "humidity_min_percent": 60.0,
                "humidity_avg_percent": 65.0,
                "humidity_max_percent": 70.0,
                "pressure_min_hpa": 1020.0,
                "pressure_avg_hpa": 1025.0,
                "pressure_max_hpa": 1030.0,
                "battery_voltage_min": None,
                "battery_voltage_avg": None,
                "battery_voltage_max": None,
                "battery_percent_min": None,
                "battery_percent_avg": None,
                "battery_percent_max": None,
            },
            {
                "period_start": day_zero + (3 * UTC_DAY_SECONDS),
                "sample_count": 1,
                "temperature_min_c": 50.0,
                "temperature_avg_c": 50.0,
                "temperature_max_c": 50.0,
                "humidity_min_percent": 80.0,
                "humidity_avg_percent": 80.0,
                "humidity_max_percent": 80.0,
                "pressure_min_hpa": 1040.0,
                "pressure_avg_hpa": 1040.0,
                "pressure_max_hpa": 1040.0,
                "battery_voltage_min": None,
                "battery_voltage_avg": None,
                "battery_voltage_max": None,
                "battery_percent_min": None,
                "battery_percent_avg": None,
                "battery_percent_max": None,
            },
            {
                "period_start": day_zero + (31 * UTC_DAY_SECONDS),
                "sample_count": 1,
                "temperature_min_c": 60.0,
                "temperature_avg_c": 60.0,
                "temperature_max_c": 60.0,
                "humidity_min_percent": 90.0,
                "humidity_avg_percent": 90.0,
                "humidity_max_percent": 90.0,
                "pressure_min_hpa": 1050.0,
                "pressure_avg_hpa": 1050.0,
                "pressure_max_hpa": 1050.0,
                "battery_voltage_min": None,
                "battery_voltage_avg": None,
                "battery_voltage_max": None,
                "battery_percent_min": None,
                "battery_percent_avg": None,
                "battery_percent_max": None,
            },
        ],
    }


def test_dashboard_sensor_history_raw_returns_battery_fields_and_nulls_for_missing_samples(
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
            measured_at=now - 120,
            timestamp_valid=True,
            temperature_c=10.0,
            humidity_percent=50.0,
            pressure_hpa=1000.0,
            battery_voltage=3.91,
            battery_percent=73,
        )
        insert_measurement(
            database_path,
            device_id="sensor-a",
            sequence=2,
            measured_at=now - 60,
            timestamp_valid=True,
            temperature_c=11.0,
            humidity_percent=51.0,
            pressure_hpa=1001.0,
        )

        response = client.get("/api/dashboard/sensors/sensor-a/history?period=24h")

    assert response.status_code == 200
    assert response.json()["points"] == [
        {
            "sequence": 1,
            "measured_at": now - 120,
            "timestamp_valid": True,
            "temperature_c": 10.0,
            "humidity_percent": 50.0,
            "pressure_hpa": 1000.0,
            "battery_voltage": 3.91,
            "battery_percent": 73,
        },
        {
            "sequence": 2,
            "measured_at": now - 60,
            "timestamp_valid": True,
            "temperature_c": 11.0,
            "humidity_percent": 51.0,
            "pressure_hpa": 1001.0,
            "battery_voltage": None,
            "battery_percent": None,
        },
    ]


def test_dashboard_sensor_history_day_returns_battery_aggregates(
    tmp_path: Path,
    monkeypatch,
) -> None:
    database_path = tmp_path / "environment.db"
    day_zero = 1_704_067_200
    history_from = day_zero
    history_to = day_zero + (31 * UTC_DAY_SECONDS)

    with create_client(database_path, monkeypatch, now=2_000_000) as client:
        insert_device(database_path, device_id="sensor-a")
        insert_measurement(
            database_path,
            device_id="sensor-a",
            sequence=1,
            measured_at=day_zero + 60,
            timestamp_valid=True,
            temperature_c=10.0,
            humidity_percent=40.0,
            pressure_hpa=1000.0,
            battery_voltage=4.10,
            battery_percent=90,
        )
        insert_measurement(
            database_path,
            device_id="sensor-a",
            sequence=2,
            measured_at=day_zero + 120,
            timestamp_valid=True,
            temperature_c=20.0,
            humidity_percent=50.0,
            pressure_hpa=1010.0,
        )
        insert_measurement(
            database_path,
            device_id="sensor-a",
            sequence=3,
            measured_at=day_zero + UTC_DAY_SECONDS + 60,
            timestamp_valid=True,
            temperature_c=30.0,
            humidity_percent=60.0,
            pressure_hpa=1020.0,
            battery_voltage=3.90,
            battery_percent=70,
        )

        response = client.get(
            f"/api/dashboard/sensors/sensor-a/history?from={history_from}&to={history_to}"
        )

    assert response.status_code == 200
    assert response.json()["points"][:2] == [
        {
            "period_start": day_zero,
            "sample_count": 2,
            "temperature_min_c": 10.0,
            "temperature_avg_c": 15.0,
            "temperature_max_c": 20.0,
            "humidity_min_percent": 40.0,
            "humidity_avg_percent": 45.0,
            "humidity_max_percent": 50.0,
            "pressure_min_hpa": 1000.0,
            "pressure_avg_hpa": 1005.0,
            "pressure_max_hpa": 1010.0,
            "battery_voltage_min": 4.1,
            "battery_voltage_avg": 4.1,
            "battery_voltage_max": 4.1,
            "battery_percent_min": 90,
            "battery_percent_avg": 90.0,
            "battery_percent_max": 90,
        },
        {
            "period_start": day_zero + UTC_DAY_SECONDS,
            "sample_count": 1,
            "temperature_min_c": 30.0,
            "temperature_avg_c": 30.0,
            "temperature_max_c": 30.0,
            "humidity_min_percent": 60.0,
            "humidity_avg_percent": 60.0,
            "humidity_max_percent": 60.0,
            "pressure_min_hpa": 1020.0,
            "pressure_avg_hpa": 1020.0,
            "pressure_max_hpa": 1020.0,
            "battery_voltage_min": 3.9,
            "battery_voltage_avg": 3.9,
            "battery_voltage_max": 3.9,
            "battery_percent_min": 70,
            "battery_percent_avg": 70.0,
            "battery_percent_max": 70,
        },
    ]


def test_dashboard_sensor_history_explicit_range_returns_empty_points_when_no_measurements_match(
    tmp_path: Path,
    monkeypatch,
) -> None:
    database_path = tmp_path / "environment.db"
    history_from = 1_700_000_000
    history_to = history_from + (31 * UTC_DAY_SECONDS)

    with create_client(database_path, monkeypatch, now=2_000_000) as client:
        insert_device(database_path, device_id="sensor-a")

        response = client.get(
            f"/api/dashboard/sensors/sensor-a/history?from={history_from}&to={history_to}"
        )

    assert response.status_code == 200
    assert response.json() == {
        "device_id": "sensor-a",
        "resolution": "day",
        "from": history_from,
        "to": history_to,
        "points": [],
    }


def test_dashboard_sensor_history_rejects_period_and_explicit_range_together(
    tmp_path: Path,
    monkeypatch,
) -> None:
    database_path = tmp_path / "environment.db"

    with create_client(database_path, monkeypatch, now=2_000_000) as client:
        insert_device(database_path, device_id="sensor-a")
        response = client.get(
            "/api/dashboard/sensors/sensor-a/history?period=24h&from=100&to=200"
        )

    assert response.status_code == 422


@pytest.mark.parametrize("query", ["from=100", "to=200"])
def test_dashboard_sensor_history_rejects_incomplete_explicit_range(
    tmp_path: Path,
    monkeypatch,
    query: str,
) -> None:
    database_path = tmp_path / "environment.db"

    with create_client(database_path, monkeypatch, now=2_000_000) as client:
        insert_device(database_path, device_id="sensor-a")
        response = client.get(f"/api/dashboard/sensors/sensor-a/history?{query}")

    assert response.status_code == 422


@pytest.mark.parametrize(
    ("history_from", "history_to"),
    [(200, 200), (300, 200)],
)
def test_dashboard_sensor_history_rejects_non_increasing_explicit_range(
    tmp_path: Path,
    monkeypatch,
    history_from: int,
    history_to: int,
) -> None:
    database_path = tmp_path / "environment.db"

    with create_client(database_path, monkeypatch, now=2_000_000) as client:
        insert_device(database_path, device_id="sensor-a")
        response = client.get(
            f"/api/dashboard/sensors/sensor-a/history?from={history_from}&to={history_to}"
        )

    assert response.status_code == 422