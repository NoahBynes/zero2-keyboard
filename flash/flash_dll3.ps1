# Try the "advance USB" initialization path of the official flashing DLL:
#   FindHid(vid,pid) -> setAdvanceUSB() -> [getBootVersion] -> _updateGampeWithFile(path)
# Pure ASCII, 32-bit PowerShell only.
param(
    [string]$Dat = '',
    [int]$Vid = 0x0483,
    [int]$ProductId = 0x5760,
    [switch]$NoUpdate
)
$ErrorActionPreference = 'Stop'
if ([IntPtr]::Size -ne 4) { throw 'Run with 32-bit PowerShell (SysWOW64).' }
$root = Split-Path -Parent $PSScriptRoot
$updaterDir = Join-Path $root '_fw-tools\win\8BitDo_Firmware_Updater_Win'
$dllPath = Join-Path $updaterDir '8BitDoFirmwareUpdaterTools.dll'
Set-Location $updaterDir
if (-not $Dat) { $Dat = Join-Path $root 'firmware-patch\out\Zero2_V1.09_identify.dat' }
$Dat = [System.IO.Path]::GetFullPath($Dat)

Add-Type -TypeDefinition @"
using System;
using System.Runtime.InteropServices;
public static class Z2Dll3 {
    [DllImport("kernel32", CharSet = CharSet.Unicode, SetLastError = true)]
    public static extern IntPtr LoadLibraryW(string path);
    [DllImport("kernel32", SetLastError = true)]
    public static extern bool SetDllDirectoryW(string path);
    [DllImport("8BitDoFirmwareUpdaterTools.dll", EntryPoint = "FindHid", CallingConvention = CallingConvention.Winapi)]
    public static extern bool FindHid(ushort vid, ushort pid);
    [DllImport("8BitDoFirmwareUpdaterTools.dll", EntryPoint = "setAdvanceUSB", CallingConvention = CallingConvention.Winapi)]
    public static extern void SetAdvanceUSB();
    [DllImport("8BitDoFirmwareUpdaterTools.dll", EntryPoint = "dll_getBootVersion", CallingConvention = CallingConvention.Winapi)]
    public static extern float GetBootVersion();
    [DllImport("8BitDoFirmwareUpdaterTools.dll", EntryPoint = "_dll_getProgress@0", CallingConvention = CallingConvention.StdCall, ExactSpelling = true)]
    public static extern int GetProgress();
    [DllImport("8BitDoFirmwareUpdaterTools.dll", EntryPoint = "_updateGampeWithFile@4", CallingConvention = CallingConvention.StdCall, CharSet = CharSet.Ansi, ExactSpelling = true)]
    public static extern void UpdateWithFile(string path);
}
"@
[void][Z2Dll3]::SetDllDirectoryW($updaterDir)
[void][Z2Dll3]::LoadLibraryW($dllPath)
Write-Host ("[i] FindHid = {0}" -f [Z2Dll3]::FindHid([uint16]$Vid, [uint16]$ProductId))
Write-Host '[i] setAdvanceUSB()'
[Z2Dll3]::SetAdvanceUSB()
Write-Host '[i] setAdvanceUSB returned'
try { Write-Host ("[i] bootVersion = {0}" -f [Z2Dll3]::GetBootVersion()) } catch { Write-Host ("[warn] bootVersion: " + $_.Exception.Message) }
if ($NoUpdate) { Write-Host '[i] -NoUpdate, stop'; exit 0 }
Write-Host ("[i] update({0})" -f $Dat)
[Z2Dll3]::UpdateWithFile($Dat)
Write-Host '[i] update returned; sleeping 120s (watch updateLog.txt)'
for ($i = 0; $i -lt 120; $i++) { Start-Sleep -Seconds 1 }
Write-Host '[i] done'
