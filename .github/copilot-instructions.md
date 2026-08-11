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

## API rules

Treat `docs/api-v1.md` as authoritative.

Do not silently modify the HTTP contract.

A measurement is uniquely identified by:

`(device_id, sequence)`

Measurement ingestion must be idempotent.

Do not acknowledge measurements before they are safely persisted.

## Testing

Add or update automated tests for behavior changes.

Use isolated temporary databases for tests.

Do not make tests depend on an existing local runtime database.

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

## Completion report

After implementing a task, summarize:

- files changed;
- what changed;
- tests run and results;
- database/schema implications;
- any assumptions or unresolved questions.