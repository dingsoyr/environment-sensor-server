from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, StrictInt, StrictStr, field_validator, model_validator


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


class DashboardSensorConfigurationPatchRequest(BaseModel):
    device_name: StrictStr | None = None
    measurement_interval_seconds: StrictInt | None = Field(default=None, gt=0)

    @model_validator(mode="before")
    @classmethod
    def validate_patch_payload(cls, value: object) -> object:
        if not isinstance(value, dict):
            return value

        editable_fields = {"device_name", "measurement_interval_seconds"}
        provided_fields = editable_fields.intersection(value)

        if not provided_fields:
            raise ValueError("at least one editable field must be supplied")

        for field_name in provided_fields:
            if value[field_name] is None:
                raise ValueError(f"{field_name} must not be null")

        return value

    @field_validator("device_name")
    @classmethod
    def validate_device_name(cls, value: str | None) -> str | None:
        if value is None:
            return value

        trimmed_value = value.strip()
        if not trimmed_value:
            raise ValueError("device_name must not be empty")

        return trimmed_value


class DashboardSensorConfigurationPatchResponse(BaseModel):
    device_id: str
    device_name: str | None
    measurement_interval_seconds: int
    config_version: int
    reported_config_version: int
    config_sync_state: Literal["synced", "waiting_for_sensor", "device_ahead"]