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

function Test-Python([string]$Exe, [string[]]$Extra) {
  # Continue + $LASTEXITCODE: a native stderr line must not become a terminating error (PS 5.1)
  $out = $null
  try {
    $ErrorActionPreference = 'Continue'
    $out = (& $Exe @Extra --version 2>&1 | Select-Object -First 1)
    if ($LASTEXITCODE -ne 0) { return $null }
    if ("$out" -notmatch '^Python (\d+)\.(\d+)') { return $null }
    $maj = [int]$Matches[1]; $min = [int]$Matches[2]
    if (-not ($maj -gt 3 -or ($maj -eq 3 -and $min -ge 10))) { return $null }
    $exe = (& $Exe @Extra -c 'import sys; print(sys.executable)' 2>$null | Select-Object -First 1)
    if ($LASTEXITCODE -ne 0 -or -not $exe) { return $null }
    return "$exe".Trim()
  } catch {
    return $null
  } finally {
    $ErrorActionPreference = 'Stop'
  }
}

function Find-Python {
  # py -3 first, like detect.ps1
  foreach ($c in 'py -3', 'python3.13', 'python3.12', 'python3.11', 'python3.10', 'python3', 'python') {
    $parts = $c -split ' '
    $cmd = Get-Command $parts[0] -ErrorAction SilentlyContinue
    if (-not $cmd) { continue }
    $found = Test-Python $cmd.Source @($parts | Select-Object -Skip 1)
    if ($found) { return $found }
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
    # pip writes warnings to stderr; under 'Stop' PS 5.1 turns them into terminating errors when output is
    # redirected, so run the native command under 'Continue' and judge it by $LASTEXITCODE alone
    $ErrorActionPreference = 'Continue'
    try {
      & $Cmd[0] $Cmd[1..($Cmd.Length - 1)]
      $code = $LASTEXITCODE
    } finally {
      $ErrorActionPreference = 'Stop'
    }
    if ($code -ne 0) { exit $code }
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
