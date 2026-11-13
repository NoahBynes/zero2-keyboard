# Set / restore the per-user WinINET HTTP proxy that the 8BitDo updater uses.
# Pure ASCII on purpose (Windows PowerShell 5.1 reads .ps1 as ANSI otherwise).
param(
    [int]$Port = 8888,
    [switch]$Off
)
$ErrorActionPreference = 'Stop'
$regPath = 'HKCU:\Software\Microsoft\Windows\CurrentVersion\Internet Settings'
$backup = Join-Path $PSScriptRoot 'proxy-backup.json'

if (-not $Off) {
    $cur = Get-ItemProperty -Path $regPath
    $bak = [ordered]@{
        ProxyEnable = $cur.ProxyEnable
        ProxyServer = $cur.ProxyServer
    }
    $bak | ConvertTo-Json | Set-Content -Path $backup -Encoding Ascii
    Set-ItemProperty -Path $regPath -Name ProxyServer -Value ("127.0.0.1:{0}" -f $Port)
    Set-ItemProperty -Path $regPath -Name ProxyEnable -Value 1
    Write-Host "[ok] HTTP proxy -> 127.0.0.1:$Port (backup saved to $backup)"
    Write-Host "     Close and reopen the 8BitDo updater so it picks up the proxy."
    Write-Host "     Restore later with:  .\set_proxy.ps1 -Off"
} else {
    if (Test-Path $backup) {
        $bak = Get-Content -Path $backup -Raw | ConvertFrom-Json
        Set-ItemProperty -Path $regPath -Name ProxyServer -Value ([string]$bak.ProxyServer)
        Set-ItemProperty -Path $regPath -Name ProxyEnable -Value ([int]$bak.ProxyEnable)
        Write-Host "[ok] proxy restored (ProxyEnable=$($bak.ProxyEnable), ProxyServer=$($bak.ProxyServer))"
    } else {
        Set-ItemProperty -Path $regPath -Name ProxyEnable -Value 0
        Write-Host "[ok] no backup found, proxy disabled"
    }
}
