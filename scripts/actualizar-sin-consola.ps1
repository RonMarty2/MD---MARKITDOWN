$ErrorActionPreference = "Stop"

$Root = Split-Path -Parent $PSScriptRoot
$LogDir = Join-Path $Root "logs"
$Log = Join-Path $LogDir "updater.log"

New-Item -ItemType Directory -Force -Path $LogDir | Out-Null
Set-Location $Root

function Write-Log {
  param([string]$Message)
  $line = "[{0}] {1}" -f (Get-Date -Format "yyyy-MM-dd HH:mm:ss"), $Message
  Add-Content -Path $Log -Value $line -Encoding UTF8
}

function Invoke-Git {
  param([string[]]$Arguments)
  Write-Log ("RUN git {0}" -f ($Arguments -join " "))
  $previousErrorActionPreference = $ErrorActionPreference
  $ErrorActionPreference = "Continue"
  try {
    & git @Arguments 2>&1 | ForEach-Object {
      Add-Content -Path $Log -Value $_ -Encoding UTF8
    }
  } finally {
    $ErrorActionPreference = $previousErrorActionPreference
  }
  if ($LASTEXITCODE -ne 0) {
    throw ("git failed with exit code {0}: git {1}" -f $LASTEXITCODE, ($Arguments -join " "))
  }
}

try {
  Write-Log "Updater started"

  if (!(Get-Command git -ErrorAction SilentlyContinue)) {
    throw "Git no esta instalado o no esta en PATH"
  }

  $branch = (& git rev-parse --abbrev-ref HEAD).Trim()
  if ($LASTEXITCODE -ne 0 -or !$branch -or $branch -eq "HEAD") {
    throw "No hay una rama git activa"
  }

  $status = (& git status --porcelain)
  if ($status) {
    $message = "update " + (Get-Date -Format "yyyy-MM-dd HH:mm:ss")
    Invoke-Git @("add", "-A")
    Invoke-Git @("commit", "-m", $message)
  } else {
    Write-Log "No local changes to commit"
  }

  Invoke-Git @("push", "-u", "origin", $branch)
  Write-Log "Updater finished"
  exit 0
} catch {
  Write-Log ("ERROR " + $_.Exception.Message)
  exit 1
}
