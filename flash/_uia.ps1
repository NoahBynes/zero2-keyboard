# Dump the UI Automation tree of the 8BitDo updater window (text).
# Pure ASCII; run with Windows PowerShell 5.1.
param(
    [string]$ProcName = '8BitDo Firmware Updater',
    [int]$MaxDepth = 7
)
$ErrorActionPreference = 'Stop'
Add-Type -AssemblyName UIAutomationClient
Add-Type -AssemblyName UIAutomationTypes
$p = Get-Process -Name $ProcName -ErrorAction SilentlyContinue | Where-Object { $_.MainWindowHandle -ne 0 } | Select-Object -First 1
if (-not $p) { throw "window not found: $ProcName" }
$root = [System.Windows.Automation.AutomationElement]::RootElement
$cond = New-Object System.Windows.Automation.PropertyCondition([System.Windows.Automation.AutomationElement]::ProcessIdProperty, $p.Id)
$win = $root.FindFirst([System.Windows.Automation.TreeScope]::Children, $cond)
if (-not $win) { throw "AutomationElement not found" }
Write-Host ("window: '" + $win.Current.Name + "' class=" + $win.Current.ClassName + " pid=" + $p.Id)

function Show-Element($el, $depth) {
    if ($depth -gt $MaxDepth) { return }
    $pad = '  ' * $depth
    $name = $el.Current.Name
    $type = $el.Current.ControlType.ProgrammaticName
    $id = $el.Current.AutomationId
    $cls = $el.Current.ClassName
    $enabled = $el.Current.IsEnabled
    $patterns = @()
    foreach ($pt in @([System.Windows.Automation.InvokePattern]::Pattern, [System.Windows.Automation.SelectionItemPattern]::Pattern, [System.Windows.Automation.TogglePattern]::Pattern, [System.Windows.Automation.ExpandCollapsePattern]::Pattern)) {
        try { if ($el.TryGetCurrentPattern($pt, [ref]$null)) { $patterns += $pt.ProgrammaticName.Replace('PatternIdentifiers.Pattern', '') } } catch {}
    }
    Write-Host ("{0}[{1}] name='{2}' id='{3}' class='{4}' enabled={5} patterns={6}" -f $pad, $type, $name, $id, $cls, $enabled, ($patterns -join ','))
    $walker = [System.Windows.Automation.TreeWalker]::ControlViewWalker
    $child = $walker.GetFirstChild($el)
    while ($child -ne $null) {
        Show-Element $child ($depth + 1)
        $child = $walker.GetNextSibling($child)
    }
}
Show-Element $win 0
