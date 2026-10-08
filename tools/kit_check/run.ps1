<#
.SYNOPSIS
Headless Kit check for the Beckhoff bridge (see README.md).

.DESCRIPTION
Generates a .kit from fixcheck.kit.template (with ${FIXCHECK_EXTS},
${FIXCHECK_FRAMEWORK_EXTS} and ${FIXCHECK_KIT_ROOT} substituted), runs kit.exe without a window with
kit_check.py as --exec, and prints the check's output. Kit exits with code 7
by design: the script quits the app itself and os._exit(7)s if a dirty stage
keeps it alive. This script exits 0 when the log holds
"OK -- all fix checks passed", 1 otherwise.

Every parameter can come from the environment instead: FIXCHECK_KIT_ROOT,
FIXCHECK_EXTS, FIXCHECK_FRAMEWORK_EXTS, FIXCHECK_STAGE, FIXCHECK_MODE, FIXCHECK_LOG.

.EXAMPLE
tools\kit_check\run.ps1 -Kit D:\kit-app-template\_build\windows-x86_64\release -Mode inject
#>
[CmdletBinding()]
param(
    # Folder holding kit\kit.exe (a kit-app-template _build\<platform>\release).
    [string]$Kit = $env:FIXCHECK_KIT_ROOT,
    # Extension folder to load (default: this repo's exts\).
    [string]$Exts = $env:FIXCHECK_EXTS,
    # exts\ of an Omni-Utils checkout, for loupe.simulation.bridge (default: ..\Omni-Utils\exts next to this repo).
    [string]$Framework = $env:FIXCHECK_FRAMEWORK_EXTS,
    # Stage to open (default: stages\beckhoff_test.usda next to this script).
    [string]$Stage = $env:FIXCHECK_STAGE,
    # "inject" = synthetic data, no PLC; "live" = the PLC named in the stage.
    [ValidateSet("", "inject", "live")]
    [string]$Mode = $env:FIXCHECK_MODE,
    # Where to keep Kit's output.
    [string]$Log = $env:FIXCHECK_LOG
)
$ErrorActionPreference = "Stop"

$here = $PSScriptRoot
$repo = (Resolve-Path (Join-Path $here "..\..")).Path
if (-not $Kit) { throw "need -Kit <kit build root> or FIXCHECK_KIT_ROOT" }
if (-not $Exts) { $Exts = Join-Path $repo "exts" }
if (-not $Framework) { $Framework = Join-Path (Split-Path $repo -Parent) "Omni-Utils\exts" }
if (-not (Test-Path (Join-Path $Framework "loupe.simulation.bridge"))) { throw "no loupe.simulation.bridge under $Framework; pass -Framework <Omni-Utils>\exts" }
if (-not $Stage) { $Stage = Join-Path $here "stages\beckhoff_test.usda" }
if (-not $Log) { $Log = "kit_check.log" }
if ($Mode -eq "live") { $Mode = "" }
if (-not [System.IO.Path]::IsPathRooted($Log)) { $Log = Join-Path (Get-Location).Path $Log }

# Kit wants forward slashes, and TOML strings would read backslashes as escapes.
function Native([string]$p) { (Resolve-Path $p).Path -replace "\\", "/" }
$Kit = Native $Kit
$Exts = Native $Exts
$Framework = Native $Framework
$Stage = Native $Stage

$kitExe = "$Kit/kit/kit.exe"
if (-not (Test-Path $kitExe)) { throw "no kit/kit.exe under $Kit" }

$work = Join-Path ([System.IO.Path]::GetTempPath()) ("fixcheck-" + [System.IO.Path]::GetRandomFileName())
New-Item -ItemType Directory -Path $work | Out-Null
try {
    $kitFile = Join-Path $work "fixcheck.kit"
    (Get-Content (Join-Path $here "fixcheck.kit.template") -Raw).
        Replace('${FIXCHECK_EXTS}', $Exts).
        Replace('${FIXCHECK_FRAMEWORK_EXTS}', $Framework).
        Replace('${FIXCHECK_KIT_ROOT}', $Kit) |
        Set-Content -Path $kitFile -NoNewline -Encoding utf8

    Write-Host "kit    $kitExe"
    Write-Host "exts   $Exts"
    Write-Host "bridge $Framework"
    Write-Host "stage  $Stage"
    Write-Host "mode   $(if ($Mode) { $Mode } else { 'live' })"
    Write-Host "log    $Log"

    $env:FIXCHECK_STAGE = $Stage
    $env:FIXCHECK_MODE = $Mode
    # Kit puts its working directory on sys.path. Run it from the temp folder so a
    # repo checkout's bare package folders (beckhoff_bridge\ at the root) cannot be
    # picked up as empty namespace packages ahead of the installed ones.
    Push-Location $work
    & $kitExe $kitFile `
        --ext-folder "$Kit/exts" `
        --ext-folder "$Kit/extscache" `
        --ext-folder "$Kit/apps" `
        --ext-folder $Exts `
        --ext-folder $Framework `
        --no-window --exec (Native (Join-Path $here "kit_check.py")) *> $Log
    $code = $LASTEXITCODE
    Pop-Location
}
finally {
    Remove-Item -Recurse -Force $work -ErrorAction SilentlyContinue
}

# Kit's own timestamped lines ("2026-...") are left in the log; show the check itself.
$lines = Get-Content $Log
$start = ($lines | Select-String -Pattern "^fix check -- " | Select-Object -First 1).LineNumber
if ($start) { $lines[($start - 1)..($lines.Count - 1)] | Where-Object { $_ -notmatch "^20\d\d-" } }
Write-Host "kit exit code $code (7 = quit forced after the check, expected)"
if ($lines -match "^OK -- all fix checks passed") { exit 0 } else { exit 1 }
