#!/bin/sh
set -eu

python -m alembic upgrade head
python /app/scripts/seed.py
exec "$@"
