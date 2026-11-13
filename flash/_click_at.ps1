# Move the mouse to given screen coordinates and left-click.
# Pure ASCII; run with Windows PowerShell 5.1.
param(
    [int]$X = 1280,
    [int]$Y = 931
)
$ErrorActionPreference = 'Stop'
Add-Type -TypeDefinition @"
using System;
using System.Runtime.InteropServices;
public class W32ClickAt {
    [DllImport("user32.dll")] public static extern bool SetCursorPos(int x, int y);
    [DllImport("user32.dll")] public static extern void mouse_event(uint flags, uint dx, uint dy, int data, UIntPtr extra);
    public static void Click(int x, int y) {
        SetCursorPos(x, y);
        System.Threading.Thread.Sleep(150);
        mouse_event(0x0002, 0, 0, 0, UIntPtr.Zero);
        System.Threading.Thread.Sleep(80);
        mouse_event(0x0004, 0, 0, 0, UIntPtr.Zero);
    }
}
"@
Write-Host ("clicking at ({0},{1})" -f $X, $Y)
[W32ClickAt]::Click($X, $Y)
