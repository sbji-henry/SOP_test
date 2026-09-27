$ErrorActionPreference = "Stop"
Set-Location (Split-Path $PSScriptRoot -Parent)
if (-not (Test-Path .secrets/gateway.env)) { throw "Run scripts/setup-public-password.ps1 first." }
docker compose -f compose.yaml -f compose.public.yaml --profile quick up --build -d --wait
if ($LASTEXITCODE -ne 0) { throw "Tunnel startup failed" }
docker compose -f compose.yaml -f compose.public.yaml logs --tail 40 quick-tunnel
