# AGENTS.md

## Project purpose

This repository contains the server application for the environment sensor system.

The server receives measurements from sensor devices over HTTP, stores them persistently, returns acknowledgements and configuration, and will later provide a simple web interface for viewing historical sensor data and managing devices.

The server is intended to run on a Raspberry Pi.

## Technology

Use:

- Python 3
- FastAPI
- Uvicorn
- SQLite
- pytest
- httpx for API tests

Keep the technology stack small.

Do not introduce Docker, PostgreSQL, Redis, Node.js, React, message brokers, ORMs, background workers, or other infrastructure unless there is a demonstrated need and the change has been explicitly discussed first.

## API contract

`docs/api-v1.md` is the authoritative contract between sensor devices and the server.

Do not change API field names, acknowledgement semantics, request structure, or response structure without explicitly updating the contract and explaining the compatibility implications.

The initial endpoint is:

`POST /api/v1/measurements`

## Measurement identity and idempotency

A measurement is uniquely identified by:

`(device_id, sequence)`

Repeated uploads of the same measurement must not create duplicate records.

The database must enforce this invariant where practical.

Acknowledgements must only be returned for measurements that the server has safely persisted.

## Data model

Keep device state separate from historical measurements.

The initial conceptual model is:

- `devices`
  - device identity
  - human-readable name
  - configuration
  - firmware version
  - last seen
  - current status such as RSSI and battery information

- `measurements`
  - device reference
  - sequence
  - timestamp
  - timestamp validity
  - temperature
  - humidity
  - pressure

Do not duplicate human-readable device names into every historical measurement.

The design should remain reasonably extensible to other sensor types later, but do not over-engineer for hypothetical requirements.

## Database

Use SQLite.

The runtime database file must not be committed to Git.

Database schema creation must be reproducible from source code.

Schema changes should be handled deliberately. Do not silently destroy existing data.

During early development, simple schema initialization is acceptable. Introduce a migration framework only when there is a real need.

## Code structure

Keep modules small and focused.

Prefer clear functions and simple data structures over unnecessary classes or abstractions.

Keep FastAPI request handling, database access, and domain logic separated when doing so improves testability and clarity.

Do not create layers merely for architectural purity.

## Testing

Automated tests are required for server behavior.

At minimum, new API behavior should have tests covering:

- successful requests
- invalid requests
- duplicate measurement uploads
- acknowledgement behavior
- persistence behavior

Tests must not depend on the production SQLite database.

Use temporary or isolated test databases.

Run the test suite after meaningful changes.

## Development workflow

Before modifying code:

1. inspect the existing implementation;
2. inspect relevant tests;
3. inspect `docs/api-v1.md` when working on API behavior.

Make the smallest change necessary to satisfy the task.

Do not redesign or refactor unrelated code.

Do not change behavior that is outside the requested scope.

## Security and configuration

Do not commit secrets, passwords, API keys, local `.env` files, or runtime databases.

Configuration that varies by environment should be externalized when needed.

The initial server runs on a trusted local network. Do not add authentication or HTTPS complexity until it is explicitly required.

## Frontend

A simple responsive web interface will be added later.

The initial direction is:

- server-rendered HTML
- responsive/mobile-first CSS
- lightweight JavaScript
- Highcharts for historical graphs

Do not introduce a frontend framework such as React unless explicitly requested.

## Validation

When completing a task, report:

- files changed;
- behavior added or changed;
- tests added or updated;
- test command used;
- test result;
- any database or compatibility implications.

Do not claim hardware or Raspberry Pi behavior was physically tested unless it actually was.