# run_all.ps1 - Windows Task Scheduler entry point for metrics-pull.
# Runs scripts\run_all.py and saves its output to logs\run-<time>.log in the
# skill folder. Never throws: the scheduler always sees exit code 0.

$ErrorActionPreference = "Continue"

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$logDir = Join-Path (Split-Path -Parent $scriptDir) "logs"
New-Item -ItemType Directory -Force -Path $logDir | Out-Null
$logFile = Join-Path $logDir ("run-" + (Get-Date -Format "yyyyMMdd-HHmmss") + ".log")

# Prefer the "py" launcher, then python on PATH.
$py = (Get-Command py -ErrorAction SilentlyContinue).Source
$pyArgs = @("-3")
if (-not $py) { $py = (Get-Command python -ErrorAction SilentlyContinue).Source; $pyArgs = @() }

if (-not $py) {
    "Python not found on PATH" | Out-File -FilePath $logFile -Encoding utf8
    exit 0
}

& $py @pyArgs (Join-Path $scriptDir "run_all.py") @args 2>&1 | Out-File -FilePath $logFile -Encoding utf8

# Keep only the newest 60 logs.
Get-ChildItem $logDir -Filter "run-*.log" | Sort-Object Name -Descending |
    Select-Object -Skip 60 | Remove-Item -Force -ErrorAction SilentlyContinue

exit 0
