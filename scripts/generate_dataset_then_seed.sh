#!/usr/bin/env bash
# Convenience: regenerate the synthetic dataset, then load it into the DB.
# Requires: `docker compose up -d db` already running (or a reachable
# Postgres per backend/.env).
set -e
cd "$(dirname "$0")/.."

echo "== 1/2  Generating synthetic dataset =="
python3 scripts/dataset_generator/generate_dataset.py

echo "== 2/2  Seeding database =="
PYTHONPATH=backend python3 scripts/seed_db.py

echo "Done."
