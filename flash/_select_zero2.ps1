# Find the Zero 2 tile in the official updater product grid (UIA), scroll it into
# view and click it. Used by the GUI flasher after opening the product page.
# Pure ASCII; run with Windows PowerShell 5.1.
param(
    [string]$ProcName = '8BitDo Firmware Updater',
    [string]$Match = 'Zero 2'
)
$ErrorActionPreference = 'Stop'
Add-Type -AssemblyName UIAutomationClient
Add-Type -AssemblyName UIAutomationTypes
Add-Type -TypeDefinition @"
using System;
using System.Runtime.InteropServices;
public class Z2TileClick {
    [StructLayout(LayoutKind.Sequential)]
    public struct RECT { public int Left; public int Top; public int Right; public int Bottom; }
    [DllImport("user32.dll")] public static extern bool GetWindowRect(IntPtr hWnd, out RECT r);
    [DllImport("user32.dll")] public static extern bool SetForegroundWindow(IntPtr hWnd);
    [DllImport("user32.dll")] public static extern bool ShowWindow(IntPtr hWnd, int cmd);
    [DllImport("user32.dll")] public static extern bool SetCursorPos(int x, int y);
    [DllImport("user32.dll")] public static extern void mouse_event(uint flags, uint dx, uint dy, int data, UIntPtr extra);
}
"@
$p = Get-Process -Name $ProcName -ErrorAction SilentlyContinue | Where-Object { $_.MainWindowHandle -ne 0 } | Select-Object -First 1
if (-not $p) { throw "window not found: $ProcName" }
$hwnd = $p.MainWindowHandle
[Z2TileClick]::ShowWindow($hwnd, 9) | Out-Null
[Z2TileClick]::SetForegroundWindow($hwnd) | Out-Null
Start-Sleep -Milliseconds 500
$rect = New-Object Z2TileClick+RECT
[Z2TileClick]::GetWindowRect($hwnd, [ref]$rect) | Out-Null
$wheelX = [int]($rect.Left + ($rect.Right - $rect.Left) * 0.5)
$wheelY = [int]($rect.Top + ($rect.Bottom - $rect.Top) * 0.62)
$visTop = $rect.Top + 80
$visBottom = $rect.Bottom - 60
Write-Host ("window=({0},{1})..({2},{3}) wheel=({4},{5})" -f $rect.Left, $rect.Top, $rect.Right, $rect.Bottom, $wheelX, $wheelY)

$root = [System.Windows.Automation.AutomationElement]::RootElement
$cond = New-Object System.Windows.Automation.PropertyCondition(
    [System.Windows.Automation.AutomationElement]::ProcessIdProperty, $p.Id)
$win = $root.FindFirst([System.Windows.Automation.TreeScope]::Children, $cond)
if (-not $win) { throw 'AutomationElement not found' }
[Z2TileClick]::SetCursorPos($wheelX, $wheelY) | Out-Null
for ($i = 0; $i -lt 80; $i++) {
    $all = $win.FindAll([System.Windows.Automation.TreeScope]::Descendants,
        [System.Windows.Automation.Condition]::TrueCondition)
    $found = $null
    foreach ($el in $all) {
        if ($el.Current.Name -eq $Match) { $found = $el; break }
    }
    if (-not $found) { throw "tile not found: $Match" }
    $r = $found.Current.BoundingRectangle
    $cy = [int]($r.Y + $r.Height / 2)
    if ($cy -ge $visTop -and $cy -le $visBottom) {
        $cx = [int]($r.X + $r.Width / 2)
        [Z2TileClick]::SetCursorPos($cx, $cy) | Out-Null
        Start-Sleep -Milliseconds 120
        [Z2TileClick]::mouse_event(0x0002, 0, 0, 0, [UIntPtr]::Zero)
        Start-Sleep -Milliseconds 60
        [Z2TileClick]::mouse_event(0x0004, 0, 0, 0, [UIntPtr]::Zero)
        Write-Host ("clicked tile at ({0},{1})" -f $cx, $cy)
        exit 0
    }
    if ($cy -gt $visBottom) { [Z2TileClick]::mouse_event(0x0800, 0, 0, -360, [UIntPtr]::Zero) }
    elseif ($cy -lt $visTop) { [Z2TileClick]::mouse_event(0x0800, 0, 0, 360, [UIntPtr]::Zero) }
    Start-Sleep -Milliseconds 220
}
throw 'could not bring tile into view'
