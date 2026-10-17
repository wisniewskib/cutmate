# cutmate setup (Windows): builds %CUTMATE_HOME%\venv (default ~\.cutmate\venv) with the plugin installed editable.
# Usage: setup.ps1 [-Gpu nvidia|none] [-Local] [-DryRun]
param(
  [ValidateSet('nvidia', 'none')][string]$Gpu = 'none',
  [switch]$Local,
  [switch]$DryRun
)
$ErrorActionPreference = 'Stop'

$Root = Split-Path -Parent $PSScriptRoot
$HomeDir = if ($env:CUTMATE_HOME) { $env:CUTMATE_HOME } else { Join-Path $HOME '.cutmate' }
$Venv = Join-Path $HomeDir 'venv'
$Py = Join-Path $Venv 'Scripts\python.exe'

function Find-Python {
  foreach ($c in 'python3.13', 'python3.12', 'python3.11', 'python3.10', 'python3', 'python') {
    $cmd = Get-Command $c -ErrorAction SilentlyContinue
    if (-not $cmd) { continue }
    $out = (& $cmd.Source --version 2>&1 | Select-Object -First 1)
    if ("$out" -match '^Python (\d+)\.(\d+)') {
      $maj = [int]$Matches[1]; $min = [int]$Matches[2]
      if ($maj -gt 3 -or ($maj -eq 3 -and $min -ge 10)) { return $cmd.Source }
    }
  }
  return $null
}

$PyBin = Find-Python
if (-not $PyBin) {
  [Console]::Error.WriteLine('Python ≥ 3.10 not found — install it first (/cutmate:setup → dependencies)')
  exit 1
}

function Run([string[]]$Cmd) {
  Write-Output ('+ ' + ($Cmd -join ' '))
  if (-not $DryRun) {
    & $Cmd[0] $Cmd[1..($Cmd.Length - 1)]
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
  }
}

$extras = 'align,track'
if ($Local) { $extras += ',faster' }

if (-not (Test-Path $Py)) {
  if (-not $DryRun) { New-Item -ItemType Directory -Force -Path $HomeDir | Out-Null }
  Run @($PyBin, '-m', 'venv', $Venv)
}
Run @($Py, '-m', 'pip', 'install', '--upgrade', 'pip')
Run @($Py, '-m', 'pip', 'install', 'torch', '--index-url', 'https://download.pytorch.org/whl/cpu')
Run @($Py, '-m', 'pip', 'install', '-e', "$Root[$extras]")
if ($Gpu -eq 'nvidia' -and $Local) {
  Run @($Py, '-m', 'pip', 'install', 'nvidia-cublas-cu12', 'nvidia-cudnn-cu12==9.*')
}

Write-Output "venv: $Venv"
Write-Output "cutmate: $(Join-Path $Venv 'Scripts\cutmate.exe')"
