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