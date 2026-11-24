<#
.SYNOPSIS
  Starts the photobooth backend and opens the UI fullscreen in kiosk mode (magic mirror).

.DESCRIPTION
  1. starts "uv run photobooth" hidden (skipped if something already answers on the port)
  2. waits until the web server responds
  3. warns if the QR link in the synchronizer config does not use this PC's current LAN IP
  4. opens Edge (or Chrome) in kiosk mode

  Screen rotation for a portrait mirror is done in Windows: Settings > System > Display > Display orientation.

.PARAMETER DryRun
  Only print what would be done.
#>
[CmdletBinding()]
param(
    [int]$Port = 8000,
    [int]$StartupTimeoutSeconds = 180,
    [switch]$DryRun
)

$ErrorActionPreference = 'Stop'
$RepoRoot = Split-Path -Parent $PSScriptRoot
$Url = "http://127.0.0.1:$Port/"
$LogDir = Join-Path $RepoRoot 'log'
$KioskLog = Join-Path $LogDir 'kiosk.log'

function Write-Step([string]$Message) {
    $line = "{0:yyyy-MM-dd HH:mm:ss}  {1}" -f (Get-Date), $Message
    Write-Host $line
    if (-not $DryRun) {
        New-Item -ItemType Directory -Force -Path $LogDir | Out-Null
        Add-Content -Path $KioskLog -Value $line
    }
}

function Test-Backend {
    try {
        $r = Invoke-WebRequest -Uri $Url -UseBasicParsing -TimeoutSec 2
        return ($r.StatusCode -eq 200)
    } catch {
        return $false
    }
}

function Get-LanIp {
    # IPv4 of the interface that owns the default route
    $route = Get-NetRoute -DestinationPrefix '0.0.0.0/0' -ErrorAction SilentlyContinue | Sort-Object RouteMetric | Select-Object -First 1
    if (-not $route) { return $null }
    (Get-NetIPAddress -InterfaceIndex $route.InterfaceIndex -AddressFamily IPv4 -ErrorAction SilentlyContinue | Select-Object -First 1).IPAddress
}

function Find-Browser {
    $candidates = @(
        "$env:ProgramFiles (x86)\Microsoft\Edge\Application\msedge.exe",
        "$env:ProgramFiles\Microsoft\Edge\Application\msedge.exe",
        "$env:ProgramFiles\Google\Chrome\Application\chrome.exe",
        "${env:ProgramFiles(x86)}\Google\Chrome\Application\chrome.exe"
    )
    $candidates | Where-Object { Test-Path $_ } | Select-Object -First 1
}

# --- 1. backend -------------------------------------------------------------
if (Test-Backend) {
    Write-Step "backend already answering on $Url, not starting another one"
} else {
    # the router at the venue may hand out another IP than last time: point the QR link at the current one
    # before the app reads its config.
    if (-not $DryRun) {
        Push-Location $RepoRoot
        try {
            $qr = & uv run python kiosk/presets/apply_mirror_config.py --update-qr-ip 2>&1 | Select-Object -Last 1
            Write-Step "QR link: $qr"
        } catch {
            Write-Step "could not refresh the QR link: $_"
        } finally {
            Pop-Location
        }
    }
    Write-Step "starting backend (uv run photobooth) in $RepoRoot"
    if (-not $DryRun) {
        Start-Process -FilePath 'uv' -ArgumentList @('run', 'photobooth') -WorkingDirectory $RepoRoot -WindowStyle Hidden
    }
}

# --- 2. wait ----------------------------------------------------------------
if (-not $DryRun) {
    $deadline = (Get-Date).AddSeconds($StartupTimeoutSeconds)
    while (-not (Test-Backend)) {
        if ((Get-Date) -gt $deadline) {
            Write-Step "backend did not answer within $StartupTimeoutSeconds s, giving up"
            exit 1
        }
        Start-Sleep -Seconds 2
    }
    Write-Step "backend is up"
}

# --- 3. QR link check -------------------------------------------------------
$lanIp = Get-LanIp
$syncConfig = Join-Path $RepoRoot 'config\plugin_synchronizer.json'
if ($lanIp -and (Test-Path $syncConfig)) {
    $qrUrl = (Get-Content $syncConfig -Raw | ConvertFrom-Json).common.custom_qr_url
    if ($qrUrl -and ($qrUrl -notlike "*$lanIp*")) {
        Write-Step "WARNING: this PC's LAN IP is $lanIp but the QR link is '$qrUrl'. Guests' phones will not reach it. Update Admin > Synchronizer > Custom Qr Url."
    } else {
        Write-Step "QR link matches LAN IP $lanIp"
    }
}

# --- 4. browser -------------------------------------------------------------
$browser = Find-Browser
if (-not $browser) {
    Write-Step "no Edge or Chrome found"
    exit 1
}

# separate profile so kiosk state never mixes with the user's browsing, and a crash does not show a restore bubble
$profileDir = Join-Path $env:LOCALAPPDATA 'photobooth-kiosk-profile'
$browserArgs = @(
    '--kiosk', $Url,
    '--edge-kiosk-type=fullscreen',
    "--user-data-dir=$profileDir",
    '--no-first-run',
    '--no-default-browser-check',
    '--disable-session-crashed-bubble',
    '--disable-infobars',
    '--disable-pinch',
    '--overscroll-history-navigation=0',
    '--autoplay-policy=no-user-gesture-required'
)
Write-Step "opening $browser $($browserArgs -join ' ')"
if (-not $DryRun) {
    Start-Process -FilePath $browser -ArgumentList $browserArgs
}
