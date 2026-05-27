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

function Start-DevProcess {
    param(
        [Parameter(Mandatory = $true)][string]$Name,
        [Parameter(Mandatory = $true)][string]$FileName,
        [Parameter(Mandatory = $true)][string[]]$ArgumentList,
        [Parameter(Mandatory = $true)][string]$WorkingDirectory,
        [hashtable]$Environment = @{}
    )

    $startInfo = [System.Diagnostics.ProcessStartInfo]::new()
    $startInfo.FileName = $FileName
    $startInfo.WorkingDirectory = $WorkingDirectory
    $startInfo.UseShellExecute = $false
    $startInfo.RedirectStandardInput = $true
    $startInfo.Arguments = ($ArgumentList | ForEach-Object {
        if ($_ -match '[\s"]') {
            '"' + ($_ -replace '"', '\"') + '"'
        } else {
            $_
        }
    }) -join ' '

    foreach ($key in $Environment.Keys) {
        $startInfo.Environment[$key] = [string]$Environment[$key]
    }

    $process = [System.Diagnostics.Process]::new()
    $process.StartInfo = $startInfo
    if (-not $process.Start()) {
        throw "Failed to start mk3 dev process '$Name'."
    }

    [pscustomobject]@{
        Name = $Name
        Process = $process
    }
}

function Stop-DevProcessTree {
    param([Parameter(Mandatory = $true)]$DevProcess)

    $process = $DevProcess.Process
    if ($process.HasExited) {
        return
    }

    Write-Host "  [stop] $($DevProcess.Name) pid=$($process.Id)"
    & taskkill /PID $process.Id /T /F 2>$null | Out-Null
}

if (-not (Get-Command docker -ErrorAction SilentlyContinue)) {
    throw "docker command was not found. Start Docker Desktop first."
}

Write-Host "Starting mk3 infrastructure..."
& docker compose -f (Join-Path $rootPath "compose.yaml") up -d mongodb qdrant kafka
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

Write-Host ""
Write-Host "Waiting for mk3 infrastructure..."
Wait-DockerContainer -Name "personal-operating-system-mk3-mongodb"
Wait-DockerContainer -Name "personal-operating-system-mk3-qdrant"
Wait-DockerContainer -Name "personal-operating-system-mk3-kafka"

Write-Host "Ensuring mk3 Kafka topics..."
& docker exec personal-operating-system-mk3-kafka /opt/kafka/bin/kafka-topics.sh `
    --bootstrap-server kafka:9092 `
    --create `
    --if-not-exists `
    --topic mk3.conversation.index-requested.v1 `
    --partitions 1 `
    --replication-factor 1 | Out-Host
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
& docker exec personal-operating-system-mk3-kafka /opt/kafka/bin/kafka-topics.sh `
    --bootstrap-server kafka:9092 `
    --create `
    --if-not-exists `
    --topic mk3.news.scrape-requested.v1 `
    --partitions 1 `
    --replication-factor 1 | Out-Host
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
& docker exec personal-operating-system-mk3-kafka /opt/kafka/bin/kafka-topics.sh `
    --bootstrap-server kafka:9092 `
    --create `
    --if-not-exists `
    --topic mk3.news.analysis-requested.v1 `
    --partitions 1 `
    --replication-factor 1 | Out-Host
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

$backendPath = Join-Path $rootPath "backend"
$frontendPath = Join-Path $rootPath "frontend"
$venvPython = Join-Path $rootPath ".venv\Scripts\python.exe"
$pythonCommand = if (Test-Path $venvPython) { $venvPython } else { "python" }
$nodeCommand = Get-Command node.exe -ErrorAction SilentlyContinue
$nodeCommand = if ($nodeCommand) { $nodeCommand.Source } else { "node" }
$nuxtCli = Join-Path $frontendPath "node_modules\nuxt\bin\nuxt.mjs"

$commonDevEnvironment = @{
    NO_COLOR = "1"
    FORCE_COLOR = "0"
}

$kafkaEnvironment = $commonDevEnvironment.Clone()
$kafkaEnvironment["KAFKA_ENABLED"] = "true"
$kafkaEnvironment["KAFKA_BOOTSTRAP_SERVERS"] = "localhost:9092"
$kafkaEnvironment["KAFKA_CONVERSATION_INDEX_TOPIC"] = "mk3.conversation.index-requested.v1"
$kafkaEnvironment["KAFKA_NEWS_SCRAPE_TOPIC"] = "mk3.news.scrape-requested.v1"
$kafkaEnvironment["KAFKA_NEWS_ANALYSIS_TOPIC"] = "mk3.news.analysis-requested.v1"

Write-Host ""
Write-Host "Starting mk3 api/web/index-worker/news-worker..."
Write-Host "  [api] $pythonCommand -m uvicorn app.main:app --reload --port 8001"
Write-Host "  [index-worker] $pythonCommand -m app.workers.conversation_index_worker"
Write-Host "  [news-worker] $pythonCommand -m app.workers.news_worker"
Write-Host "  [web] $nodeCommand $nuxtCli dev"
Write-Host "Press Ctrl+C to stop mk3 app processes."
Write-Host ""

$devProcesses = @()
try {
    $devProcesses += Start-DevProcess `
        -Name "api" `
        -FileName $pythonCommand `
        -ArgumentList @("-m", "uvicorn", "app.main:app", "--reload", "--port", "8001") `
        -WorkingDirectory $backendPath `
        -Environment $kafkaEnvironment

    $indexWorkerEnvironment = $kafkaEnvironment.Clone()
    $indexWorkerEnvironment["KAFKA_CONVERSATION_INDEX_GROUP_ID"] = "mk3-conversation-index-worker"
    $devProcesses += Start-DevProcess `
        -Name "index-worker" `
        -FileName $pythonCommand `
        -ArgumentList @("-m", "app.workers.conversation_index_worker") `
        -WorkingDirectory $backendPath `
        -Environment $indexWorkerEnvironment

    $newsWorkerEnvironment = $kafkaEnvironment.Clone()
    $newsWorkerEnvironment["KAFKA_NEWS_GROUP_ID"] = "mk3-news-worker"
    $devProcesses += Start-DevProcess `
        -Name "news-worker" `
        -FileName $pythonCommand `
        -ArgumentList @("-m", "app.workers.news_worker") `
        -WorkingDirectory $backendPath `
        -Environment $newsWorkerEnvironment

    $devProcesses += Start-DevProcess `
        -Name "web" `
        -FileName $nodeCommand `
        -ArgumentList @($nuxtCli, "dev") `
        -WorkingDirectory $frontendPath `
        -Environment $commonDevEnvironment

    while ($true) {
        $stopped = $devProcesses | Where-Object { $_.Process.HasExited }
        if ($stopped) {
            throw "mk3 dev process '$($stopped[0].Name)' stopped unexpectedly with exit code '$($stopped[0].Process.ExitCode)'."
        }

        Start-Sleep -Milliseconds 500
    }
} finally {
    if ($devProcesses.Count -gt 0) {
        Write-Host ""
        Write-Host "Stopping mk3 app process trees..."
    }
    foreach ($devProcess in $devProcesses) {
        Stop-DevProcessTree -DevProcess $devProcess
    }
    [Console]::ResetColor()
    [Console]::CursorVisible = $true
}
