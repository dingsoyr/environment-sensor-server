from __future__ import annotations

from dataclasses import dataclass
import os
import sqlite3
from pathlib import Path


DEFAULT_DATABASE_PATH = Path("data/environment.db")
DATABASE_PATH_ENV_VAR = "ENVIRONMENT_SENSOR_DATABASE_PATH"


@dataclass(frozen=True)
class DeviceConfigurationRecord:
    config_version: int
    device_name: str | None
    measurement_interval_seconds: int


@dataclass(frozen=True)
class LatestMeasurementRecord:
    sequence: int
    measured_at: int
    timestamp_valid: bool
    temperature_c: float
    humidity_percent: float
    pressure_hpa: float


@dataclass(frozen=True)
class DashboardSensorRecord:
    device_id: str
    device_name: str | None
    firmware_version: str | None
    last_seen_at: int | None
    rssi_dbm: int | None
    battery_voltage: float | None
    battery_percent: int | None
    measurement_interval_seconds: int
    config_version: int
    reported_config_version: int
    config_sync_state: str
    latest_measurement: LatestMeasurementRecord | None


@dataclass(frozen=True)
class DashboardSensorHistoryPointRecord:
    sequence: int
    measured_at: int
    timestamp_valid: bool
    temperature_c: float
    humidity_percent: float
    pressure_hpa: float


def _build_dashboard_sensor_record(row: sqlite3.Row | tuple) -> DashboardSensorRecord:
    latest_measurement = None
    if row[10] is not None:
        latest_measurement = LatestMeasurementRecord(
            sequence=row[10],
            measured_at=row[11],
            timestamp_valid=bool(row[12]),
            temperature_c=row[13],
            humidity_percent=row[14],
            pressure_hpa=row[15],
        )

    return DashboardSensorRecord(
        device_id=row[0],
        device_name=row[1],
        firmware_version=row[2],
        last_seen_at=row[3],
        rssi_dbm=row[4],
        battery_voltage=row[5],
        battery_percent=row[6],
        measurement_interval_seconds=row[7],
        config_version=row[8],
        reported_config_version=row[9],
        config_sync_state=_derive_config_sync_state(
            device_id=row[0],
            config_version=row[8],
            reported_config_version=row[9],
        ),
        latest_measurement=latest_measurement,
    )


DASHBOARD_SENSOR_SELECT = """
    SELECT
        d.device_id,
        d.device_name,
        d.firmware_version,
        d.last_seen_at,
        d.rssi_dbm,
        d.battery_voltage,
        d.battery_percent,
        d.measurement_interval_seconds,
        d.config_version,
        d.reported_config_version,
        m.sequence,
        m.measured_at,
        m.timestamp_valid,
        m.temperature_c,
        m.humidity_percent,
        m.pressure_hpa
    FROM devices d
    LEFT JOIN measurements m
      ON m.device_id = d.device_id
     AND m.sequence = (
         SELECT MAX(m2.sequence)
         FROM measurements m2
         WHERE m2.device_id = d.device_id
     )
"""


def get_database_path(database_path: str | Path | None = None) -> Path:
    if database_path is not None:
        return Path(database_path)

    configured_path = os.getenv(DATABASE_PATH_ENV_VAR)
    if configured_path:
        return Path(configured_path)

    return DEFAULT_DATABASE_PATH


def connect_database(database_path: str | Path | None = None) -> sqlite3.Connection:
    resolved_path = get_database_path(database_path)
    resolved_path.parent.mkdir(parents=True, exist_ok=True)

    connection = sqlite3.connect(resolved_path)
    connection.execute("PRAGMA foreign_keys = ON")
    return connection


def initialize_database(database_path: str | Path | None = None) -> Path:
    resolved_path = get_database_path(database_path)

    with connect_database(resolved_path) as connection:
        connection.executescript(
            """
            CREATE TABLE IF NOT EXISTS devices (
                device_id TEXT PRIMARY KEY,
                device_name TEXT,
                firmware_version TEXT,
                config_version INTEGER NOT NULL DEFAULT 0,
                reported_config_version INTEGER NOT NULL DEFAULT 0 CHECK (reported_config_version >= 0),
                measurement_interval_seconds INTEGER NOT NULL DEFAULT 3600,
                last_seen_at INTEGER,
                rssi_dbm INTEGER,
                battery_voltage REAL,
                battery_percent INTEGER
            );

            CREATE TABLE IF NOT EXISTS measurements (
                id INTEGER PRIMARY KEY,
                device_id TEXT NOT NULL,
                sequence INTEGER NOT NULL,
                measured_at INTEGER NOT NULL,
                timestamp_valid INTEGER NOT NULL,
                temperature_c REAL NOT NULL,
                humidity_percent REAL NOT NULL,
                pressure_hpa REAL NOT NULL,
                UNIQUE (device_id, sequence),
                FOREIGN KEY (device_id) REFERENCES devices(device_id)
            );

            CREATE INDEX IF NOT EXISTS idx_measurements_device_measured_at
            ON measurements(device_id, measured_at);
            """
        )

    return resolved_path


def get_device_configuration(
    device_id: str,
    database_path: str | Path | None = None,
) -> DeviceConfigurationRecord | None:
    with connect_database(database_path) as connection:
        row = connection.execute(
            """
            SELECT config_version, device_name, measurement_interval_seconds
            FROM devices
            WHERE device_id = ?
            """,
            (device_id,),
        ).fetchone()

    if row is None:
        return None

    return DeviceConfigurationRecord(
        config_version=row[0],
        device_name=row[1],
        measurement_interval_seconds=row[2],
    )


def device_exists(
    device_id: str,
    database_path: str | Path | None = None,
) -> bool:
    with connect_database(database_path) as connection:
        row = connection.execute(
            """
            SELECT 1
            FROM devices
            WHERE device_id = ?
            """,
            (device_id,),
        ).fetchone()

    return row is not None


def _derive_config_sync_state(
    device_id: str,
    config_version: int,
    reported_config_version: int,
) -> str:
    if reported_config_version == config_version:
        return "synced"

    if reported_config_version < config_version:
        return "waiting_for_sensor"

    return "device_ahead"


def list_dashboard_sensors(
    database_path: str | Path | None = None,
) -> list[DashboardSensorRecord]:
    with connect_database(database_path) as connection:
        rows = connection.execute(
            DASHBOARD_SENSOR_SELECT
            + """
            ORDER BY d.device_name, d.device_id
            """
        ).fetchall()

    return [_build_dashboard_sensor_record(row) for row in rows]


def get_dashboard_sensor(
    device_id: str,
    database_path: str | Path | None = None,
) -> DashboardSensorRecord | None:
    with connect_database(database_path) as connection:
        row = connection.execute(
            DASHBOARD_SENSOR_SELECT
            + """
            WHERE d.device_id = ?
            """,
            (device_id,),
        ).fetchone()

    if row is None:
        return None

    return _build_dashboard_sensor_record(row)


def list_dashboard_sensor_history(
    device_id: str,
    measured_from: int,
    measured_to: int,
    database_path: str | Path | None = None,
) -> list[DashboardSensorHistoryPointRecord]:
    with connect_database(database_path) as connection:
        rows = connection.execute(
            """
            SELECT
                sequence,
                measured_at,
                timestamp_valid,
                temperature_c,
                humidity_percent,
                pressure_hpa
            FROM measurements
            WHERE device_id = ?
              AND measured_at >= ?
              AND measured_at < ?
            ORDER BY measured_at ASC, sequence ASC
            """,
            (device_id, measured_from, measured_to),
        ).fetchall()

    return [
        DashboardSensorHistoryPointRecord(
            sequence=row[0],
            measured_at=row[1],
            timestamp_valid=bool(row[2]),
            temperature_c=row[3],
            humidity_percent=row[4],
            pressure_hpa=row[5],
        )
        for row in rows
    ]