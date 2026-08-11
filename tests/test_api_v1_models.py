import pytest
from pydantic import ValidationError

from app.api_v1_models import MeasurementUploadRequest, MeasurementUploadResponse


def make_request_payload() -> dict:
    return {
        "api_version": 1,
        "device_id": "sensor-d8cbb0",
        "firmware_version": "0.1.0",
        "config_version": 2,
        "status": {
            "rssi_dbm": -61,
            "battery_voltage": 3.92,
            "battery_percent": 74,
        },
        "measurements": [
            {
                "sequence": 721,
                "measured_at": 1_786_300_052,
                "timestamp_valid": True,
                "temperature_c": 19.01,
                "humidity_percent": 53.49,
                "pressure_hpa": 990.79,
            },
            {
                "sequence": 722,
                "measured_at": 1_786_303_652,
                "timestamp_valid": True,
                "temperature_c": 18.94,
                "humidity_percent": 53.80,
                "pressure_hpa": 990.83,
            },
        ],
    }


def make_response_payload() -> dict:
    return {
        "api_version": 1,
        "acknowledged_through": 722,
        "server_time": 1_786_303_653,
        "config_version": 2,
    }


def test_request_example_from_contract_is_accepted() -> None:
    model = MeasurementUploadRequest.model_validate(make_request_payload())

    assert model.api_version == 1
    assert len(model.measurements) == 2


def test_request_without_battery_fields_is_accepted() -> None:
    payload = make_request_payload()
    payload["status"] = {"rssi_dbm": -61}

    model = MeasurementUploadRequest.model_validate(payload)

    assert model.status.battery_voltage is None
    assert model.status.battery_percent is None


def test_api_version_other_than_one_is_rejected() -> None:
    payload = make_request_payload()
    payload["api_version"] = 2

    with pytest.raises(ValidationError):
        MeasurementUploadRequest.model_validate(payload)


def test_empty_device_id_is_rejected() -> None:
    payload = make_request_payload()
    payload["device_id"] = ""

    with pytest.raises(ValidationError):
        MeasurementUploadRequest.model_validate(payload)


def test_empty_firmware_version_is_rejected() -> None:
    payload = make_request_payload()
    payload["firmware_version"] = ""

    with pytest.raises(ValidationError):
        MeasurementUploadRequest.model_validate(payload)


def test_negative_config_version_is_rejected() -> None:
    payload = make_request_payload()
    payload["config_version"] = -1

    with pytest.raises(ValidationError):
        MeasurementUploadRequest.model_validate(payload)


def test_empty_measurements_array_is_rejected() -> None:
    payload = make_request_payload()
    payload["measurements"] = []

    with pytest.raises(ValidationError):
        MeasurementUploadRequest.model_validate(payload)


def test_negative_sequence_is_rejected() -> None:
    payload = make_request_payload()
    payload["measurements"][0]["sequence"] = -1

    with pytest.raises(ValidationError):
        MeasurementUploadRequest.model_validate(payload)


@pytest.mark.parametrize("battery_percent", [0, 100])
def test_battery_percent_boundary_values_are_accepted(battery_percent: int) -> None:
    payload = make_request_payload()
    payload["status"]["battery_percent"] = battery_percent

    model = MeasurementUploadRequest.model_validate(payload)

    assert model.status.battery_percent == battery_percent


@pytest.mark.parametrize("battery_percent", [-1, 101])
def test_battery_percent_out_of_range_is_rejected(battery_percent: int) -> None:
    payload = make_request_payload()
    payload["status"]["battery_percent"] = battery_percent

    with pytest.raises(ValidationError):
        MeasurementUploadRequest.model_validate(payload)


def test_response_without_configuration_is_accepted() -> None:
    model = MeasurementUploadResponse.model_validate(make_response_payload())

    assert model.configuration is None


def test_response_with_configuration_is_accepted() -> None:
    payload = make_response_payload()
    payload["config_version"] = 3
    payload["configuration"] = {
        "device_name": "Utesensor nord",
        "measurement_interval_seconds": 3600,
    }

    model = MeasurementUploadResponse.model_validate(payload)

    assert model.configuration is not None
    assert model.configuration.measurement_interval_seconds == 3600


@pytest.mark.parametrize("interval", [0, -1])
def test_response_configuration_interval_must_be_greater_than_zero(interval: int) -> None:
    payload = make_response_payload()
    payload["configuration"] = {
        "device_name": "Utesensor nord",
        "measurement_interval_seconds": interval,
    }

    with pytest.raises(ValidationError):
        MeasurementUploadResponse.model_validate(payload)