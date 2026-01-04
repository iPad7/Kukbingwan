#!/usr/bin/env bash
set -euo pipefail

USER="${AIRFLOW_ADMIN_USER:-admin}"
EMAIL="${AIRFLOW_ADMIN_EMAIL:-admin@example.com}"
PASSWORD="${AIRFLOW_ADMIN_PASSWORD:-admin}"

echo "Creating Airflow admin user '${USER}' (container: airflow-webserver)..."

# If user already exists, skip creation.
if docker compose exec airflow-webserver airflow users list | grep -q " ${USER} " ; then
  echo "User '${USER}' already exists. Skipping."
  exit 0
fi

docker compose exec airflow-webserver airflow users create \
  --username "${USER}" \
  --firstname Admin \
  --lastname User \
  --role Admin \
  --email "${EMAIL}" \
  --password "${PASSWORD}"

echo "Done. Login at http://localhost:8080 with user '${USER}'."
