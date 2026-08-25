# Naarm List

A listing service of gigs and events in Melbourne (Naarm).

### Python Development Setup

For local Python development, linting, and testing:

1. Create a virtual environment:

    ```bash
    python3 -m venv .venv
    ```

2. Activate the virtual environment:

    ```bash
    source .venv/bin/activate
    ```

3. Install development dependencies:

    ```bash
    pip install -r app/requirements.txt
    ```

4. Run tests and lint checks:

    ```bash
    pytest -v tests
    pylint app tests scripts
    python -m pycodestyle app tests scripts --max-line-length=99
    ```

5. Deactivate when done:

    ```bash
    deactivate
    ```

### Quick Local Site

To start a local test site with MongoDB using the default development settings:

```powershell
.\scripts\start-local-site.ps1
```

On macOS/Linux:

```bash
sh scripts/start-local-site.sh
```

The script creates `.env` from `.env.example` if needed, then runs `docker compose up --build`.
Visit `http://localhost:8000` once the containers are ready.

### Docker Compose

This setup uses `docker-compose` to spin up the MongoDB backend and web frontend.

1. Before running, create a `.env` file. You can copy `.env.example` or use one of the
   scripts above.

    ```bash
    DB_NAME="gigsdb"
    DB_URL="mongodb://db:27017/"

    # for db seed script only
    MONGO_HOST="db"
    MONGO_PORT="27017"

    ADMIN_PASS="pw1234"
    ADMIN_USER="user"
    ```

2. Bring it up with Docker:

    ```bash
    docker-compose up --build
    ```

3. Access the app at `http://localhost:8000`.

4. Optional database seeding:

    A script `seed_db.sh` is provided to seed the MongoDB database from a JSON backup file.

    You can run it with env vars sourced from your `.env` using:

    ```bash
    docker-compose --profile seed up seed_db
    ```

    This script can also restore the database from the latest exported backup file in
    the `db_data/` directory.

    Backup files are created in the admin dashboard. Scroll to the bottom and select
    "Export Database", or open `http://localhost:8000/admin/export_db` directly after
    logging in.

### Database Dumps

Use the Python scripts for portable JSON dump export/import. They read `.env` by default and
fall back to `mongodb://localhost:27017/` and `gigsdb`. If `.env` contains Docker Compose's
`mongodb://db:27017/` host, the scripts map that to `localhost` when run from your terminal.

Export a dump:

```powershell
python scripts\db_export.py
```

Export to a specific file:

```powershell
python scripts\db_export.py --output db_data\manual_backup.json
```

Import or update records from a dump without dropping existing collections:

```powershell
python scripts\db_import.py db_data\manual_backup.json
```

Restore a dump by dropping imported collections first:

```powershell
python scripts\db_import.py db_data\manual_backup.json --drop --yes
```

Both scripts accept `--uri` and `--db` if you need to point at a different MongoDB instance.

If you are on an old server running the `main` branch and only have Docker Compose available,
copy or run the standalone Compose exporter from the directory containing `docker-compose.yml`:

```bash
bash scripts/manual-export-from-compose.sh
```

It exports from the running MongoDB Compose service into
`db_data/naarm_list_backup_YYYYmmdd_HHMMSS.json`. It does not need the newer Python
import/export helpers to exist on that server.
