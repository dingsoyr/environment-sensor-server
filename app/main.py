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
from app.database import get_device_configuration, initialize_database
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