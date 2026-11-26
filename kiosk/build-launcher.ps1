<#
.SYNOPSIS
  Builds "Espejo.exe" (the event panel) in the app folder, using the C# compiler included in Windows.
  Optionally puts a shortcut on the desktop.
#>
[CmdletBinding()]
param([switch]$DesktopShortcut)

$ErrorActionPreference = 'Stop'
$RepoRoot = Split-Path -Parent $PSScriptRoot
$csc = Join-Path $env:WINDIR 'Microsoft.NET\Framework64\v4.0.30319\csc.exe'
if (-not (Test-Path $csc)) { throw "C# compiler not found at $csc" }

$out = Join-Path $RepoRoot 'Espejo.exe'
& $csc /nologo /target:winexe /optimize "/out:$out" /r:System.Windows.Forms.dll /r:System.Drawing.dll (Join-Path $PSScriptRoot 'launcher\Espejo.cs')
if ($LASTEXITCODE -ne 0) { throw 'compilation failed' }
Write-Host "built $out"

if ($DesktopShortcut) {
    $lnk = Join-Path ([Environment]::GetFolderPath('Desktop')) 'Espejo.lnk'
    $sh = (New-Object -ComObject WScript.Shell).CreateShortcut($lnk)
    $sh.TargetPath = $out
    $sh.WorkingDirectory = $RepoRoot
    $sh.Save()
    Write-Host "shortcut: $lnk"
}
