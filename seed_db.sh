#!/bin/bash
# Seed MongoDB from a Naarm List JSON dump.

set -euo pipefail

BACKUP_DIR=${BACKUP_DIR:-"/db_data"}
DB_NAME=${DB_NAME:-"gigsdb"}
DB_URL=${DB_URL:-"mongodb://db:27017/"}
CONFIRM="yes"
BACKUP_FILE=""
AUTO_CONFIRM="no"

if [ ! -d "$BACKUP_DIR" ] && [ -d "db_data" ]; then
  BACKUP_DIR="db_data"
fi

usage() {
  echo "Usage: $0 [-y] [backup_file.json]"
  echo "  -y                Skip confirmation prompt."
  echo "  backup_file.json  Path to backup JSON file (default: latest in $BACKUP_DIR)."
  exit 1
}

default_backup_file() {
  find "$BACKUP_DIR" -maxdepth 1 -type f -name 'naarm_list_backup_*.json' \
    | sort \
    | tail -n1
}

while [ $# -gt 0 ]; do
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

if [ -z "$BACKUP_FILE" ] || [ ! -f "$BACKUP_FILE" ]; then
  echo "Backup file not found: $BACKUP_FILE"
  exit 1
fi

IMPORT_SCRIPT="/scripts/db_import.py"
if [ ! -f "$IMPORT_SCRIPT" ]; then
  IMPORT_SCRIPT="scripts/db_import.py"
fi

if [ ! -f "$IMPORT_SCRIPT" ]; then
  echo "Import script not found: $IMPORT_SCRIPT"
  exit 1
fi

if [ "$AUTO_CONFIRM" != "yes" ]; then
  echo "WARNING: This will drop and replace imported collections in database ($DB_NAME)."
  echo "Dump file: $BACKUP_FILE"
  read -r -p "Are you sure you want to continue? [y/N]: " CONFIRM
  if [[ ! "$CONFIRM" =~ ^[Yy]$ ]]; then
    echo "Aborted."
    exit 1
  fi
fi

echo "Seeding database: $DB_NAME from backup file: $BACKUP_FILE"
python "$IMPORT_SCRIPT" "$BACKUP_FILE" --uri "$DB_URL" --db "$DB_NAME" --drop --yes
echo "Database seeding complete."
