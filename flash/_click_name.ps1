# Click a UI Automation element by exact/partial name (Invoke pattern or mouse).
# Pure ASCII; run with Windows PowerShell 5.1.
param(
    [string]$ProcName = '8BitDo Firmware Updater',
    [string]$Match = '更新'
)
$ErrorActionPreference = 'Stop'
Add-Type -AssemblyName UIAutomationClient
Add-Type -AssemblyName UIAutomationTypes
Add-Type -TypeDefinition @"
using System;
using System.Runtime.InteropServices;
public class W32Click2 {
    [DllImport("user32.dll")] public static extern bool SetCursorPos(int x, int y);
    [DllImport("user32.dll")] public static extern void mouse_event(uint flags, uint dx, uint dy, int data, UIntPtr extra);
    public static void Click(int x, int y) {
        SetCursorPos(x, y);
        System.Threading.Thread.Sleep(120);
        mouse_event(0x0002, 0, 0, 0, UIntPtr.Zero);
        System.Threading.Thread.Sleep(60);
        mouse_event(0x0004, 0, 0, 0, UIntPtr.Zero);
    }
}
"@
$p = Get-Process -Name $ProcName -ErrorAction SilentlyContinue | Where-Object { $_.MainWindowHandle -ne 0 } | Select-Object -First 1
if (-not $p) { throw "window not found: $ProcName" }
$root = [System.Windows.Automation.AutomationElement]::RootElement
$cond = New-Object System.Windows.Automation.PropertyCondition([System.Windows.Automation.AutomationElement]::ProcessIdProperty, $p.Id)
$win = $root.FindFirst([System.Windows.Automation.TreeScope]::Children, $cond)
$all = $win.FindAll([System.Windows.Automation.TreeScope]::Descendants, [System.Windows.Automation.Condition]::TrueCondition)
$target = $null
foreach ($el in $all) {
    $n = $el.Current.Name
    if ($n -and ($n -eq $Match -or $n -like "*$Match*")) {
        if ($el.Current.ControlType.ProgrammaticName -eq 'ControlType.Button' -or $n -eq $Match) { $target = $el; if ($n -eq $Match) { break } }
    }
}
if (-not $target) { throw "element not found: $Match" }
$r = $target.Current.BoundingRectangle
Write-Host ("target name='{0}' type={1} rect=({2},{3}) {4}x{5}" -f $target.Current.Name, $target.Current.ControlType.ProgrammaticName, [int]$r.X, [int]$r.Y, [int]$r.Width, [int]$r.Height)
$invoked = $false
try {
    $pattern = $null
    if ($target.TryGetCurrentPattern([System.Windows.Automation.InvokePattern]::Pattern, [ref]$pattern)) {
        $pattern.Invoke()
        $invoked = $true
        Write-Host 'invoked via InvokePattern'
    }
} catch { Write-Host ("InvokePattern failed: " + $_.Exception.Message) }
if (-not $invoked) {
    $cx = [int]($r.X + $r.Width / 2)
    $cy = [int]($r.Y + $r.Height / 2)
    Write-Host ("mouse click at ({0},{1})" -f $cx, $cy)
    [W32Click2]::Click($cx, $cy)
}
