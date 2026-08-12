from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import time

from app.api_v1_models import MeasurementUploadRequest
from app.database import connect_database


@dataclass(frozen=True)
class MeasurementIngestionResult:
    acknowledged_through: int
    server_time: int
    config_version: int


def ingest_measurement_upload(
    request: MeasurementUploadRequest,
    database_path: str | Path | None = None,
) -> MeasurementIngestionResult:
    server_time = int(time.time())
    uploaded_sequences = {measurement.sequence for measurement in request.measurements}
    min_sequence = min(uploaded_sequences)
    max_sequence = max(uploaded_sequences)

    with connect_database(database_path) as connection:
        connection.execute(
            """
            INSERT INTO devices (
                device_id,
                device_name,
                firmware_version,
                config_version,
                reported_config_version,
                last_seen_at,
                rssi_dbm,
                battery_voltage,
                battery_percent
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(device_id) DO UPDATE SET
                firmware_version = excluded.firmware_version,
                reported_config_version = excluded.reported_config_version,
                last_seen_at = excluded.last_seen_at,
                rssi_dbm = excluded.rssi_dbm,
                battery_voltage = excluded.battery_voltage,
                battery_percent = excluded.battery_percent
            """,
            (
                request.device_id,
                request.device_id,
                request.firmware_version,
                request.config_version,
                request.config_version,
                server_time,
                request.status.rssi_dbm,
                request.status.battery_voltage,
                request.status.battery_percent,
            ),
        )

        connection.executemany(
            """
            INSERT INTO measurements (
                device_id,
                sequence,
                measured_at,
                timestamp_valid,
                temperature_c,
                humidity_percent,
                pressure_hpa
            )
            VALUES (?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(device_id, sequence) DO NOTHING
            """,
            [
                (
                    request.device_id,
                    measurement.sequence,
                    measurement.measured_at,
                    int(measurement.timestamp_valid),
                    measurement.temperature_c,
                    measurement.humidity_percent,
                    measurement.pressure_hpa,
                )
                for measurement in request.measurements
            ],
        )

        persisted_rows = connection.execute(
            """
            SELECT sequence
            FROM measurements
            WHERE device_id = ?
              AND sequence BETWEEN ? AND ?
            """,
            (request.device_id, min_sequence, max_sequence),
        ).fetchall()
        persisted_sequences = {row[0] for row in persisted_rows}

        acknowledged_through = min_sequence
        while acknowledged_through + 1 in persisted_sequences:
            acknowledged_through += 1

        config_version = connection.execute(
            "SELECT config_version FROM devices WHERE device_id = ?",
            (request.device_id,),
        ).fetchone()[0]

    return MeasurementIngestionResult(
        acknowledged_through=acknowledged_through,
        server_time=server_time,
        config_version=config_version,
    )