# Find a UI Automation element by (partial) name and print its rectangle.
# Pure ASCII; run with Windows PowerShell 5.1.
param(
    [string]$ProcName = '8BitDo Firmware Updater',
    [string]$Match = 'Zero 2'
)
$ErrorActionPreference = 'Stop'
Add-Type -AssemblyName UIAutomationClient
Add-Type -AssemblyName UIAutomationTypes
$p = Get-Process -Name $ProcName -ErrorAction SilentlyContinue | Where-Object { $_.MainWindowHandle -ne 0 } | Select-Object -First 1
if (-not $p) { throw "window not found: $ProcName" }
$root = [System.Windows.Automation.AutomationElement]::RootElement
$cond = New-Object System.Windows.Automation.PropertyCondition([System.Windows.Automation.AutomationElement]::ProcessIdProperty, $p.Id)
$win = $root.FindFirst([System.Windows.Automation.TreeScope]::Children, $cond)
$all = $win.FindAll([System.Windows.Automation.TreeScope]::Descendants,
    [System.Windows.Automation.Condition]::TrueCondition)
Write-Host ("descendants: {0}" -f $all.Count)
foreach ($el in $all) {
    $n = $el.Current.Name
    if ($n -and $n -like "*$Match*") {
        $r = $el.Current.BoundingRectangle
        Write-Host ("name='{0}' type={1} offscreen={2} rect=({3},{4}) {5}x{6}" -f `
            $n, $el.Current.ControlType.ProgrammaticName, $el.Current.IsOffscreen, `
            [int]$r.X, [int]$r.Y, [int]$r.Width, [int]$r.Height)
    }
}
