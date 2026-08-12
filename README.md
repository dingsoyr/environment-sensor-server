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