<#
.SYNOPSIS
Run the Kit tests of loupe.simulation.beckhoff_bridge through omni.kit.test.

.DESCRIPTION
Starts an empty Kit app from a kit-app-template build with omni.kit.test
enabled and lets it run the extension's test suite (the [[test]] section of
extension.toml) in its own process. The extension depends on the framework
loupe.simulation.bridge, so the exts\ folder of an Omni-Utils checkout has to
be on the search path too. The libraries come from the bundled wheels or from
tools\dev_link.py (see the root README). Exits with omni.kit.test's code: 0
when every test passed.

Kit is run from a temp folder: it puts its working directory on sys.path, and
from the repo root the bare beckhoff_bridge\ folder would import as an empty
namespace package ahead of the installed one.

.EXAMPLE
tools\kit_test.ps1 -Kit D:\kit-app-template\_build\windows-x86_64\release -Framework D:\Omni-Utils\exts
#>
[CmdletBinding()]
param(
    # Folder holding kit\kit.exe (a kit-app-template _build\<platform>\release).
    [string]$Kit = $env:FIXCHECK_KIT_ROOT,
    # Extension folder (default: this repo's exts\).
    [string]$Exts = $env:FIXCHECK_EXTS,
    # exts\ of an Omni-Utils checkout (default: ..\Omni-Utils\exts next to this repo).
    [string]$Framework = $env:FIXCHECK_FRAMEWORK_EXTS,
    # Where to keep Kit's output (default: kit_test.log in the current folder).
    [string]$Log = "kit_test.log"
)
$ErrorActionPreference = "Stop"
$repo = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
if (-not $Kit) { throw "need -Kit <kit build root> or FIXCHECK_KIT_ROOT" }
if (-not $Exts) { $Exts = Join-Path $repo "exts" }
if (-not $Framework) { $Framework = Join-Path (Split-Path $repo -Parent) "Omni-Utils\exts" }
if (-not (Test-Path (Join-Path $Framework "loupe.simulation.bridge"))) { throw "no loupe.simulation.bridge under $Framework; pass -Framework <Omni-Utils>\exts" }
if (-not [System.IO.Path]::IsPathRooted($Log)) { $Log = Join-Path (Get-Location).Path $Log }
function Native([string]$p) { (Resolve-Path $p).Path -replace "\\", "/" }
$Kit = Native $Kit
$Exts = Native $Exts
$Framework = Native $Framework

$work = Join-Path ([System.IO.Path]::GetTempPath()) ("kittest-" + [System.IO.Path]::GetRandomFileName())
New-Item -ItemType Directory -Path $work | Out-Null
Push-Location $work
try {
    & "$Kit/kit/kit.exe" --empty --enable omni.kit.test `
        --ext-folder "$Kit/exts" --ext-folder "$Kit/extscache" --ext-folder "$Kit/apps" `
        --ext-folder $Exts --ext-folder $Framework `
        --/app/extensions/registryEnabled=true `
        --/exts/omni.kit.test/testExts/0="loupe.simulation.beckhoff_bridge" `
        --/exts/omni.kit.test/runTestsAndQuit=true --no-window *> $Log
    $code = $LASTEXITCODE
}
finally {
    Pop-Location
    Remove-Item -Recurse -Force $work -ErrorAction SilentlyContinue
}
Get-Content $Log | Select-String -Pattern "^\|\| (test_|Ran |OK|FAILED)|^\[\s*(pass|fail)|Failing tests|^\[ERROR\]|^\[OK\]"
Write-Host "kit exit code $code (0 = all tests passed); log $Log"
exit $code
