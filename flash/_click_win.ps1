# Foreground the updater window, then click at window-relative coordinates.
# Pure ASCII; run with Windows PowerShell 5.1.
param(
    [string]$ProcName = '8BitDo Firmware Updater',
    [int]$LocalX = 400,
    [int]$LocalY = 560,
    [switch]$DumpForeground
)
$ErrorActionPreference = 'Stop'
Add-Type -TypeDefinition @"
using System;
using System.Runtime.InteropServices;
public class W32WinClick {
    [StructLayout(LayoutKind.Sequential)]
    public struct RECT { public int Left; public int Top; public int Right; public int Bottom; }
    [DllImport("user32.dll")] public static extern bool GetWindowRect(IntPtr hWnd, out RECT r);
    [DllImport("user32.dll")] public static extern bool SetForegroundWindow(IntPtr hWnd);
    [DllImport("user32.dll")] public static extern bool ShowWindow(IntPtr hWnd, int cmd);
    [DllImport("user32.dll")] public static extern IntPtr GetForegroundWindow();
    [DllImport("user32.dll")] public static extern bool SetCursorPos(int x, int y);
    [DllImport("user32.dll")] public static extern void mouse_event(uint flags, uint dx, uint dy, int data, UIntPtr extra);
    public static void Click(int x, int y) {
        SetCursorPos(x, y);
        System.Threading.Thread.Sleep(150);
        mouse_event(0x0002, 0, 0, 0, UIntPtr.Zero);
        System.Threading.Thread.Sleep(80);
        mouse_event(0x0004, 0, 0, 0, UIntPtr.Zero);
    }
    public static IntPtr Foreground() { return GetForegroundWindow(); }
}
"@
$p = Get-Process -Name $ProcName -ErrorAction SilentlyContinue | Where-Object { $_.MainWindowHandle -ne 0 } | Select-Object -First 1
if (-not $p) { throw "window not found: $ProcName" }
$h = $p.MainWindowHandle
[W32WinClick]::ShowWindow($h, 9) | Out-Null
[W32WinClick]::SetForegroundWindow($h) | Out-Null
Start-Sleep -Milliseconds 700
if ($DumpForeground) {
    Write-Host ("foreground hwnd={0} target hwnd={1}" -f [W32WinClick]::Foreground(), $h)
}
$r = New-Object W32WinClick+RECT
[W32WinClick]::GetWindowRect($h, [ref]$r) | Out-Null
$x = $r.Left + $LocalX
$y = $r.Top + $LocalY
Write-Host ("window rect=({0},{1}); clicking window-local ({2},{3}) -> screen ({4},{5})" -f $r.Left, $r.Top, $LocalX, $LocalY, $x, $y)
[W32WinClick]::Click($x, $y)
