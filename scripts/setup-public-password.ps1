$ErrorActionPreference = "Stop"
Set-Location (Split-Path $PSScriptRoot -Parent)
New-Item -ItemType Directory -Force .secrets | Out-Null
if (Test-Path .secrets/gateway.env) { throw "gateway.env exists; move it before rotating the password." }
Write-Host "Enter a new password at the Caddy prompt. It will not be stored in plaintext."
docker run --rm -it -v "${PWD}/.secrets:/secrets" caddy:2-alpine sh -c 'umask 077; caddy hash-password > /secrets/password.hash'
if ($LASTEXITCODE -ne 0) { throw "Password hashing failed" }
$hash = (Get-Content .secrets/password.hash -Raw).Trim()
if (-not $hash.StartsWith('$2')) { throw "Invalid password hash" }
@("SOP_USER=sop", "SOP_PASSWORD_HASH=$hash") | Set-Content -Encoding ascii .secrets/gateway.env
Remove-Item .secrets/password.hash
Write-Host "User: sop. Password hash saved to .secrets/gateway.env."
