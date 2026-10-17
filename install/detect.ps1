# cutmate environment report (Windows): prints one JSON object, installs nothing.
$ErrorActionPreference = 'SilentlyContinue'

function Get-Ver($text) {
    if ($text -match '(\d+\.\d+(\.\d+)?)') { return $Matches[1] }
    return $null
}

$arch = $env:PROCESSOR_ARCHITECTURE
if ($arch -eq 'AMD64') { $arch = 'x86_64' }
$pkg = $null
if (Get-Command winget -ErrorAction SilentlyContinue) { $pkg = 'winget' }

# gpu
$gpu = [ordered]@{ kind = 'none'; name = $null; vram_mb = $null; driver = $null }
if (Get-Command nvidia-smi -ErrorAction SilentlyContinue) {
    $line = (& nvidia-smi --query-gpu=name,memory.total,driver_version --format=csv,noheader,nounits 2>$null | Select-Object -First 1)
    if ($line) {
        $p = $line -split ',\s*'
        $gpu.kind = 'nvidia'; $gpu.name = $p[0]; $gpu.vram_mb = [int]$p[1]; $gpu.driver = $p[2].Trim()
    }
}
if ($gpu.kind -eq 'none') {
    $vc = Get-CimInstance Win32_VideoController | Select-Object -First 1
    if ($vc) { $gpu.name = $vc.Name }
}

# disk
$drive = (Get-Item $HOME).PSDrive
$disk = [int][math]::Floor($drive.Free / 1GB)

# tools
$ffmpegV = $null
if (Get-Command ffmpeg -ErrorAction SilentlyContinue) {
    $first = (& ffmpeg -version 2>$null | Select-Object -First 1)
    if ($first -match 'ffmpeg version (\S+)') { $ffmpegV = $Matches[1] } else { $ffmpegV = 'unknown' }
}

$pyBin = $null; $pyVer = $null; $pyVenv = $false
$cands = @(@('py', '-3'), @('python'))
foreach ($c in $cands) {
    $exe = $c[0]
    if (-not (Get-Command $exe -ErrorAction SilentlyContinue)) { continue }
    $extra = @($c | Select-Object -Skip 1)
    $v = Get-Ver ((& $exe @extra --version 2>&1 | Select-Object -First 1) | Out-String)
    if (-not $v) { continue }
    $parts = $v.Split('.')
    if ([int]$parts[0] -gt 3 -or ([int]$parts[0] -eq 3 -and [int]$parts[1] -ge 10)) {
        $pyBin = (& $exe @extra -c "import sys; print(sys.executable)" 2>$null | Select-Object -First 1)
        $pyVer = $v
        & $exe @extra -c "import ensurepip, venv" 2>$null | Out-Null
        $pyVenv = ($LASTEXITCODE -eq 0)
        break
    }
}

$nodeV = $null; $nodeMajor = 0
if (Get-Command node -ErrorAction SilentlyContinue) {
    $nodeV = ((& node --version 2>$null | Select-Object -First 1) -replace '^v', '')
    $nodeMajor = [int](($nodeV -split '\.')[0])
}
$npx = [bool](Get-Command npx -ErrorAction SilentlyContinue)
$heygenV = $null
if (Get-Command heygen -ErrorAction SilentlyContinue) {
    $heygenV = Get-Ver ((& heygen --version 2>$null | Select-Object -First 1) | Out-String)
    if (-not $heygenV) { $heygenV = 'unknown' }
}

# cutmate home
$cmHome = $env:CUTMATE_HOME
if (-not $cmHome) { $cmHome = Join-Path $HOME '.cutmate' }
$cmVenv = Test-Path (Join-Path $cmHome 'venv\Scripts\python.exe')
$cmCfg = Test-Path (Join-Path $cmHome 'config.json')

# missing + install
$missing = @()
if (-not $ffmpegV) { $missing += 'ffmpeg' }
if (-not $pyBin) { $missing += 'python' }
if ($pyBin -and -not $pyVenv) { $missing += 'python-venv' }
if (-not $nodeV -or $nodeMajor -lt 22) { $missing += 'node' }

$cmds = @{
    'ffmpeg' = 'winget install -e --id Gyan.FFmpeg'
    'python' = 'winget install -e --id Python.Python.3.12'
    'node'   = 'winget install -e --id OpenJS.NodeJS.LTS'
}
$install = @()
if ($pkg) { foreach ($m in $missing) { if ($cmds.ContainsKey($m)) { $install += $cmds[$m] } } }

$report = [ordered]@{
    os = 'windows'
    distro = $null
    arch = $arch
    pkg = $pkg
    gpu = $gpu
    disk_free_gb = $disk
    tools = [ordered]@{
        ffmpeg = $ffmpegV
        python = $pyVer
        python_bin = $pyBin
        python_venv = $pyVenv
        node = $nodeV
        npx = $npx
        heygen = $heygenV
    }
    cutmate = [ordered]@{ home = $cmHome; venv = $cmVenv; config = $cmCfg }
    missing = @($missing)
    install = @($install)
}
$report | ConvertTo-Json -Depth 4
exit 0
