"""Import a Naarm List JSON dump into MongoDB."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
from typing import Any

from bson import ObjectId
from pymongo import MongoClient


REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_COLLECTIONS = {
    'events': 'events',
    'venues': 'venues',
    'organisers': 'Organisers',
    'artists': 'Artists',
    'tmp': 'tmp',
}
OBJECT_ID_FIELDS = {'_id', 'target_id'}


def load_dotenv(env_path: Path) -> None:
    """Load simple KEY=VALUE pairs from .env without overriding real env vars."""
    if not env_path.exists():
        return

    for raw_line in env_path.read_text(encoding='utf-8').splitlines():
        line = raw_line.strip()
        if not line or line.startswith('#') or '=' not in line:
            continue
        key, value = line.split('=', 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


def restore_object_ids(value: Any, field_name: str | None = None) -> Any:
    """Recursively convert known ObjectId string fields back to ObjectIds."""
    if isinstance(value, list):
        return [restore_object_ids(item) for item in value]

    if isinstance(value, dict):
        return {
            key: restore_object_ids(child_value, key)
            for key, child_value in value.items()
        }

    if field_name in OBJECT_ID_FIELDS and isinstance(value, str) and ObjectId.is_valid(value):
        return ObjectId(value)

    return value


def default_mongo_uri() -> str:
    """Return a practical Mongo URI for host or Docker execution."""
    uri = os.getenv('DB_URL') or 'mongodb://localhost:27017/'
    if uri.startswith('mongodb://db:') and not Path('/.dockerenv').exists():
        return uri.replace('mongodb://db:', 'mongodb://localhost:', 1)
    return uri


def parse_args() -> argparse.Namespace:
    """Parse CLI options."""
    parser = argparse.ArgumentParser(
        description='Import a Naarm List JSON dump into MongoDB.'
    )
    parser.add_argument('dump', type=Path, help='Path to a JSON dump file.')
    parser.add_argument(
        '--uri',
        default=None,
        help='MongoDB URI. Defaults to DB_URL from env/.env, then mongodb://localhost:27017/.',
    )
    parser.add_argument(
        '--db',
        default=None,
        help='Database name. Defaults to DB_NAME from env/.env, then gigsdb.',
    )
    parser.add_argument(
        '--drop',
        action='store_true',
        help='Drop each imported collection before loading it.',
    )
    parser.add_argument(
        '--yes',
        action='store_true',
        help='Confirm destructive --drop imports without prompting.',
    )
    return parser.parse_args()


def confirm_drop(db_name: str, dump_path: Path) -> None:
    """Prompt before destructive imports."""
    print(f'WARNING: this will drop imported collections in database "{db_name}".')
    print(f'Dump file: {dump_path}')
    confirmation = input('Type "yes" to continue: ')
    if confirmation != 'yes':
        raise SystemExit('Import aborted.')


def load_dump(dump_path: Path) -> dict[str, list[dict[str, Any]]]:
    """Read and validate a JSON dump file."""
    if not dump_path.exists():
        raise SystemExit(f'Dump file not found: {dump_path}')

    with dump_path.open('r', encoding='utf-8') as dump_file:
        data = json.load(dump_file)

    if not isinstance(data, dict):
        raise SystemExit('Dump must be a JSON object keyed by collection name.')

    for dump_key, documents in data.items():
        if dump_key not in DEFAULT_COLLECTIONS:
            raise SystemExit(f'Unexpected collection in dump: {dump_key}')
        if not isinstance(documents, list):
            raise SystemExit(f'Collection "{dump_key}" must contain a JSON array.')

    return data


def import_database(uri: str, db_name: str, dump_path: Path, drop: bool = False) -> None:
    """Import one dump file into MongoDB."""
    client = MongoClient(uri)
    db = client[db_name]
    data = load_dump(dump_path)

    for dump_key, collection_name in DEFAULT_COLLECTIONS.items():
        documents = data.get(dump_key, [])
        collection = db[collection_name]

        if drop:
            collection.drop()

        if not documents:
            print(f'Skipping {dump_key}: no documents.')
            continue

        restored_documents = [restore_object_ids(document) for document in documents]
        if drop:
            collection.insert_many(restored_documents, ordered=False)
        else:
            for document in restored_documents:
                document_id = document.get('_id')
                if document_id is None:
                    collection.insert_one(document)
                else:
                    collection.replace_one({'_id': document_id}, document, upsert=True)
        print(f'Imported {len(restored_documents)} document(s) into {collection_name}.')


def main() -> None:
    """Run the import command."""
    load_dotenv(REPO_ROOT / '.env')
    args = parse_args()
    uri = args.uri or default_mongo_uri()
    db_name = args.db or os.getenv('DB_NAME') or 'gigsdb'

    if args.drop and not args.yes:
        confirm_drop(db_name, args.dump)

    import_database(uri, db_name, args.dump, drop=args.drop)
    print(f'Imported dump into database "{db_name}".')


if __name__ == '__main__':
    main()
