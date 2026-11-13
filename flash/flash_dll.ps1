# Call the official 8BitDo flashing library directly (32-bit PowerShell only).
# The app's P/Invoke wrapper was identified by reflection:
#   _8BitDoFirmwareUpdater.View.UpdateView.dll_updateGampeWithFile -> Void(String)
#     entry point: updateGampeWithFile (PE32 export: _updateGampeWithFile@4)
#
# Usage (32-bit!):
#   %WINDIR%\SysWOW64\WindowsPowerShell\v1.0\powershell.exe -ExecutionPolicy Bypass -File .\flash_dll.ps1 -Dat ..\firmware-patch\out\Zero2_V1.09_identify.dat
#   add -SmokeTest to only load the DLL and query a benign function.
#
# Pure ASCII.
param(
    [Parameter(Mandatory = $true)][string]$Dat,
    [switch]$SmokeTest
)
$ErrorActionPreference = 'Stop'
if ([IntPtr]::Size -ne 4) {
    throw 'Run this script with 32-bit PowerShell: %WINDIR%\SysWOW64\WindowsPowerShell\v1.0\powershell.exe'
}
$root = Split-Path -Parent $PSScriptRoot
$updaterDir = Join-Path $root '_fw-tools\win\8BitDo_Firmware_Updater_Win'
$dllPath = Join-Path $updaterDir '8BitDoFirmwareUpdaterTools.dll'
if (-not (Test-Path $dllPath)) { throw "DLL not found: $dllPath" }
$Dat = [System.IO.Path]::GetFullPath($Dat)
if (-not (Test-Path $Dat)) { throw "firmware not found: $Dat" }

Set-Location -Path $updaterDir
Write-Host "[i] cwd       : $updaterDir"
Write-Host "[i] DLL       : $dllPath"
Write-Host "[i] firmware  : $Dat"

Add-Type -TypeDefinition @"
using System;
using System.Runtime.InteropServices;
public static class Z2Native {
    [DllImport("kernel32", CharSet = CharSet.Unicode, SetLastError = true)]
    public static extern IntPtr LoadLibraryW(string path);
    [DllImport("kernel32", SetLastError = true)]
    public static extern IntPtr GetProcAddress(IntPtr h, string name);
    [DllImport("kernel32", SetLastError = true)]
    public static extern bool SetDllDirectoryW(string path);
    [DllImport("8BitDoFirmwareUpdaterTools.dll", EntryPoint = "_updateGampeWithFile@4", CallingConvention = CallingConvention.StdCall, CharSet = CharSet.Ansi, ExactSpelling = true)]
    public static extern void UpdateGamepadWithFile(string path);
    [DllImport("8BitDoFirmwareUpdaterTools.dll", EntryPoint = "_dll_getProgress@0", CallingConvention = CallingConvention.StdCall, ExactSpelling = true)]
    public static extern int GetProgress();
    [DllImport("8BitDoFirmwareUpdaterTools.dll", EntryPoint = "_dll_errorUpdate@0", CallingConvention = CallingConvention.StdCall, ExactSpelling = true)]
    public static extern int GetError();
    [DllImport("8BitDoFirmwareUpdaterTools.dll", EntryPoint = "dll_getType", CallingConvention = CallingConvention.StdCall, ExactSpelling = true)]
    public static extern uint GetType2();
}
"@
[void][Z2Native]::SetDllDirectoryW($updaterDir)
$h = [Z2Native]::LoadLibraryW($dllPath)
Write-Host ("[i] LoadLibrary handle: {0}" -f $h)
if ($h -eq [IntPtr]::Zero) { throw "LoadLibrary failed: $([ComponentModel.Win32Exception]::new([Runtime.InteropServices.Marshal]::GetLastWin32Error()).Message)" }
$p1 = [Z2Native]::GetProcAddress($h, '_updateGampeWithFile@4')
$p2 = [Z2Native]::GetProcAddress($h, '_dll_getProgress@0')
Write-Host ("[i] GetProcAddress update={0} progress={1}" -f $p1, $p2)
if ($SmokeTest) { try { Write-Host ("[i] dll_getType() = {0}" -f [Z2Native]::GetType2()) } catch { Write-Host ("[warn] dll_getType failed: " + $_.Exception.Message) } }
try { Write-Host ("[i] dll_getProgress() = {0}" -f [Z2Native]::GetProgress()) } catch { Write-Host ("[warn] getProgress failed: " + $_.Exception.Message) }
if ($SmokeTest) { Write-Host '[i] smoke test done'; exit 0 }

Write-Host '[i] calling _updateGampeWithFile@4 (returns immediately, flashing runs in background)'
[Z2Native]::UpdateGamepadWithFile($Dat)
Write-Host '[i] call returned; watching data\updateLog.txt (no more DLL calls while flashing)'
$log = Join-Path $updaterDir 'data\updateLog.txt'
$last = ''
for ($i = 0; $i -lt 180; $i++) {
    Start-Sleep -Seconds 1
    if (Test-Path $log) {
        $tail = Get-Content $log -Tail 3 -ErrorAction SilentlyContinue
        $line = ($tail -join ' | ')
        if ($line -ne $last) { Write-Host ("[i] t+{0}s log: {1}" -f ($i + 1), $line); $last = $line }
        if ($line -match 'update end|Update complete|更新结束') { Write-Host '[i] log indicates the flash finished'; break }
    }
}
Write-Host '[i] done watching'

