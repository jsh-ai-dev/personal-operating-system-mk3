$ErrorActionPreference = 'Stop'

$rootPath = $PSScriptRoot

function Wait-DockerContainer {
    param(
        [Parameter(Mandatory = $true)][string]$Name,
        [int]$TimeoutSeconds = 120
    )

    $deadline = (Get-Date).AddSeconds($TimeoutSeconds)
    while ((Get-Date) -lt $deadline) {
        $status = (& docker inspect --format '{{if .State.Health}}{{.State.Health.Status}}{{else}}{{.State.Status}}{{end}}' $Name 2>$null)
        if ($LASTEXITCODE -eq 0) {
            if ($status -eq 'healthy' -or $status -eq 'running') {
                Write-Host "  [ready] $Name ($status)"
                return
            }
            Write-Host "  [wait]  $Name ($status)"
        } else {
            Write-Host "  [wait]  $Name (not found)"
        }
        Start-Sleep -Seconds 2
    }

    throw "Timed out waiting for Docker container '$Name'."
}

function Receive-PrefixedJob {
    param([Parameter(Mandatory = $true)]$Job)

    Receive-Job $Job -ErrorAction Continue 2>&1 | ForEach-Object {
        Write-Host "[$($Job.Name)] $_"
    }
}

if (-not (Get-Command docker -ErrorAction SilentlyContinue)) {
    throw "docker command was not found. Start Docker Desktop first."
}

Write-Host "Starting mk3 infrastructure..."
& docker compose -f (Join-Path $rootPath "compose.yaml") up -d mongodb qdrant
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

Write-Host ""
Write-Host "Waiting for mk3 infrastructure..."
Wait-DockerContainer -Name "personal-operating-system-mk3-mongodb"
Wait-DockerContainer -Name "personal-operating-system-mk3-qdrant"

$backendPath = Join-Path $rootPath "backend"
$frontendPath = Join-Path $rootPath "frontend"
$venvPython = Join-Path $rootPath ".venv\Scripts\python.exe"
$pythonCommand = if (Test-Path $venvPython) { $venvPython } else { "python" }

Write-Host ""
Write-Host "Starting mk3 api/web..."
Write-Host "  [api] $pythonCommand -m uvicorn app.main:app --reload --port 8001"
Write-Host "  [web] npm run dev"
Write-Host "Press Ctrl+C to stop both mk3 app processes."
Write-Host ""

$jobs = @()
try {
    $jobs += Start-Job -Name "api" -ScriptBlock {
        param($WorkingDirectory, $PythonCommand)
        Set-Location $WorkingDirectory
        & $PythonCommand -m uvicorn app.main:app --reload --port 8001 2>&1
    } -ArgumentList $backendPath, $pythonCommand

    $jobs += Start-Job -Name "web" -ScriptBlock {
        param($WorkingDirectory)
        Set-Location $WorkingDirectory
        npm run dev 2>&1
    } -ArgumentList $frontendPath

    while ($true) {
        foreach ($job in $jobs) {
            Receive-PrefixedJob -Job $job
        }

        $failed = $jobs | Where-Object { $_.State -eq "Failed" }
        if ($failed) {
            foreach ($job in $failed) {
                Receive-PrefixedJob -Job $job
            }
            throw "mk3 dev process '$($failed[0].Name)' failed."
        }

        $running = $jobs | Where-Object { $_.State -eq "Running" }
        if (-not $running) {
            break
        }

        Start-Sleep -Milliseconds 500
    }
} finally {
    foreach ($job in $jobs) {
        if ($job.State -eq "Running") {
            Stop-Job $job
        }
        Receive-PrefixedJob -Job $job
        Remove-Job $job -Force
    }
}
