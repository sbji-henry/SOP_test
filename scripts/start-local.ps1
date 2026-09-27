$ErrorActionPreference = "Stop"
Set-Location (Split-Path $PSScriptRoot -Parent)
docker compose up --build -d --wait
if ($LASTEXITCODE -ne 0) { throw "Docker startup failed" }
Invoke-RestMethod http://127.0.0.1:8080/health
