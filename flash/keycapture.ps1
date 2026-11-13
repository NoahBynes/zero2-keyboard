# Zero 2 keyboard-mode key capture window v2 (Windows PowerShell 5.1).
# Catches command keys (Tab/Esc/Enter/arrows/PageUp/Home/End/Delete/Backspace) via
# ProcessCmdKey as well as normal keys, so Tab is logged too.
# Pure ASCII on purpose.
param(
    [string]$LogPath = "$PSScriptRoot\_keys.log"
)
$ErrorActionPreference = 'Stop'
Add-Type -AssemblyName System.Windows.Forms
Add-Type -AssemblyName System.Drawing
$refs = @(
    [System.Windows.Forms.Form].Assembly.Location,
    [System.Drawing.Color].Assembly.Location
)
Add-Type -TypeDefinition @"
using System;
using System.Windows.Forms;
public class Z2CaptureForm : Form {
    public event EventHandler<KeyEventArgs> CommandKey;
    protected override bool ProcessCmdKey(ref Message msg, Keys keyData) {
        Keys k = keyData & Keys.KeyCode;
        if (k != Keys.None && CommandKey != null) {
            CommandKey(this, new KeyEventArgs(keyData));
        }
        return true;
    }
}
"@ -ReferencedAssemblies $refs
$logFull = [System.IO.Path]::GetFullPath($LogPath)
if (Test-Path $logFull) { Remove-Item $logFull -Force -ErrorAction SilentlyContinue }
$script:count = 0

$form = New-Object Z2CaptureForm
$form.Text = 'Zero2 key capture v2 - press all 12 buttons'
$form.Size = New-Object System.Drawing.Size(640, 460)
$form.StartPosition = 'CenterScreen'
$form.TopMost = $true
$form.KeyPreview = $true
$form.BackColor = [System.Drawing.Color]::White

$label = New-Object System.Windows.Forms.Label
$label.Text = "1) Click this window once so it has focus.`r`n2) Order: UP DOWN LEFT RIGHT SELECT START A B X Y L R`r`nTab/Esc/Enter are now captured too. Close with the X button when done.`r`n"
$label.Dock = 'Top'
$label.Height = 92
$label.Font = New-Object System.Drawing.Font('Consolas', 9)
$form.Controls.Add($label)

$box = New-Object System.Windows.Forms.TextBox
$box.Multiline = $true
$box.ScrollBars = 'Vertical'
$box.Dock = 'Fill'
$box.ReadOnly = $true
$box.Font = New-Object System.Drawing.Font('Consolas', 12)
$form.Controls.Add($box)
[void]$form.Controls.SetChildIndex($label, 0)

function Write-Key($e) {
    $script:count++
    $line = ("{0:HH:mm:ss.fff}`t{1}`t{2}`t{3}" -f (Get-Date), $e.KeyCode, ([int]$e.KeyCode), $e.Modifiers)
    Add-Content -Path $logFull -Value $line
    $box.AppendText(("$($script:count).  " + $e.KeyCode.ToString() + '   code=' + [int]$e.KeyCode + '   ' + $e.Modifiers + "`r`n"))
}

$form.add_KeyDown({ param($s, $e) Write-Key $e })
$form.add_CommandKey({ param($s, $e) Write-Key $e })
$form.add_Shown({
    $form.Activate()
    $form.TopMost = $true
    $form.Focus()
})
Write-Host "logging keys to: $logFull"
[System.Windows.Forms.Application]::Run($form)
