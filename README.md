# Environment Sensor Server

Server application for receiving, storing and displaying measurements from environment sensor devices.

The application is intended to run on a Raspberry Pi and uses:

- Python
- FastAPI
- Uvicorn
- SQLite

The sensor/server API contract is documented in [`docs/api-v1.md`](docs/api-v1.md).

The current repository includes:

- a FastAPI ingestion API for ESP32 measurement uploads;
- SQLite persistence and schema initialization for local runtime data;
- dashboard JSON APIs for sensor overview, detail, history, and configuration updates;
- server-rendered dashboard pages using Jinja2 templates;
- Bootstrap 5, Bootstrap Icons, vanilla JavaScript, and Highcharts loaded from CDNs;
- development-only demo data SQL scripts for local dashboard work;
- a pytest suite covering API, database, dashboard, and demo tooling behavior.

## Current status

The project is under active development.

Initial goals:

- receive measurement batches from sensor devices;
- store measurements in SQLite;
- handle duplicate uploads safely;
- acknowledge persisted measurements;
- return server time and device configuration;
- provide a responsive web interface for historical sensor data and device configuration.

## Development environment

Development is currently done in Ubuntu under WSL2.

The same application will later run on Raspberry Pi OS, giving the local development and production environments a similar Linux-based setup.

## Requirements

- Python 3
- Python `venv`
- Git

On Ubuntu / WSL:

```bash
sudo apt update
sudo apt install python3 python3-venv python3-pip git
```

## Clone the repository

```bash
git clone https://github.com/dingsoyr/environment-sensor-server.git
cd environment-sensor-server
```

## Create a virtual environment

```bash
python3 -m venv .venv
```

Activate it:

```bash
source .venv/bin/activate
```

The shell prompt should now indicate that `.venv` is active.

## Install dependencies

```bash
pip install -r requirements.txt
```

## Run the development server

With the virtual environment activated:

```bash
uvicorn app.main:app --reload
```

The server will be available at:

```text
http://127.0.0.1:8000
```

Dashboard home page:

```text
http://127.0.0.1:8000/
```

Health endpoint:

```text
http://127.0.0.1:8000/health
```

Expected response:

```json
{
  "status": "ok"
}
```

FastAPI automatically provides interactive API documentation at:

```text
http://127.0.0.1:8000/docs
```

## WSL2 network access for local devices

The default development setup above is enough when you only access the server from the same machine.

If you want to reach the FastAPI development server from other devices on your local network, such as ESP32 devices or mobile phones, use the manual setup below.

This is a development-only setup for WSL2 and is not the final Raspberry Pi deployment configuration.

### 1. Uvicorn must listen on all interfaces

Start the development server with:

```bash
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

The `0.0.0.0` value is only the bind address used by Uvicorn inside WSL.

Clients must not use `http://0.0.0.0:8000`. Use the Windows PC LAN IP when connecting from ESP32 devices, phones, or other computers.

### 2. WSL2 mirrored networking

On Windows, create or edit:

```text
%USERPROFILE%\.wslconfig
```

with:

```ini
[wsl2]
networkingMode=mirrored

[experimental]
hostAddressLoopback=true
```

After changing `.wslconfig`, restart WSL from PowerShell:

```powershell
wsl --shutdown
```

Then start Ubuntu / WSL again.

### 3. Hyper-V firewall rule

With mirrored networking enabled, inbound traffic may still be blocked because the default Hyper-V inbound policy for WSL is typically `Block`.

From an elevated PowerShell, inspect the current WSL Hyper-V firewall policy:

```powershell
Get-NetFirewallHyperVVMSetting -PolicyStore ActiveStore -Name '{40E0AC32-46A5-438A-A0B2-2B479E8F2E90}'
```

To allow inbound TCP traffic to the development server on port 8000, add this rule:

```powershell
New-NetFirewallHyperVRule `
  -Name "WSL-Uvicorn-8000" `
  -DisplayName "WSL Uvicorn 8000" `
  -Direction Inbound `
  -VMCreatorId '{40E0AC32-46A5-438A-A0B2-2B479E8F2E90}' `
  -Protocol TCP `
  -LocalPorts 8000
```

This keeps the default inbound policy blocked and only opens TCP port `8000` for the development server.

### 4. Verify access

Inside WSL:

```bash
ss -ltnp | grep 8000
curl http://127.0.0.1:8000/health
```

From Windows:

```powershell
curl.exe http://<WINDOWS-LAN-IP>:8000/health
```

From another device on the same Wi-Fi, open:

```text
http://<WINDOWS-LAN-IP>:8000/health
```

Expected response:

```text
{"status":"ok"}
```

### 5. Development server address

During development, ESP32 devices should send measurements to the Windows PC LAN IP, for example:

```text
http://192.168.x.x:8000/api/v1/measurements
```

Do not treat that example IP as a permanent production address.

- `localhost` only works on the same machine.
- ESP32 and mobile clients must use the PC's LAN IP.
- The LAN IP may change if DHCP assigns a new address.
- This is for development in WSL2 only, not for the final Raspberry Pi deployment.

## Run tests

```bash
.venv/bin/python -m pytest
```

The pytest suite currently covers:

- database helpers and schema behavior;
- measurement ingestion behavior;
- API v1 endpoint behavior;
- dashboard JSON endpoints;
- dashboard HTML shells and static asset wiring;
- dashboard configuration sync behavior;
- demo SQL scripts.

Tests use isolated temporary databases and must not depend on the runtime SQLite database.

Physical ESP32 or other hardware integration testing is outside pytest.

The current suite may emit an existing upstream FastAPI/Starlette TestClient deprecation warning related to `httpx`. Treat that as a warning, not a project test failure.

## Battery persistence

The latest reported battery state remains stored on the `devices` row in `battery_voltage` and `battery_percent` for current dashboard status.

Battery values are also stored historically per measurement in the `measurements` table when the device upload includes them, so battery history can be queried and charted alongside other measurement history.

The project does not yet provide database migrations. After schema changes during development, recreate the local development database instead of upgrading an existing one.

## API contract

The version 1 sensor API is documented in:

`docs/api-v1.md`

## Dashboard history API

The dashboard history endpoint is:

```text
GET /api/dashboard/sensors/{device_id}/history
```

The request must use exactly one query mode:

- `period=24h|7d|30d`
- `from=<unix>&to=<unix>`

The two modes are mutually exclusive. The endpoint returns `422` for ambiguous or incomplete combinations such as:

- `period` together with `from` or `to`
- `from` without `to`
- `to` without `from`
- `from >= to`

All timestamps use Unix time in UTC. Range filters use half-open interval semantics:

```text
[from, to)
```

meaning `measured_at >= from` and `measured_at < to`.

Response payloads include a `resolution` field describing the returned point type:

- `resolution="raw"` for raw measurements
- `resolution="day"` for UTC daily aggregates

Resolution rules:

- `period=24h`, `period=7d`, and `period=30d` always return raw measurements
- explicit `from`/`to` ranges of `30 * 24 * 60 * 60` seconds or less return raw measurements
- explicit `from`/`to` ranges longer than that return daily aggregates

Daily aggregation uses UTC calendar-day buckets without expanding the requested interval to whole days. Each day point includes:

- `period_start`
- `sample_count`
- `temperature_min_c`, `temperature_avg_c`, `temperature_max_c`
- `humidity_min_percent`, `humidity_avg_percent`, `humidity_max_percent`
- `pressure_min_hpa`, `pressure_avg_hpa`, `pressure_max_hpa`

Days with no measurements are omitted.

```text
docs/api-v1.md
```

The main sensor upload endpoint will be:

```http
POST /api/v1/measurements
```

A measurement is uniquely identified by:

```text
(device_id, sequence)
```

Repeated uploads must not create duplicate measurements.

## Database

SQLite is used for persistent storage.

By default, the runtime database path is `data/environment.db`.

The `data/` directory is created automatically if it does not already exist.

At application startup, the server initializes the database schema for the configured database path.

You can override the default path with the `ENVIRONMENT_SENSOR_DATABASE_PATH` environment variable.

New databases receive the current schema objects defined by the application, including required tables and indexes.

Existing databases are not automatically migrated when the schema changes. The current `initialize_database()` behavior creates missing schema objects for new databases, but it is not a general migration engine.

During development, schema changes may require manual SQL changes or recreating the local database. No migration framework currently exists.

Runtime database files are intentionally excluded from Git.

The server source code must be able to create the required database schema on a new installation.

## Dashboard

The current dashboard surface includes:

- `/` for the dashboard home page;
- `/sensors/{device_id}` for a sensor detail page;
- history views for `24h`, `7d`, and `30d`;
- dashboard configuration editing for sensor name and measurement interval;
- configuration sync states of `synced`, `waiting_for_sensor`, and `device_ahead`.
- derived contact health from `last_seen_at` and configured measurement interval, kept separate from configuration synchronization.

The HTML page routes serve thin shells. Current dashboard state is loaded through dashboard JSON APIs.

## Frontend stack

The dashboard uses:

- Jinja2 templates;
- Bootstrap 5 from CDN;
- Bootstrap Icons from CDN;
- vanilla JavaScript;
- Highcharts from CDN.

## Demo dashboard data

Development-only SQL scripts are available for populating a local database with synthetic historical measurements for dashboard work.

Do not run these scripts against a production database.

The `sqlite3` CLI is required to run the scripts manually.

The application schema must already exist before running them. On a fresh clone, starting the server once is a simple way to initialize the local database.

The scripts only target the dedicated demo device `sensor-demo-001` with device name `Demo sensor`.

Script paths:

- `scripts/create_demo_data.sql`
- `scripts/delete_demo_data.sql`

Create demo data in the local development database:

```bash
sqlite3 data/environment.db < scripts/create_demo_data.sql
```

Remove the demo device and its measurements:

```bash
sqlite3 data/environment.db < scripts/delete_demo_data.sql
```

Verify the inserted measurement count:

```sql
SELECT device_id, COUNT(*)
FROM measurements
WHERE device_id = 'sensor-demo-001'
GROUP BY device_id;
```

The create script regenerates exactly 17,520 hourly measurements for the demo device, spanning approximately 730 days (about 2 years), and remains useful for current 24h / 7d / 30d dashboard views as well as future long-range history development. The dataset now also includes deterministic synthetic historical battery data with several discharge/reset cycles so the battery history visualization is easy to test; this is demo data only and not a calibrated battery-life model.

## Project structure

Current structure:

```text
environment-sensor-server/
├── app/
│   ├── main.py                    # FastAPI app, routes, lifespan wiring
│   ├── database.py                # SQLite schema, queries, dashboard config persistence
│   ├── measurement_ingestion.py   # Measurement ingestion transaction behavior
│   ├── api_v1_models.py           # ESP32 API request/response models
│   ├── dashboard_models.py        # Dashboard API models
│   ├── templates/                 # Server-rendered HTML templates
│   └── static/                    # Dashboard CSS and JavaScript
├── docs/
│   └── api-v1.md                  # API v1 contract
├── scripts/                       # Development/demo SQL helpers
├── tests/                         # Pytest suite
├── .gitignore
├── AGENTS.md
├── README.md
└── requirements.txt
```

## Raspberry Pi deployment

The Raspberry Pi deployment is not configured yet.

The intended workflow is:

```text
Development in WSL
        |
        | git push
        v
      GitHub
        |
        | git pull
        v
 Raspberry Pi
        |
        v
 FastAPI / Uvicorn / SQLite
```

Once the application is ready for continuous operation on the Pi, it will be configured as a `systemd` service.

Deployment instructions will be added here when that setup is implemented.

## Development principles

Keep the application simple.

Do not add infrastructure such as Docker, PostgreSQL, Redis or frontend frameworks unless there is a demonstrated need.

API behavior must remain consistent with `docs/api-v1.md`.

See [`AGENTS.md`](AGENTS.md) for the project's development and architecture rules.