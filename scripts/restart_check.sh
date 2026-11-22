#!/usr/bin/env bash
# Phase-exit check (local, not CI): a finished run and the library rows it stored (papers, chunks)
# must survive `docker compose restart` of the API and Postgres. The finished run is created from
# the host on the fake surface (see scripts/fake_run.py) in the compose Postgres, then read back
# through the compose API.
set -euo pipefail

cd "$(dirname "$0")/.."

API_URL="${API_URL:-http://localhost:8000}"
PYTHON="${PYTHON:-.venv/bin/python}"
DATABASE_URL_ON_HOST="${DATABASE_URL_ON_HOST:-postgresql+psycopg://postgres:postgres@localhost:5432/postgres}"
START_TIMEOUT_SECONDS="${START_TIMEOUT_SECONDS:-120}"

json_field() {
    python3 -c 'import json, sys; print(json.load(sys.stdin)[sys.argv[1]])' "$1"
}

library_counts() {
    docker compose exec -T db psql -U postgres -tAc \
        "SELECT (SELECT count(*) FROM papers) || ' papers, ' || (SELECT count(*) FROM chunks) || ' chunks'"
}

wait_for_health() {
    local deadline=$((SECONDS + START_TIMEOUT_SECONDS))
    until curl -fs "$API_URL/health" >/dev/null; do
        if ((SECONDS >= deadline)); then
            echo "FAIL: API did not become healthy within ${START_TIMEOUT_SECONDS}s" >&2
            exit 1
        fi
        sleep 2
    done
}

echo "Starting the stack and migrating..."
docker compose up -d --build db backend
wait_for_health
docker compose exec -T backend alembic upgrade head

echo "Creating a finished run on the fake surface..."
job_id=$(PROFILE=test REPOSITORY_BACKEND=postgres DATABASE_URL="$DATABASE_URL_ON_HOST" \
    "$PYTHON" -m scripts.fake_run | tail -n 1)
before=$(curl -fs "$API_URL/status/$job_id")
step=$(echo "$before" | json_field current_step)
if [[ "$step" != "completed" ]]; then
    echo "FAIL: run $job_id is '$step' instead of 'completed': $before" >&2
    exit 1
fi
library_before=$(library_counts)
if [[ "$library_before" == "0 papers, 0 chunks" ]]; then
    echo "FAIL: the run stored no papers or chunks" >&2
    exit 1
fi
echo "Run $job_id is completed ($library_before); restarting API and Postgres..."

docker compose restart db backend
wait_for_health

after=$(curl -fs "$API_URL/status/$job_id")
if [[ "$before" != "$after" ]]; then
    echo "FAIL: status of run $job_id changed across the restart" >&2
    echo "before: $before" >&2
    echo "after:  $after" >&2
    exit 1
fi
library_after=$(library_counts)
if [[ "$library_before" != "$library_after" ]]; then
    echo "FAIL: library changed across the restart: $library_before -> $library_after" >&2
    exit 1
fi
echo "OK: run $job_id, its full result and the library ($library_after) survived the restart."
