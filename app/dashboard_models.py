from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class DashboardLatestMeasurement(BaseModel):
    sequence: int
    measured_at: int
    timestamp_valid: bool
    temperature_c: float
    humidity_percent: float
    pressure_hpa: float


class DashboardSensorConfiguration(BaseModel):
    measurement_interval_seconds: int
    config_version: int
    reported_config_version: int
    config_sync_state: Literal["synced", "waiting_for_sensor", "device_ahead"]


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


class DashboardSensorDetail(BaseModel):
    device_id: str
    device_name: str | None
    firmware_version: str | None
    last_seen_at: int | None
    rssi_dbm: int | None
    battery_voltage: float | None
    battery_percent: int | None
    configuration: DashboardSensorConfiguration
    latest_measurement: DashboardLatestMeasurement | None


class DashboardSensorHistoryPoint(BaseModel):
    sequence: int
    measured_at: int
    timestamp_valid: bool
    temperature_c: float
    humidity_percent: float
    pressure_hpa: float


class DashboardSensorHistoryResponse(BaseModel):
    device_id: str
    period: Literal["24h", "7d", "30d"]
    from_: int = Field(alias="from")
    to: int
    points: list[DashboardSensorHistoryPoint]

    model_config = ConfigDict(populate_by_name=True)