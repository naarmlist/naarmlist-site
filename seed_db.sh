#!/bin/bash
# seed_db.sh - Seed MongoDB from a backup JSON file

set -e

# Default values
BACKUP_DIR="db_data"
DB_NAME=${DB_NAME:-"gigsdb"}
# Use 'db' as default host for Docker Compose
MONGO_HOST=${MONGO_HOST:-"db"}
MONGO_PORT=${MONGO_PORT:-"27017"}

# Parse args
CONFIRM="yes"
BACKUP_FILE=""
AUTO_CONFIRM="no"

usage() {
  echo "Usage: $0 [-y] [backup_file.json]"
  echo "  -y                Skip confirmation prompt (dangerous!)"
  echo "  backup_file.json  Path to backup JSON file (default: latest in $BACKUP_DIR)"
  exit 1
}

# Find latest backup file by yymmdd in filename
default_backup_file() {
  # List files, extract the 8-digit date, sort, pick latest date, then pick the latest file for that date
  files=$(ls "$BACKUP_DIR"/naarm_list_backup_*.json 2>/dev/null)
  latest_date=$(echo "$files" | grep -oE 'backup_([0-9]{8})_[0-9]{6}\.json' | grep -oE '[0-9]{8}' | sort -nr | head -n1)
  echo "$files" | grep "$latest_date" | sort | tail -n1
}


# Parse options
while [[ $# -gt 0 ]]; do
  case $1 in
    -y)
      AUTO_CONFIRM="yes"
      shift
      ;;
    -h|--help)
      usage
      ;;
    *)
      BACKUP_FILE="$1"
      shift
      ;;
  esac
done

if [ -z "$BACKUP_FILE" ]; then
  BACKUP_FILE=$(default_backup_file)
fi

if [ ! -f "$BACKUP_FILE" ]; then
  echo "Backup file not found: $BACKUP_FILE"
  exit 1
fi

# Use DB_NAME from .env if set
if [ -n "$DB_NAME" ]; then
  DEFAULT_DB="$DB_NAME"
fi

if [ "$AUTO_CONFIRM" != "yes" ]; then
  echo "WARNING: This will overwrite data in the MongoDB database ($DEFAULT_DB)!"
  read -p "Are you sure you want to continue? [y/N]: " CONFIRM
  if [[ ! "$CONFIRM" =~ ^[Yy]$ ]]; then
    echo "Aborted."
    exit 1
  fi
fi


# Extract collections from JSON (assumes top-level keys are collection names)
COLLECTIONS=$(jq -r 'keys[]' "$BACKUP_FILE")
echo "Seeding database: $DEFAULT_DB from backup file: $BACKUP_FILE" to "$MONGO_HOST:$MONGO_PORT"

for COL in $COLLECTIONS; do
  echo "Importing collection: $COL"
  jq ".\"$COL\"" "$BACKUP_FILE" > "/tmp/${COL}.json"
  # Skip import if file is empty array
  if [ "$(cat /tmp/${COL}.json)" = "[]" ]; then
    echo "Skipping $COL: empty collection."
    rm "/tmp/${COL}.json"
    continue
  fi
  mongoimport --host "$MONGO_HOST" --port "$MONGO_PORT" \
    --db "$DEFAULT_DB" --collection "$COL" --drop \
    --file "/tmp/${COL}.json" --jsonArray
  rm "/tmp/${COL}.json"
done

echo "Database seeding complete."
echo "\nSample data from each collection in $DEFAULT_DB:" 

for COL in $COLLECTIONS; do
  echo "\nCollection: $COL (top 5 documents)"
  mongosh --host "$MONGO_HOST" --port "$MONGO_PORT" "$DEFAULT_DB" --quiet --eval "db.getCollection('$COL').find().limit(5).forEach(doc => printjson(doc))"
done
