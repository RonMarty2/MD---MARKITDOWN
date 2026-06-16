$ErrorActionPreference = "Stop"

$Root = Split-Path -Parent $PSScriptRoot
$LogDir = Join-Path $Root "logs"
$RunDir = Join-Path $Root ".run"
$Log = Join-Path $LogDir "launcher.log"
$PidFile = Join-Path $RunDir "server.pid"

New-Item -ItemType Directory -Force -Path $LogDir | Out-Null
New-Item -ItemType Directory -Force -Path $RunDir | Out-Null

function Write-Log {
  param([string]$Message)
  $line = "[{0}] {1}" -f (Get-Date -Format "yyyy-MM-dd HH:mm:ss"), $Message
  Add-Content -Path $Log -Value $line -Encoding UTF8
}

try {
  Write-Log "Stop requested"

  if (!(Test-Path $PidFile)) {
    Write-Log "No PID file found"
    exit 0
  }

  $processId = [int](Get-Content $PidFile -Raw)
  $process = Get-Process -Id $processId -ErrorAction SilentlyContinue

  if ($process) {
    Stop-Process -Id $processId -Force
    Write-Log ("Stopped PID {0}" -f $processId)
  } else {
    Write-Log ("PID {0} was not running" -f $processId)
  }

  Remove-Item $PidFile -Force -ErrorAction SilentlyContinue
  exit 0
} catch {
  Write-Log ("ERROR " + $_.Exception.Message)
  exit 1
}
