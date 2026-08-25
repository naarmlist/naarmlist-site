# Naarm List

A listing service of gigs and events in Melbourne (Naarm)

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

### Instructions

This setup uses `docker-compose` to spin up the mongo backend and web frontend

1. **Build and run the services:**

    Before running you will need a `.env` file set up. You can copy `.env.example` or use
    one of the scripts above.

    ```bash
    $ cat .env

    DB_NAME="gigsdb"
    DB_URL="mongodb://db:27017/"

    # for db seed script only
    MONGO_HOST="db"
    MONGO_PORT="27017"

    ADMIN_PASS="pw1234"
    ADMIN_USER="user"
    ```

2. Now you can bring it up using docker

    ```bash
    docker-compose up --build
    ```

3. **Access the app** by visiting `http://localhost:8000`.

4. **(OPTIONAL)** Database Seeding

    A script `seed_db.sh` is provided to seed the MongoDB database from a JSON backup file.

    You can attempt to run the it with all env vars sourced from your `env` using `docker-compose --profile seed up seed_db`

    This script can also be used to restore the database from the latest exported backup file in the `db_data/` directory.

    Backup files are created in the admin dashboard. Scroll to the bottom and select 'Export Database' or accessing the link directly e.g. `http://localhost:8000/admin/export_db` will automatically start an export and download.

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

It exports from the running MongoDB Compose service into `db_data/naarm_list_backup_YYYYmmdd_HHMMSS.json`.
It does not need the newer Python import/export helpers to exist on that server.
