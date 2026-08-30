$ErrorActionPreference = "Stop"

$RepoRoot = Split-Path -Parent $PSScriptRoot
$EnvFile = Join-Path $RepoRoot ".env"
$ExampleEnvFile = Join-Path $RepoRoot ".env.example"

Set-Location $RepoRoot

if (-not (Test-Path $EnvFile)) {
    Copy-Item -LiteralPath $ExampleEnvFile -Destination $EnvFile
    Write-Host "Created .env from .env.example"
}

docker compose up --build
