# Alternative to the proxy: hijack dl.8bitdo.com via the hosts file and run the
# local server on port 8080. Requires an elevated (Administrator) PowerShell.
# Pure ASCII (Windows PowerShell 5.1 ANSI reading).
param(
    [switch]$Off
)
$ErrorActionPreference = 'Stop'

$id = [Security.Principal.WindowsIdentity]::GetCurrent()
$principal = New-Object Security.Principal.WindowsPrincipal $id
if (-not $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
    throw 'This script must be run as Administrator (hosts file is protected).'
}

$hosts = Join-Path $env:WINDIR 'System32\drivers\etc\hosts'
$markerBegin = '# >>> zero2-keyboard patched firmware BEGIN >>>'
$markerEnd = '# <<< zero2-keyboard patched firmware END <<<'
$lines = @(
    $markerBegin,
    '127.0.0.1 dl.8bitdo.com',
    '127.0.0.1 dl.8bitdo.cn',
    '127.0.0.1 beta.8bitdo.com',
    $markerEnd
)

$content = Get-Content -Path $hosts -Raw
if ($Off) {
    $pattern = [regex]::Escape($markerBegin) + '.*?' + [regex]::Escape($markerEnd) + '\s*'
    $new = [regex]::Replace($content, $pattern, '', 'Singleline')
    Set-Content -Path $hosts -Value $new.TrimEnd() -Encoding ASCII
    Write-Host '[ok] hosts entries removed. Flush DNS: ipconfig /flushdns'
} else {
    if ($content -match [regex]::Escape($markerBegin)) {
        Write-Host '[ok] hosts entries already present'
    } else {
        $backup = Join-Path $PSScriptRoot 'hosts.backup'
        Copy-Item -Path $hosts -Destination $backup -Force
        $text = $content.TrimEnd() + "`r`n`r`n" + ($lines -join "`r`n") + "`r`n"
        Set-Content -Path $hosts -Value $text -Encoding ASCII
        Write-Host "[ok] hosts entries added (backup: $backup)"
    }
    Write-Host 'Next: run the local server on port 8080 in another window:'
    Write-Host '  python ..\patched_updater_proxy.py --patched ..\firmware-patch\out\Zero2_V1.09_identify.dat --port 8080'
    Write-Host 'Then open the 8BitDo updater (no system proxy needed).'
    Write-Host 'Undo later with: .\hosts_hijack.ps1 -Off'
}
ipconfig /flushdns | Out-Null
