# Environment Sensor Server

Server application for receiving, storing and displaying measurements from the environment sensor devices.

The application is intended to run on a Raspberry Pi and uses:

- Python
- FastAPI
- Uvicorn
- SQLite

The sensor/server API contract is documented in [`docs/api-v1.md`](docs/api-v1.md).

## Current status

The project is under active development.

Initial goals:

- receive measurement batches from sensor devices;
- store measurements in SQLite;
- handle duplicate uploads safely;
- acknowledge persisted measurements;
- return server time and device configuration;
- later provide a responsive web interface for historical sensor data and device configuration.

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

## Run tests

```bash
pytest
```

Tests should use isolated temporary databases and must not depend on the runtime SQLite database.

## API contract

The version 1 sensor API is documented in:

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

Runtime database files are intentionally excluded from Git.

The server source code must be able to create the required database schema on a new installation.

## Project structure

Current and planned structure:

```text
environment-sensor-server/
├── app/
│   ├── __init__.py
│   └── main.py
├── docs/
│   └── api-v1.md
├── tests/
├── .gitignore
├── AGENTS.md
├── README.md
└── requirements.txt
```

The structure will grow incrementally as database and API functionality is added.

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