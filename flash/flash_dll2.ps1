# Replicate the official updater's DLL call order in a clean 32-bit process:
#   FindHid(vid,pid) -> Open_Hid() -> dll_getType() -> _updateGampeWithFile(path)
# This avoids the updater UI holding an extra HID handle on the same device.
# Pure ASCII; run with 32-bit PowerShell.
param(
    [Parameter(Mandatory = $true)][string]$Dat,
    [int]$Vid = 0x0483,
    [int]$ProductId = 0x5760,
    [switch]$NoUpdate
)
$ErrorActionPreference = 'Stop'
if ([IntPtr]::Size -ne 4) { throw 'Run with 32-bit PowerShell (SysWOW64).' }
$root = Split-Path -Parent $PSScriptRoot
$updaterDir = Join-Path $root '_fw-tools\win\8BitDo_Firmware_Updater_Win'
$dllPath = Join-Path $updaterDir '8BitDoFirmwareUpdaterTools.dll'
if (-not (Test-Path $dllPath)) { throw "DLL not found: $dllPath" }
$Dat = [System.IO.Path]::GetFullPath($Dat)
if (-not (Test-Path $Dat)) { throw "firmware not found: $Dat" }
Set-Location $updaterDir

Add-Type -TypeDefinition @"
using System;
using System.Runtime.InteropServices;
public static class Z2Dll {
    [DllImport("kernel32", CharSet = CharSet.Unicode, SetLastError = true)]
    public static extern IntPtr LoadLibraryW(string path);
    [DllImport("kernel32", SetLastError = true)]
    public static extern bool SetDllDirectoryW(string path);
    [DllImport("8BitDoFirmwareUpdaterTools.dll", EntryPoint = "FindHid", CallingConvention = CallingConvention.Winapi)]
    public static extern bool FindHid(ushort vid, ushort pid);
    [DllImport("8BitDoFirmwareUpdaterTools.dll", EntryPoint = "Open_Hid", CallingConvention = CallingConvention.Winapi)]
    public static extern bool OpenHid();
    [DllImport("8BitDoFirmwareUpdaterTools.dll", EntryPoint = "dll_getType", CallingConvention = CallingConvention.Winapi)]
    public static extern uint GetTypeDll();
    [DllImport("8BitDoFirmwareUpdaterTools.dll", EntryPoint = "_dll_getBootVersion_beta@0", CallingConvention = CallingConvention.StdCall, ExactSpelling = true)]
    public static extern uint GetBootVersionBeta();
    [DllImport("8BitDoFirmwareUpdaterTools.dll", EntryPoint = "_dll_getProgress@0", CallingConvention = CallingConvention.StdCall, ExactSpelling = true)]
    public static extern int GetProgress();
    [DllImport("8BitDoFirmwareUpdaterTools.dll", EntryPoint = "_dll_errorUpdate@0", CallingConvention = CallingConvention.StdCall, ExactSpelling = true)]
    public static extern int GetError();
    [DllImport("8BitDoFirmwareUpdaterTools.dll", EntryPoint = "_updateGampeWithFile@4", CallingConvention = CallingConvention.StdCall, CharSet = CharSet.Ansi, ExactSpelling = true)]
    public static extern void UpdateWithFile(string path);
}
"@
[void][Z2Dll]::SetDllDirectoryW($updaterDir)
$h = [Z2Dll]::LoadLibraryW($dllPath)
Write-Host ("[i] LoadLibrary: {0}" -f $h)
Write-Host ("[i] FindHid(0x{0:x4}, 0x{1:x4}) = {2}" -f $Vid, $ProductId, [Z2Dll]::FindHid([uint16]$Vid, [uint16]$ProductId))
Write-Host ("[i] Open_Hid() = {0}" -f [Z2Dll]::OpenHid())
try { Write-Host ("[i] dll_getType() = 0x{0:x8}" -f [Z2Dll]::GetTypeDll()) } catch { Write-Host ("[warn] dll_getType: " + $_.Exception.Message) }
try { Write-Host ("[i] bootVersionBeta() = {0}" -f [Z2Dll]::GetBootVersionBeta()) } catch { Write-Host ("[warn] bootVersionBeta: " + $_.Exception.Message) }
try { Write-Host ("[i] progress() = {0} error() = {1}" -f [Z2Dll]::GetProgress(), [Z2Dll]::GetError()) } catch { Write-Host ("[warn] progress/error: " + $_.Exception.Message) }
if ($NoUpdate) { Write-Host '[i] -NoUpdate set, stopping'; exit 0 }
Write-Host ("[i] calling _updateGampeWithFile@4({0})" -f $Dat)
[Z2Dll]::UpdateWithFile($Dat)
Write-Host '[i] returned; sleeping 120s while the DLL works (check updateLog.txt)'
for ($i = 0; $i -lt 120; $i++) { Start-Sleep -Seconds 1 }
Write-Host '[i] done'

