# One-shot helper:
#   1. start the local firmware proxy,
#   2. point the user proxy at it,
#   3. launch the official 8BitDo Firmware Updater,
#   4. restore everything after the updater exits.
# Run it from a normal PowerShell window (no admin needed):
#   powershell -ExecutionPolicy Bypass -File .\flash_with_proxy.ps1
#   powershell -ExecutionPolicy Bypass -File .\flash_with_proxy.ps1 -Patched ..\firmware-patch\out\Zero2_V1.09_drawing.dat
param(
    [string]$Patched = '',
    [double]$Version = 1.09,
    [int]$Port = 8888,
    [switch]$KeepProxy
)
$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $PSScriptRoot
if (-not $Patched) {
    $Patched = Join-Path $root 'firmware-patch\out\Zero2_V1.09_identify.dat'
}
$Patched = [System.IO.Path]::GetFullPath($Patched)
if (-not (Test-Path $Patched)) { throw "patched firmware not found: $Patched" }

$pythonCmd = Get-Command python -ErrorAction SilentlyContinue
if (-not $pythonCmd) { throw 'Python not found in PATH. Install Python 3.8+ or start the proxy manually.' }
$python = $pythonCmd.Source

$proxyScript = Join-Path $PSScriptRoot 'patched_updater_proxy.py'
$setProxy = Join-Path $PSScriptRoot 'set_proxy.ps1'
$updater = Join-Path $root '_fw-tools\win\8BitDo_Firmware_Updater_Win\8BitDo Firmware Updater.exe'
if (-not (Test-Path $updater)) { throw "official updater not found: $updater" }

Write-Host "== starting local firmware proxy =="
$proxyProc = Start-Process -FilePath $python -ArgumentList @($proxyScript, '--patched', $Patched, '--version', $Version, '--port', $Port) -WorkingDirectory $PSScriptRoot -PassThru
Start-Sleep -Seconds 2
if ($proxyProc.HasExited) { throw "proxy exited early, run it manually to see the error" }

Write-Host "== pointing Windows proxy at 127.0.0.1:$Port =="
& $setProxy -Port $Port

Write-Host "== launching 8BitDo Firmware Updater =="
Write-Host "   1) Put the controller into BOOT mode: power it off, hold L + R + START, plug in USB."
Write-Host "   2) In the updater choose the manual/advanced mode and select '8BitDo Zero 2 gamepad'."
Write-Host "   3) It should offer version 1.09. Click Update and do NOT unplug during flashing."
Write-Host "   4) Close the updater when it finishes; this script then restores your proxy."
$up = Start-Process -FilePath $updater -PassThru
$up.WaitForExit()

if (-not $KeepProxy) {
    Write-Host "== restoring previous proxy settings =="
    & $setProxy -Off
} else {
    Write-Host "[keep] proxy left enabled on 127.0.0.1:$Port"
}
Stop-Process -Id $proxyProc.Id -Force -ErrorAction SilentlyContinue
Write-Host "[done] Now unplug USB, power the controller on with the normal combo and test."
