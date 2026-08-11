from __future__ import annotations

from typing import Annotated, Literal

from pydantic import BaseModel, Field, StringConstraints


NonEmptyString = Annotated[str, StringConstraints(min_length=1)]


class DeviceStatus(BaseModel):
    rssi_dbm: int
    battery_voltage: float | None = None
    battery_percent: int | None = Field(default=None, ge=0, le=100)


class MeasurementUploadItem(BaseModel):
    sequence: int = Field(ge=0)
    measured_at: int
    timestamp_valid: bool
    temperature_c: float
    humidity_percent: float
    pressure_hpa: float


class MeasurementUploadRequest(BaseModel):
    api_version: Literal[1]
    device_id: NonEmptyString
    firmware_version: NonEmptyString
    config_version: int = Field(ge=0)
    status: DeviceStatus
    measurements: list[MeasurementUploadItem] = Field(min_length=1)


class DeviceConfiguration(BaseModel):
    device_name: str
    measurement_interval_seconds: int = Field(gt=0)


class MeasurementUploadResponse(BaseModel):
    api_version: Literal[1]
    acknowledged_through: int
    server_time: int
    config_version: int
    configuration: DeviceConfiguration | None = None