# Build a custom-keyboard Zero 2 firmware from a JSON mapping file.
# Pure ASCII (Windows PowerShell 5.1 ANSI reading).
#
# Examples:
#   .\build_custom.ps1 -Profile custom-template.json -Version 111
#   .\build_custom.ps1 -Profile drawing.json -Version 112 -Name my_drawing.dat
param(
    [Parameter(Mandatory = $true)][string]$Profile,
    [int]$Version = 109,
    [string]$Name = ''
)
$ErrorActionPreference = 'Stop'
$py = Get-Command python -ErrorAction SilentlyContinue
if (-not $py) { throw 'Python not found in PATH' }
$root = Split-Path -Parent $PSScriptRoot
$fw = Join-Path $PSScriptRoot 'Zero2_V1.08.dat'
if (-not (Test-Path $fw)) { throw "official firmware missing: $fw (see README: fetch via firmware-patch/_tools)" }
if (-not $Profile.Contains('\')) { $Profile = Join-Path $PSScriptRoot ('profiles\' + $Profile) }
if (-not (Test-Path $Profile)) { throw "profile not found: $Profile" }
if (-not $Name) { $Name = 'Zero2_V{0}_custom.dat' -f $Version }
$outDir = Join-Path $PSScriptRoot 'out'
New-Item -ItemType Directory -Force -Path $outDir | Out-Null
$out = Join-Path $outDir $Name
& $py.Source (Join-Path $PSScriptRoot 'patch_fw.py') patch $fw --mapping $Profile --version $Version --out $out
if ($LASTEXITCODE -ne 0) { throw 'patch_fw.py failed' }
Write-Host "[ok] built $out (header version $Version)"
$adv = [double]$Version / 100.0
Write-Host ("     flash it with:  ..\flash\flash_with_proxy.ps1 -Patched `"{0}`" -Version {1:0.00}" -f $out, $adv)
