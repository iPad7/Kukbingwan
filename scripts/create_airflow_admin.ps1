$User = if ($env:AIRFLOW_ADMIN_USER) { $env:AIRFLOW_ADMIN_USER } else { "admin" }
$Email = if ($env:AIRFLOW_ADMIN_EMAIL) { $env:AIRFLOW_ADMIN_EMAIL } else { "admin@example.com" }
$Password = if ($env:AIRFLOW_ADMIN_PASSWORD) { $env:AIRFLOW_ADMIN_PASSWORD } else { "admin" }

Write-Host "Creating Airflow admin user '$User' (container: airflow-webserver)..."

# Check if user already exists
$existing = docker compose exec airflow-webserver airflow users list 2>$null | Select-String " $User "
if ($LASTEXITCODE -eq 0 -and $existing) {
    Write-Host "User '$User' already exists. Skipping."
    exit 0
}

docker compose exec airflow-webserver airflow users create `
  --username $User `
  --firstname Admin `
  --lastname User `
  --role Admin `
  --email $Email `
  --password $Password

if ($LASTEXITCODE -ne 0) {
    Write-Error "Failed to create user '$User'. Exit code: $LASTEXITCODE"
    exit $LASTEXITCODE
}

Write-Host "Done. Login at http://localhost:8080 with user '$User'."
