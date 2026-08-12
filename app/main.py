from __future__ import annotations

import sqlite3
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request

from app.api_v1_models import (
    DeviceConfiguration,
    MeasurementUploadRequest,
    MeasurementUploadResponse,
)
from app.dashboard_models import (
    DashboardLatestMeasurement,
    DashboardSensorConfiguration,
    DashboardSensorDetail,
    DashboardSensor,
    DashboardSensorsResponse,
)
from app.database import (
    get_dashboard_sensor,
    get_device_configuration,
    initialize_database,
    list_dashboard_sensors,
)
from app.measurement_ingestion import ingest_measurement_upload


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    initialize_database(app.state.database_path)
    yield


def create_app(database_path: str | Path | None = None) -> FastAPI:
    app = FastAPI(title="Environment Sensor Server", lifespan=lifespan)
    app.state.database_path = database_path

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/api/dashboard/sensors", response_model=DashboardSensorsResponse)
    def get_dashboard_sensors(request: Request) -> DashboardSensorsResponse:
        try:
            sensor_records = list_dashboard_sensors(
                database_path=request.app.state.database_path,
            )
        except sqlite3.DatabaseError as error:
            raise HTTPException(status_code=500, detail="Internal Server Error") from error

        sensors = [
            DashboardSensor(
                device_id=sensor_record.device_id,
                device_name=sensor_record.device_name,
                firmware_version=sensor_record.firmware_version,
                last_seen_at=sensor_record.last_seen_at,
                rssi_dbm=sensor_record.rssi_dbm,
                battery_voltage=sensor_record.battery_voltage,
                battery_percent=sensor_record.battery_percent,
                measurement_interval_seconds=sensor_record.measurement_interval_seconds,
                config_version=sensor_record.config_version,
                reported_config_version=sensor_record.reported_config_version,
                config_sync_state=sensor_record.config_sync_state,
                latest_measurement=(
                    DashboardLatestMeasurement(
                        sequence=sensor_record.latest_measurement.sequence,
                        measured_at=sensor_record.latest_measurement.measured_at,
                        timestamp_valid=sensor_record.latest_measurement.timestamp_valid,
                        temperature_c=sensor_record.latest_measurement.temperature_c,
                        humidity_percent=sensor_record.latest_measurement.humidity_percent,
                        pressure_hpa=sensor_record.latest_measurement.pressure_hpa,
                    )
                    if sensor_record.latest_measurement is not None
                    else None
                ),
            )
            for sensor_record in sensor_records
        ]

        return DashboardSensorsResponse(sensors=sensors)

    @app.get("/api/dashboard/sensors/{device_id}", response_model=DashboardSensorDetail)
    def get_dashboard_sensor_detail(
        device_id: str,
        request: Request,
    ) -> DashboardSensorDetail:
        try:
            sensor_record = get_dashboard_sensor(
                device_id,
                database_path=request.app.state.database_path,
            )
        except sqlite3.DatabaseError as error:
            raise HTTPException(status_code=500, detail="Internal Server Error") from error

        if sensor_record is None:
            raise HTTPException(status_code=404, detail="Not Found")

        latest_measurement = (
            DashboardLatestMeasurement(
                sequence=sensor_record.latest_measurement.sequence,
                measured_at=sensor_record.latest_measurement.measured_at,
                timestamp_valid=sensor_record.latest_measurement.timestamp_valid,
                temperature_c=sensor_record.latest_measurement.temperature_c,
                humidity_percent=sensor_record.latest_measurement.humidity_percent,
                pressure_hpa=sensor_record.latest_measurement.pressure_hpa,
            )
            if sensor_record.latest_measurement is not None
            else None
        )

        return DashboardSensorDetail(
            device_id=sensor_record.device_id,
            device_name=sensor_record.device_name,
            firmware_version=sensor_record.firmware_version,
            last_seen_at=sensor_record.last_seen_at,
            rssi_dbm=sensor_record.rssi_dbm,
            battery_voltage=sensor_record.battery_voltage,
            battery_percent=sensor_record.battery_percent,
            configuration=DashboardSensorConfiguration(
                measurement_interval_seconds=sensor_record.measurement_interval_seconds,
                config_version=sensor_record.config_version,
                reported_config_version=sensor_record.reported_config_version,
                config_sync_state=sensor_record.config_sync_state,
            ),
            latest_measurement=latest_measurement,
        )

    @app.post(
        "/api/v1/measurements",
        response_model=MeasurementUploadResponse,
        response_model_exclude_none=True,
    )
    def post_measurements(
        upload: MeasurementUploadRequest,
        request: Request,
    ) -> MeasurementUploadResponse:
        try:
            result = ingest_measurement_upload(
                upload,
                database_path=request.app.state.database_path,
            )
        except sqlite3.DatabaseError as error:
            raise HTTPException(status_code=500, detail="Internal Server Error") from error

        device_configuration = get_device_configuration(
            upload.device_id,
            database_path=request.app.state.database_path,
        )
        if device_configuration is None:
            raise HTTPException(status_code=500, detail="Internal Server Error")

        configuration = None
        if (
            device_configuration.config_version > upload.config_version
            and device_configuration.device_name is not None
        ):
            configuration = DeviceConfiguration(
                device_name=device_configuration.device_name,
                measurement_interval_seconds=device_configuration.measurement_interval_seconds,
            )

        return MeasurementUploadResponse(
            api_version=1,
            acknowledged_through=result.acknowledged_through,
            server_time=result.server_time,
            config_version=device_configuration.config_version,
            configuration=configuration,
        )

    return app


app = create_app()