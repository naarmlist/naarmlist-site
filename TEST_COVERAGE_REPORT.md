# Test Coverage Report

Generated: 2026-08-23

Command run:

```powershell
python -m coverage run --source=app,scripts -m pytest tests
python -m coverage report -m
python -m coverage report -m --format=markdown
```

## Result

```text
58 passed
```

## Application Coverage

```text
Name         Stmts   Miss  Cover   Missing
------------------------------------------
app\app.py     499     28    94%   48-50, 94, 219-220, 252, 271, 288, 307, 342, 357, 548-551, 557, 603, 723, 759, 784-785, 875-877, 920-922, 926
------------------------------------------
TOTAL          499     28    94%
```

## Workflow Coverage Run

```text
Name                   Stmts   Miss  Cover   Missing
----------------------------------------------------
app\app.py               499     28    94%   48-50, 94, 219-220, 252, 271, 288, 307, 342, 357, 548-551, 557, 603, 723, 759, 784-785, 875-877, 920-922, 926
scripts\db_export.py      65     18    72%   30, 51-52, 60, 65-89, 114-121, 125
scripts\db_import.py      92     26    72%   28-36, 61, 66-90, 146, 154-163, 167
----------------------------------------------------
TOTAL                    656     72    89%
```

## Coverage Added

- Public routes: directory pages, detail pages, notes search, event search, add-event form, robots, logout.
- Admin routes: event list ordering, edit form, missing event handling, export data, export download.
- Review workflow: approve, reject, insert new records, update by target, update by lookup.
- Database safety: unknown collections, unapproved fields, dotted keys, operator-like keys, empty payloads, and orphan target edits.
- Existing event and directory behavior: validation, trimming, duplicate prevention, links, calendar, ICS, and access controls.
- Seeded dummy data safety: read-only routes are exercised against populated collections and checked for unintended mutation.
- Database dump scripts: export/import collection mapping, ObjectId restoration, malformed dump rejection, compact JSON output, dotenv loading, and idempotent non-drop imports.

## Test Database Model

The test suite uses `mongomock` through the shared `client` fixture in `tests/conftest.py`.
For each test, the fixture creates a fresh in-memory MongoDB client and assigns its database
to `app.db_override`. The application code already checks `app.db_override` in
`get_db_connection()`, so routes run normally but use the isolated in-memory database instead
of the real configured MongoDB instance.

Tests can safely populate this database with dummy data before calling routes. The data only
exists for that one test and is discarded when the fixture finishes. The database safety tests
use this directly: they seed artists, organisers, venues, events, and pending review rows,
hit public/admin routes, and then assert that collections were either unchanged for read-only
routes or changed only in the expected reviewed ways.
