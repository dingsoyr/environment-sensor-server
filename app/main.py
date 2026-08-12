from __future__ import annotations

import sqlite3
import time
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Literal

from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from app.api_v1_models import (
    DeviceConfiguration,
    MeasurementUploadRequest,
    MeasurementUploadResponse,
)
from app.dashboard_models import (
    DashboardLatestMeasurement,
    DashboardSensorConfigurationPatchRequest,
    DashboardSensorConfigurationPatchResponse,
    DashboardSensorConfiguration,
    DashboardSensorDetail,
    DashboardSensorHistoryDayPoint,
    DashboardSensorHistoryDayResponse,
    DashboardSensorHistoryPoint,
    DashboardSensorHistoryRawResponse,
    DashboardSensorHistoryResponse,
    DashboardSensor,
    DashboardSensorsResponse,
)
from app.database import (
    device_exists,
    get_dashboard_sensor,
    get_device_configuration,
    initialize_database,
    list_dashboard_sensor_history,
    list_dashboard_sensor_history_by_day,
    list_dashboard_sensors,
    UNSET,
    update_dashboard_sensor_configuration,
)
from app.measurement_ingestion import ingest_measurement_upload


HistoryPeriod = Literal["24h", "7d", "30d"]

PERIOD_SECONDS: dict[HistoryPeriod, int] = {
    "24h": 24 * 60 * 60,
    "7d": 7 * 24 * 60 * 60,
    "30d": 30 * 24 * 60 * 60,
}
RAW_HISTORY_RANGE_LIMIT_SECONDS = 30 * 24 * 60 * 60

APP_DIR = Path(__file__).resolve().parent
TEMPLATES_DIR = APP_DIR / "templates"
STATIC_DIR = APP_DIR / "static"


def calculate_history_window(period: HistoryPeriod, now: int | None = None) -> tuple[int, int]:
    current_time = int(time.time()) if now is None else now
    return current_time - PERIOD_SECONDS[period], current_time


def resolve_history_request(
    *,
    period: HistoryPeriod | None,
    measured_from: int | None,
    measured_to: int | None,
) -> tuple[HistoryPeriod | None, int, int]:
    has_period = period is not None
    has_from = measured_from is not None
    has_to = measured_to is not None

    if has_period:
        if has_from or has_to:
            raise HTTPException(
                status_code=422,
                detail="Specify either period or from/to, not both",
            )

        history_from, history_to = calculate_history_window(period)
        return period, history_from, history_to

    if has_from != has_to:
        raise HTTPException(
            status_code=422,
            detail="Both from and to must be provided together",
        )

    if not has_from:
        raise HTTPException(
            status_code=422,
            detail="Specify either period or from/to",
        )

    assert measured_from is not None
    assert measured_to is not None

    if measured_from >= measured_to:
        raise HTTPException(
            status_code=422,
            detail="from must be less than to",
        )

    return None, measured_from, measured_to


def should_return_raw_history(*, period: HistoryPeriod | None, history_from: int, history_to: int) -> bool:
    if period is not None:
        return True

    return history_to - history_from <= RAW_HISTORY_RANGE_LIMIT_SECONDS


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    initialize_database(app.state.database_path)
    yield


def create_app(database_path: str | Path | None = None) -> FastAPI:
    app = FastAPI(title="Environment Sensor Server", lifespan=lifespan)
    app.state.database_path = database_path
    templates = Jinja2Templates(directory=str(TEMPLATES_DIR))

    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

    @app.get("/", response_class=HTMLResponse)
    def dashboard_home(request: Request) -> HTMLResponse:
        return templates.TemplateResponse(
            request,
            "dashboard.html",
            {
                "page_title": "Sensorar",
            },
        )

    @app.get("/sensors/{device_id}", response_class=HTMLResponse)
    def dashboard_sensor_detail_page(device_id: str, request: Request) -> HTMLResponse:
        return templates.TemplateResponse(
            request,
            "sensor_detail.html",
            {
                "page_title": "Sensor",
                "device_id": device_id,
            },
        )

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

    @app.patch(
        "/api/dashboard/sensors/{device_id}/configuration",
        response_model=DashboardSensorConfigurationPatchResponse,
    )
    def patch_dashboard_sensor_configuration(
        device_id: str,
        patch_request: DashboardSensorConfigurationPatchRequest,
        request: Request,
    ) -> DashboardSensorConfigurationPatchResponse:
        try:
            configuration_record = update_dashboard_sensor_configuration(
                device_id,
                device_name=(
                    patch_request.device_name
                    if "device_name" in patch_request.model_fields_set
                    else UNSET
                ),
                measurement_interval_seconds=(
                    patch_request.measurement_interval_seconds
                    if "measurement_interval_seconds" in patch_request.model_fields_set
                    else UNSET
                ),
                database_path=request.app.state.database_path,
            )
        except sqlite3.DatabaseError as error:
            raise HTTPException(status_code=500, detail="Internal Server Error") from error

        if configuration_record is None:
            raise HTTPException(status_code=404, detail="Not Found")

        return DashboardSensorConfigurationPatchResponse(
            device_id=configuration_record.device_id,
            device_name=configuration_record.device_name,
            measurement_interval_seconds=configuration_record.measurement_interval_seconds,
            config_version=configuration_record.config_version,
            reported_config_version=configuration_record.reported_config_version,
            config_sync_state=configuration_record.config_sync_state,
        )

    @app.get(
        "/api/dashboard/sensors/{device_id}/history",
        response_model=DashboardSensorHistoryResponse,
        response_model_by_alias=True,
        response_model_exclude_none=True,
    )
    def get_dashboard_sensor_history(
        device_id: str,
        request: Request,
        period: HistoryPeriod | None = Query(default=None),
        measured_from: int | None = Query(default=None, alias="from"),
        measured_to: int | None = Query(default=None, alias="to"),
    ) -> DashboardSensorHistoryResponse:
        selected_period, history_from, history_to = resolve_history_request(
            period=period,
            measured_from=measured_from,
            measured_to=measured_to,
        )
        use_raw_history = should_return_raw_history(
            period=selected_period,
            history_from=history_from,
            history_to=history_to,
        )

        try:
            if not device_exists(device_id, database_path=request.app.state.database_path):
                raise HTTPException(status_code=404, detail="Not Found")

            if use_raw_history:
                point_records = list_dashboard_sensor_history(
                    device_id,
                    measured_from=history_from,
                    measured_to=history_to,
                    database_path=request.app.state.database_path,
                )
            else:
                point_records = list_dashboard_sensor_history_by_day(
                    device_id,
                    measured_from=history_from,
                    measured_to=history_to,
                    database_path=request.app.state.database_path,
                )
        except sqlite3.DatabaseError as error:
            raise HTTPException(status_code=500, detail="Internal Server Error") from error

        if use_raw_history:
            return DashboardSensorHistoryRawResponse(
                device_id=device_id,
                resolution="raw",
                period=selected_period,
                from_=history_from,
                to=history_to,
                points=[
                    DashboardSensorHistoryPoint(
                        sequence=point_record.sequence,
                        measured_at=point_record.measured_at,
                        timestamp_valid=point_record.timestamp_valid,
                        temperature_c=point_record.temperature_c,
                        humidity_percent=point_record.humidity_percent,
                        pressure_hpa=point_record.pressure_hpa,
                    )
                    for point_record in point_records
                ],
            )

        return DashboardSensorHistoryDayResponse(
            device_id=device_id,
            resolution="day",
            from_=history_from,
            to=history_to,
            points=[
                DashboardSensorHistoryDayPoint(
                    period_start=point_record.period_start,
                    sample_count=point_record.sample_count,
                    temperature_min_c=point_record.temperature_min_c,
                    temperature_avg_c=point_record.temperature_avg_c,
                    temperature_max_c=point_record.temperature_max_c,
                    humidity_min_percent=point_record.humidity_min_percent,
                    humidity_avg_percent=point_record.humidity_avg_percent,
                    humidity_max_percent=point_record.humidity_max_percent,
                    pressure_min_hpa=point_record.pressure_min_hpa,
                    pressure_avg_hpa=point_record.pressure_avg_hpa,
                    pressure_max_hpa=point_record.pressure_max_hpa,
                )
                for point_record in point_records
            ],
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