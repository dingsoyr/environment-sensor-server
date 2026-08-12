# Copilot instructions

Follow `AGENTS.md` and `docs/api-v1.md`.

This is a small Raspberry Pi server application for environment sensors.

## General approach

Before editing:

1. inspect the relevant existing files;
2. inspect existing tests;
3. read `docs/api-v1.md` before changing API behavior.

Make small, focused changes.

Do not refactor unrelated code.

Do not introduce new frameworks, dependencies, patterns, or infrastructure unless they are necessary for the requested task.

Prefer straightforward Python that is easy to understand and maintain.

Keep route handlers in `app/main.py` thin.

Put ingestion behavior in `app/measurement_ingestion.py`.

Put SQLite connection, schema, query, and configuration persistence behavior in `app/database.py`.

Keep API request and response models in the appropriate model modules.

## Technology constraints

Use the existing stack:

- Python
- FastAPI
- Uvicorn
- SQLite
- pytest
- httpx

Do not introduce:

- Docker
- PostgreSQL
- Redis
- SQLAlchemy or another ORM unless explicitly requested
- React
- Node.js build tooling
- MQTT
- background job systems

without explicit approval.

Use Python's built-in `sqlite3` module unless a later requirement clearly justifies another database abstraction.

Preserve the current frontend stack:

- Jinja2
- Bootstrap
- Bootstrap Icons
- vanilla JavaScript
- Highcharts

Do not introduce React, Vue, Svelte, jQuery, npm build tooling, or other frontend frameworks unless explicitly requested.

## API rules

Treat `docs/api-v1.md` as authoritative.

Do not silently modify the HTTP contract.

A measurement is uniquely identified by:

`(device_id, sequence)`

Measurement ingestion must be idempotent.

Do not acknowledge measurements before they are safely persisted.

Preserve configuration ownership semantics:

- the server owns `config_version`;
- the device reports `reported_config_version` through ingestion;
- dashboard PATCH behavior must not update `reported_config_version`;
- ingestion must not overwrite an existing server-owned `config_version`.

Preserve current dashboard/API separation: page shells stay thin, and dashboard state is loaded through the existing dashboard APIs.

Do not casually change API v1 wire semantics.

Schema changes must not invent automatic migration behavior. Update schema initialization for new databases when appropriate, and handle existing development databases manually only when the task explicitly requires it.

## Testing

Add or update automated tests for behavior changes.

Use isolated temporary databases for tests.

Do not make tests depend on an existing local runtime database.

Run `.venv/bin/python -m pytest` for repository changes unless the task is strictly documentation-only.

Do not treat the current upstream FastAPI/Starlette TestClient deprecation warning related to `httpx` as a project failure.

After changes, run the relevant tests and report the result.

## Style

Prefer:

- explicit names;
- type hints where useful;
- small functions;
- simple modules;
- clear validation;
- predictable error handling.

Avoid:

- unnecessary classes;
- generic repository/service/factory abstractions with no immediate benefit;
- premature optimization;
- speculative extensibility.

Avoid new dependencies unless they are necessary and justified.

## Completion report

After implementing a task, summarize:

- files changed;
- what changed;
- tests run and results;
- database/schema implications;
- any assumptions or unresolved questions.