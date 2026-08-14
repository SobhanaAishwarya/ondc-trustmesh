#!/bin/sh
# Applies pending migrations before the API starts accepting traffic, so a
# fresh container never serves against a stale/empty schema. `set -e` so a
# failed migration stops the container instead of starting a broken API.
set -e

echo "Running database migrations..."
alembic upgrade head

echo "Starting API..."
exec "$@"
