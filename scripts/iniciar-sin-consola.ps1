$ErrorActionPreference = "Stop"

$Root = Split-Path -Parent $PSScriptRoot
$LogDir = Join-Path $Root "logs"
$RunDir = Join-Path $Root ".run"
$Log = Join-Path $LogDir "launcher.log"
$ServerOut = Join-Path $LogDir "server.out.log"
$ServerErr = Join-Path $LogDir "server.err.log"
$PidFile = Join-Path $RunDir "server.pid"
$Url = "http://127.0.0.1:8000"

New-Item -ItemType Directory -Force -Path $LogDir | Out-Null
New-Item -ItemType Directory -Force -Path $RunDir | Out-Null
Set-Location $Root

function Write-Log {
  param([string]$Message)
  $line = "[{0}] {1}" -f (Get-Date -Format "yyyy-MM-dd HH:mm:ss"), $Message
  Add-Content -Path $Log -Value $line -Encoding UTF8
}

function Invoke-Logged {
  param(
    [string]$FilePath,
    [string[]]$Arguments
  )

  Write-Log ("RUN {0} {1}" -f $FilePath, ($Arguments -join " "))
  $previousErrorActionPreference = $ErrorActionPreference
  $ErrorActionPreference = "Continue"
  try {
    & $FilePath @Arguments 2>&1 | ForEach-Object {
      Add-Content -Path $Log -Value $_ -Encoding UTF8
    }
  } finally {
    $ErrorActionPreference = $previousErrorActionPreference
  }
  if ($LASTEXITCODE -ne 0) {
    throw ("Command failed with exit code {0}: {1}" -f $LASTEXITCODE, $FilePath)
  }
}

function Test-AppReady {
  try {
    $response = Invoke-WebRequest -Uri "$Url/api/health" -UseBasicParsing -TimeoutSec 2
    return $response.StatusCode -eq 200
  } catch {
    return $false
  }
}

function Open-App {
  if ($env:MARKITDOWN_NO_BROWSER -ne "1") {
    Start-Process $Url
  }
}

try {
  Write-Log "Launcher started"

  if (Test-AppReady) {
    Write-Log "Server already running"
    Open-App
    exit 0
  }

  $venvPython = Join-Path $Root ".venv\Scripts\python.exe"
  if (!(Test-Path $venvPython)) {
    if (Get-Command python -ErrorAction SilentlyContinue) {
      Invoke-Logged "python" @("-m", "venv", ".venv")
    } elseif (Get-Command py -ErrorAction SilentlyContinue) {
      Invoke-Logged "py" @("-3", "-m", "venv", ".venv")
    } else {
      throw "Python no esta instalado o no esta en PATH"
    }
  }

  $requirements = Join-Path $Root "requirements.txt"
  $hashFile = Join-Path $Root ".venv\.requirements.sha256"
  $currentHash = (Get-FileHash $requirements -Algorithm SHA256).Hash
  $installedHash = if (Test-Path $hashFile) { (Get-Content $hashFile -Raw).Trim() } else { "" }

  if ($currentHash -ne $installedHash) {
    Write-Log "Installing dependencies"
    Invoke-Logged $venvPython @("-m", "pip", "install", "--upgrade", "pip")
    Invoke-Logged $venvPython @("-m", "pip", "install", "setuptools<81", "wheel")
    Invoke-Logged $venvPython @("-m", "pip", "install", "--no-build-isolation", "openai-whisper==20240930")
    Invoke-Logged $venvPython @("-m", "pip", "install", "-r", "requirements.txt")
    Set-Content -Path $hashFile -Value $currentHash -Encoding ASCII
  } else {
    Write-Log "Dependencies already installed"
  }

  if (Test-AppReady) {
    Write-Log "Server became ready during setup"
    Open-App
    exit 0
  }

  Write-Log "Starting server"
  $process = Start-Process `
    -FilePath $venvPython `
    -ArgumentList @("-m", "uvicorn", "app:app", "--host", "127.0.0.1", "--port", "8000") `
    -WorkingDirectory $Root `
    -WindowStyle Hidden `
    -RedirectStandardOutput $ServerOut `
    -RedirectStandardError $ServerErr `
    -PassThru

  Set-Content -Path $PidFile -Value $process.Id -Encoding ASCII
  Write-Log ("Server PID {0}" -f $process.Id)

  for ($i = 0; $i -lt 60; $i++) {
    Start-Sleep -Seconds 1
    if (Test-AppReady) {
      Write-Log "Server ready"
      Open-App
      exit 0
    }
    if ($process.HasExited) {
      throw ("Server exited early with code {0}. Check server.err.log" -f $process.ExitCode)
    }
  }

  throw "Server did not become ready within 60 seconds"
} catch {
  Write-Log ("ERROR " + $_.Exception.Message)
  exit 1
}
