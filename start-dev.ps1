$ErrorActionPreference = "Stop"

$projectRoot = $PSScriptRoot
$pythonPath = Join-Path $projectRoot ".venv\Scripts\python.exe"
$frontendPath = Join-Path $projectRoot "frontend"
$packageJsonPath = Join-Path $frontendPath "package.json"
$nodeModulesPath = Join-Path $frontendPath "node_modules"

$requiredPaths = @(
    @{ Path = $pythonPath; Description = ".venv\Scripts\python.exe"; Type = "Leaf" }
    @{ Path = $frontendPath; Description = "frontend\"; Type = "Container" }
    @{ Path = $packageJsonPath; Description = "frontend\package.json"; Type = "Leaf" }
    @{ Path = $nodeModulesPath; Description = "frontend\node_modules"; Type = "Container" }
)

foreach ($requiredPath in $requiredPaths) {
    if (-not (Test-Path -LiteralPath $requiredPath.Path -PathType $requiredPath.Type)) {
        Write-Error "Voraussetzung fehlt: $($requiredPath.Description). Bitte die lokale Entwicklungsumgebung zuerst einrichten."
        exit 1
    }
}

Write-Host "Backend wird gestartet ..."

$backendProcess = Start-Process `
    -FilePath $pythonPath `
    -ArgumentList @(
        "-m", "uvicorn",
        "app.main:app",
        "--reload",
        "--host", "127.0.0.1",
        "--port", "8000"
    ) `
    -WorkingDirectory $projectRoot `
    -PassThru `
    -NoNewWindow

$backendReady = $false

for ($attempt = 0; $attempt -lt 60; $attempt++) {
    try {
        $response = Invoke-WebRequest `
            -Uri "http://127.0.0.1:8000/health" `
            -UseBasicParsing `
            -TimeoutSec 2

        if ($response.StatusCode -eq 200) {
            $backendReady = $true
            break
        }
    }
    catch {
        Start-Sleep -Milliseconds 500
    }
}

if (-not $backendReady) {
    Write-Error "Backend konnte innerhalb von 30 Sekunden nicht gestartet werden."
    exit 1
}

Write-Host "Backend bereit."
Write-Host "Backend:  http://127.0.0.1:8000"
Write-Host "Swagger:  http://127.0.0.1:8000/docs"
Write-Host ""
Write-Host "Frontend wird gestartet ..."
Write-Host "Frontend: http://localhost:5173"
Write-Host ""

Set-Location -LiteralPath $frontendPath
npm run dev