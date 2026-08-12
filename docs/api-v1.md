# Environment Sensor API v1

This document defines the HTTP contract between environment sensor devices and the server.

## Endpoint

```http
POST /api/v1/measurements
Content-Type: application/json
```

A device sends one or more buffered measurements in a single request.

The server stores the measurements and returns an acknowledgement together with server time and configuration information.

## Request

Example:

```json
{
  "api_version": 1,
  "device_id": "sensor-d8cbb0",
  "firmware_version": "0.1.0",
  "config_version": 2,
  "status": {
    "rssi_dbm": -61,
    "battery_voltage": 3.92,
    "battery_percent": 74
  },
  "measurements": [
    {
      "sequence": 721,
      "measured_at": 1786300052,
      "timestamp_valid": true,
      "temperature_c": 19.01,
      "humidity_percent": 53.49,
      "pressure_hpa": 990.79
    },
    {
      "sequence": 722,
      "measured_at": 1786303652,
      "timestamp_valid": true,
      "temperature_c": 18.94,
      "humidity_percent": 53.80,
      "pressure_hpa": 990.83
    }
  ]
}
```

## Request fields

### Device

| Field | Type | Required | Description |
| --- | --- | --- | --- |
| `api_version` | integer | yes | API contract version. Must be `1`. |
| `device_id` | string | yes | Stable unique identifier for the device. |
| `firmware_version` | string | yes | Firmware version running on the device. |
| `config_version` | integer | yes | Configuration version currently reported by the device as its applied local configuration version. |
| `status` | object | yes | Current device status at transmission time. |
| `measurements` | array | yes | Buffered measurements to upload. |

### Status

| Field | Type | Required | Description |
| --- | --- | --- | --- |
| `rssi_dbm` | integer | yes | Wi-Fi RSSI at transmission time in dBm. |
| `battery_voltage` | number | no | Battery voltage in volts. |
| `battery_percent` | integer | no | Estimated battery state of charge from 0 to 100 percent. |

Battery fields are optional so devices without battery measurement support can use the same API.

### Measurement

| Field | Type | Required | Description |
| --- | --- | --- | --- |
| `sequence` | integer | yes | Monotonically increasing measurement sequence number for this device. |
| `measured_at` | integer | yes | Measurement timestamp as Unix time in UTC. |
| `timestamp_valid` | boolean | yes | Whether `measured_at` is known to contain a valid synchronized timestamp. |
| `temperature_c` | number | yes | Temperature in degrees Celsius. |
| `humidity_percent` | number | yes | Relative humidity in percent. |
| `pressure_hpa` | number | yes | Atmospheric pressure in hPa. |

## Successful response

```json
{
  "api_version": 1,
  "acknowledged_through": 722,
  "server_time": 1786303653,
  "config_version": 2
}
```

### Response fields

| Field | Type | Description |
| --- | --- | --- |
| `api_version` | integer | API contract version. |
| `acknowledged_through` | integer | Highest contiguous sequence number acknowledged by the server. |
| `server_time` | integer | Current server Unix time in UTC. |
| `config_version` | integer | Current server-owned desired configuration version for the device. |
| `configuration` | object | Optional configuration, present when the server has a newer configuration for the device. |

## Configuration update

If the server has a newer configuration than the device, the response may contain `configuration`.

Example:

```json
{
  "api_version": 1,
  "acknowledged_through": 722,
  "server_time": 1786303653,
  "config_version": 3,
  "configuration": {
    "device_name": "Utesensor nord",
    "measurement_interval_seconds": 3600
  }
}
```

## Acknowledgement semantics

A measurement is uniquely identified by:

```text
(device_id, sequence)
```

The server must treat repeated uploads of the same measurement as idempotent. Receiving the same `(device_id, sequence)` more than once must not create duplicate measurements.

`acknowledged_through` means that the server acknowledges all measurements for the device up to and including that sequence number.

The device may remove acknowledged measurements from its local buffer only after receiving a valid successful response from the server.

The device must retain its buffered measurements if:

- the request times out;
- the server cannot be reached;
- the server returns a non-success status;
- the response is invalid or cannot be parsed.

This allows a device to safely retry an upload after communication failures without losing measurements or creating duplicates.

## Time

All timestamps are Unix timestamps in UTC.

`server_time` allows the device to update or validate its local clock after communicating with the server.

A measurement where `timestamp_valid` is `false` must not be assumed to have an accurate `measured_at` value.

## Configuration

The device sends its current `config_version` with every upload.

In requests, `config_version` means the configuration version the device currently reports as applied locally.

If the server configuration version is newer, the server may include the new configuration in the response.

In responses, `config_version` means the server-owned current desired configuration version for that device.

These values may differ while the device is waiting to receive and apply a newer server configuration.

The `configuration` object is only included when a complete server-managed
configuration is available. If the server has a newer `config_version` but
the configuration is incomplete, for example because `device_name` has not
yet been set, the server omits `configuration` while still returning the
newer server-side `config_version`.

The device must not update its local `config_version` unless a
`configuration` object is received and successfully applied.

The initial configurable fields are:

| Field | Type | Description |
| --- | --- | --- |
| `device_name` | string | Human-readable name for the sensor. |
| `measurement_interval_seconds` | integer | Interval between measurements in seconds. |

Additional configuration fields may be introduced later.

## HTTP status codes

The initial API uses:

| Status | Meaning |
| --- | --- |
| `200 OK` | Measurements accepted and a valid acknowledgement is returned. |
| `400 Bad Request` | Request is invalid. |
| `500 Internal Server Error` | Server failed to process or persist the request. |

Only a valid `200 OK` response containing a valid acknowledgement may cause the device to remove measurements from its local buffer.