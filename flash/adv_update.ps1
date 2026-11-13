# Try the legacy "advance USB" path of the flashing DLL against the bootloader:
#   FindHid(0483:5760) -> setAdvanceUSB() -> _updateGampeWithFile(file)
# 32-bit PowerShell only. Pure ASCII.
param(
    [Parameter(Mandatory = $true)][string]$Dat
)
$ErrorActionPreference = 'Stop'
if ([IntPtr]::Size -ne 4) { throw 'Run with 32-bit PowerShell.' }
$root = Split-Path -Parent $PSScriptRoot
$updaterDir = Join-Path $root '_fw-tools\win\8BitDo_Firmware_Updater_Win'
$dllPath = Join-Path $updaterDir '8BitDoFirmwareUpdaterTools.dll'
$Dat = [System.IO.Path]::GetFullPath($Dat)
Set-Location $updaterDir

Add-Type -TypeDefinition @"
using System;
using System.Runtime.InteropServices;
public static class Z2Adv {
    [DllImport("kernel32", CharSet = CharSet.Unicode, SetLastError = true)]
    public static extern IntPtr LoadLibraryW(string path);
    [DllImport("kernel32", SetLastError = true)]
    public static extern bool SetDllDirectoryW(string path);
    [DllImport("8BitDoFirmwareUpdaterTools.dll", EntryPoint = "FindHid", CallingConvention = CallingConvention.Winapi)]
    public static extern bool FindHid(ushort vid, ushort pid);
    [DllImport("8BitDoFirmwareUpdaterTools.dll", EntryPoint = "setAdvanceUSB", CallingConvention = CallingConvention.Winapi)]
    public static extern void SetAdvanceUSB();
    [DllImport("8BitDoFirmwareUpdaterTools.dll", EntryPoint = "_updateGampeWithFile@4", CallingConvention = CallingConvention.StdCall, CharSet = CharSet.Ansi, ExactSpelling = true)]
    public static extern void UpdateWithFile(string path);
    [DllImport("8BitDoFirmwareUpdaterTools.dll", EntryPoint = "_dll_getProgress@0", CallingConvention = CallingConvention.StdCall, ExactSpelling = true)]
    public static extern int GetProgress();
}
"@
[void][Z2Adv]::SetDllDirectoryW($updaterDir)
[void][Z2Adv]::LoadLibraryW($dllPath)
Write-Host ("[i] FindHid = {0}" -f [Z2Adv]::FindHid(0x0483, 0x5760))
Write-Host '[i] setAdvanceUSB()'
[Z2Adv]::SetAdvanceUSB()
Write-Host '[i] updateWithFile'
[Z2Adv]::UpdateWithFile($Dat)
Write-Host '[i] returned, polling progress'
for ($i = 0; $i -lt 120; $i++) {
    Start-Sleep -Seconds 1
    try { $p = [Z2Adv]::GetProgress() } catch { Write-Host ("[warn] progress: " + $_.Exception.Message); break }
    if ($i % 2 -eq 0) { Write-Host ("[i] t+{0}s progress={1}" -f ($i + 1), $p) }
}
Write-Host '[i] done'
