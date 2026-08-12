from __future__ import annotations

from typing import Literal

from pydantic import BaseModel


class DashboardLatestMeasurement(BaseModel):
    sequence: int
    measured_at: int
    timestamp_valid: bool
    temperature_c: float
    humidity_percent: float
    pressure_hpa: float


class DashboardSensor(BaseModel):
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
    config_sync_state: Literal["synced", "waiting_for_sensor", "device_ahead"]
    latest_measurement: DashboardLatestMeasurement | None


class DashboardSensorsResponse(BaseModel):
    sensors: list[DashboardSensor]