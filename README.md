# Naarm List

A listing service of gigs and events in Melbourne (Naarm)

### Instructions

This setup uses `docker-compose` to spin up the mongo backend and web frontend

1. **Build and run the services:**

    Before running you will need a `.env` file set up.

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
