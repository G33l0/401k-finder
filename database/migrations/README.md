# Database migrations

Schema migrations are defined in code, in
[`app/database/schema.py`](../../app/database/schema.py), as an ordered list of
`MigrationStep` objects guarded by a `schema_version` table. The application
applies any outstanding steps on start-up, so there is nothing to run by hand.

This folder holds SQL snapshots of each schema version for reference — useful
when inspecting a database with an external tool, or when working out what
changed between two versions.

## Why not Alembic

Alembic solves a problem this application does not have. The database here is a
local, single-user cache of public files: it is never shared, never migrated in
place across a fleet, and can always be rebuilt from source by re-importing.
That makes a linear `schema_version` counter sufficient, and it removes a
dependency and a migration-history directory from a Windows build that is
already large.

If the database ever becomes something users share or that outlives its source
data, that trade-off changes and Alembic becomes the right answer.

## Regenerating a snapshot

```bash
python -c "
from app.database.engine import get_engine
from app.database.init_db import initialize_database
from sqlalchemy import text
initialize_database()
with get_engine().connect() as c:
    rows = c.execute(text(
        \"SELECT sql FROM sqlite_master WHERE sql IS NOT NULL ORDER BY type DESC, name\"
    ))
    print(';\n\n'.join(r[0] for r in rows) + ';')
" > database/migrations/schema_v4.sql
```

## If the schema is ahead of the application

Opening a database written by a newer build raises a `DatabaseError` naming both
versions rather than migrating backwards. Upgrade the application, or delete the
database file and re-import — `401k-finder reset` does the latter.
