# Verify that a .NET Framework (Windows PowerShell 5.1) program honours the
# per-user WinINET proxy and that our local firmware proxy answers correctly.
# Usage:
#   1) start proxy:  python patched_updater_proxy.py --patched out\Zero2_V1.09_identify.dat
#   2) set proxy:    .\set_proxy.ps1
#   3) run:          powershell -ExecutionPolicy Bypass -File .\verify_proxy.ps1
#   4) restore:      .\set_proxy.ps1 -Off
# Pure ASCII (Windows PowerShell 5.1 ANSI reading).
param(
    [string]$Url = 'http://dl.8bitdo.com:8080/firmware/select',
    [string]$Type = '30'
)
$ErrorActionPreference = 'Stop'
Write-Host ("PowerShell {0} / .NET {1} / 64-bit={2}" -f $PSVersionTable.PSVersion, $PSVersionTable.CLRVersion, [Environment]::Is64BitProcess)
try {
    $req = [System.Net.WebRequest]::Create($Url)
    $req.Method = 'POST'
    $req.ContentLength = 0
    $req.Headers.Add('Beta', '1')
    $req.Headers.Add('Type', $Type)
    $req.Timeout = 15000
    $resp = $req.GetResponse()
    $sr = New-Object System.IO.StreamReader($resp.GetResponseStream())
    $text = $sr.ReadToEnd()
    Write-Host ("[ok] response {0} bytes:" -f $text.Length)
    Write-Host $text.Substring(0, [Math]::Min(400, $text.Length))
} catch {
    Write-Host ("[fail] " + $_.Exception.Message)
    Write-Host 'If the local proxy log shows no request, .NET ignored the WinINET proxy; use hosts_hijack.ps1 instead.'
    exit 1
}
