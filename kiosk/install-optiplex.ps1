<#
.SYNOPSIS
  Installs the magic mirror on a fresh Windows PC (for example the OptiPlex).

.DESCRIPTION
  1. installs git and uv with winget if they are missing
  2. clones the backend repository (the compiled frontend is part of it, no Node needed)
  3. installs the dependencies (uv sync)
  4. configures the mirror: webcam, QR sharing, event title, photo strip (kiosk/presets/apply_mirror_config.py)
  5. registers the kiosk to start when the user logs on (kiosk/install-autostart.ps1)

  Safe to run again: an existing installation is updated and the settings are re-applied.

.EXAMPLE
  powershell -ExecutionPolicy Bypass -File install-optiplex.ps1 -Title "MIS XV LUCIA♥"

.PARAMETER DryRun
  Only print what would be done.
#>
[CmdletBinding()]
param(
    [string]$InstallDir = 'C:\photobooth',
    [string]$RepoUrl = 'https://github.com/sdarionicolas-boop/photobooth-app.git',
    [string]$Branch = 'feature/magic-mirror',
    [string]$Title,
    [string]$Camera = 'auto',
    [string]$AdminPassword,
    [switch]$NoAutostart,
    [switch]$DryRun
)

$ErrorActionPreference = 'Stop'
$RepoDir = Join-Path $InstallDir 'photobooth-app'

function Write-Step([string]$Message) { Write-Host "`n==> $Message" -ForegroundColor Cyan }

function Invoke-Native([string]$What, [scriptblock]$Command) {
    Write-Host "    $What"
    if ($DryRun) { return }
    & $Command
    if ($LASTEXITCODE -ne 0) { throw "failed: $What (exit code $LASTEXITCODE)" }
}

function Update-SessionPath {
    $env:Path = [Environment]::GetEnvironmentVariable('Path', 'Machine') + ';' + [Environment]::GetEnvironmentVariable('Path', 'User')
}

function Install-WithWinget([string]$Command, [string]$Id) {
    if (Get-Command $Command -ErrorAction SilentlyContinue) {
        Write-Host "    $Command found"
        return
    }
    if (-not (Get-Command winget -ErrorAction SilentlyContinue)) {
        throw "$Command is missing and winget is not available. Install '$Id' manually and run this script again."
    }
    Invoke-Native "winget install $Id" { winget install --id $Id -e --silent --accept-package-agreements --accept-source-agreements }
    Update-SessionPath
    if (-not $DryRun -and -not (Get-Command $Command -ErrorAction SilentlyContinue)) {
        throw "$Command was installed but is not on PATH yet. Open a new PowerShell window and run this script again."
    }
}

# --- questions --------------------------------------------------------------
if (-not $Title) {
    $Title = Read-Host 'Titulo del evento para la pantalla de inicio (ej: MIS XV LUCIA)'
}
if (-not $Title) { throw 'A title is required.' }

if (-not $AdminPassword) {
    $secure = Read-Host 'Contrasena de administrador (minimo 4 caracteres, Enter para dejar 0000)' -AsSecureString
    $AdminPassword = [Runtime.InteropServices.Marshal]::PtrToStringAuto([Runtime.InteropServices.Marshal]::SecureStringToBSTR($secure))
}

# --- 1. tools ---------------------------------------------------------------
Write-Step 'Checking tools'
Install-WithWinget 'git' 'Git.Git'
Install-WithWinget 'uv' 'astral-sh.uv'

# --- 2. code ----------------------------------------------------------------
Write-Step "Getting the code into $RepoDir"
if (Test-Path (Join-Path $RepoDir '.git')) {
    Invoke-Native 'git fetch' { git -C $RepoDir fetch origin }
    Invoke-Native "git checkout $Branch" { git -C $RepoDir checkout $Branch }
    Invoke-Native 'git pull' { git -C $RepoDir pull --ff-only }
} else {
    if (-not $DryRun) { New-Item -ItemType Directory -Force -Path $InstallDir | Out-Null }
    Invoke-Native "git clone $RepoUrl" { git clone --branch $Branch $RepoUrl $RepoDir }
}

# --- 3. dependencies --------------------------------------------------------
Write-Step 'Installing dependencies (first time takes a few minutes)'
if (-not $DryRun) { Push-Location $RepoDir }
try {
    Invoke-Native 'uv sync' { uv sync }

    # --- 4. configuration ---------------------------------------------------
    Write-Step 'Configuring the mirror'
    $configArgs = @('run', 'python', 'kiosk/presets/apply_mirror_config.py', '--title', $Title, '--camera', $Camera)
    if ($AdminPassword) { $configArgs += @('--admin-password', $AdminPassword) }
    Invoke-Native 'apply_mirror_config.py' { uv @configArgs }
} finally {
    if (-not $DryRun) { Pop-Location }
}

# --- 5. autostart -----------------------------------------------------------
if ($NoAutostart) {
    Write-Step 'Skipping autostart (-NoAutostart)'
} else {
    Write-Step 'Registering the kiosk to start at logon'
    if (-not $DryRun) { & (Join-Path $RepoDir 'kiosk\install-autostart.ps1') }
}

Write-Step 'Done'
Write-Host @"

Para abrirlo ahora:   & '$RepoDir\kiosk\start-kiosk.ps1'
Salir del kiosco:     Alt+F4

Falta hacer a mano en esta PC:
  - Girar la pantalla a vertical:  Configuracion > Sistema > Pantalla > Orientacion
  - Inicio de sesion automatico (para que arranque solo tras un corte de luz):  netplwiz
  - Conectar la webcam y la PC al router del evento (el QR usa la IP de la PC y se actualiza en cada arranque)
  - Cambiar el titulo: Admin > Configuracion > Uisettings > Frontpage Title
"@
