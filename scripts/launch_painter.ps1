# Session-only plugin discovery. No registry or persistent environment changes.
[CmdletBinding()]
param(
    [string]$PainterExecutable,
    [switch]$Launch
)

$ErrorActionPreference = 'Stop'
$repository = Split-Path -Parent $PSScriptRoot
$distribution = Join-Path $repository 'painter_python'
$entryPoint = Join-Path $distribution 'plugins\MBToolkit_3DPainter\__init__.py'
if (-not (Test-Path -LiteralPath $entryPoint -PathType Leaf)) {
    throw "Plugin entry point missing: $entryPoint"
}

if (-not $PainterExecutable) {
    $PainterExecutable = Join-Path $env:ProgramFiles 'Adobe\Adobe Substance 3D Painter\Adobe Substance 3D Painter.exe'
}
if (-not (Test-Path -LiteralPath $PainterExecutable -PathType Leaf)) {
    throw 'Painter executable not found. Supply -PainterExecutable with its absolute path.'
}
$PainterExecutable = (Resolve-Path -LiteralPath $PainterExecutable).Path
$version = (Get-Item -LiteralPath $PainterExecutable).VersionInfo.ProductVersion
Write-Output "Painter executable: $PainterExecutable"
Write-Output "Executable product version (not runtime verification): $version"
Write-Output "Plugin distribution: $distribution"

# Do not guess how to merge an existing external-plugin search configuration.
$previous = $env:SUBSTANCE_PAINTER_PLUGINS_PATH
if ($previous -and $previous -ne $distribution) {
    throw "An external plugin search path is already set: $previous. Launch from a clean session or configure discovery explicitly."
}
if (-not $Launch) {
    Write-Output 'Preflight passed. Use -Launch to start Painter with session-only discovery.'
    return
}
if (Get-Process -Name 'Adobe Substance 3D Painter' -ErrorAction SilentlyContinue) {
    throw 'Painter is already running. Close it normally before using this launcher.'
}
try {
    $env:SUBSTANCE_PAINTER_PLUGINS_PATH = $distribution
    $process = Start-Process -FilePath $PainterExecutable -PassThru
    Write-Output "Painter launch requested. Process ID: $($process.Id). Plugin loading and UI remain to be verified."
}
finally {
    $env:SUBSTANCE_PAINTER_PLUGINS_PATH = $previous
}