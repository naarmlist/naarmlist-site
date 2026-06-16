#!/usr/bin/env sh
set -eu

repo_root="$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)"
cd "$repo_root"

if [ ! -f .env ]; then
    cp .env.example .env
    echo "Created .env from .env.example"
fi

docker compose up --build
