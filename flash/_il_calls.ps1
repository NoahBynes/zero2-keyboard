# Inspect the IL of methods that call dll_updateGampeWithFile, and print the
# DllImport details. 32-bit PS 5.1, pure ASCII.
param(
    [Parameter(Mandatory = $true)][string]$Exe
)
$ErrorActionPreference = 'Stop'
Add-Type -AssemblyName System.Reflection
$asm = [System.Reflection.Assembly]::Load([System.IO.File]::ReadAllBytes($Exe))
$types = $asm.GetTypes()
$flags = [System.Reflection.BindingFlags]'Public,NonPublic,Static,Instance'

$wrapper = $null
foreach ($t in $types) {
    foreach ($m in $t.GetMethods($flags)) {
        if ($m.Name -eq 'dll_updateGampeWithFile') { $wrapper = $m }
    }
}
if (-not $wrapper) { throw 'wrapper not found' }
Write-Host ("wrapper: {0}.{1} token=0x{2:x8}" -f $wrapper.DeclaringType.FullName, $wrapper.Name, $wrapper.MetadataToken)
foreach ($a in $wrapper.GetCustomAttributes([System.Runtime.InteropServices.DllImportAttribute], $false)) {
    Write-Host ("  DllImport: dll='{0}' entry='{1}' calling={2} charset={3} exact={4}" -f $a.Value, $a.EntryPoint, $a.CallingConvention, $a.CharSet, $a.ExactSpelling)
}
$token = $wrapper.MetadataToken

function Get-IL([System.Reflection.MethodBase]$m) {
    try {
        $body = $m.GetMethodBody()
        if (-not $body) { return $null }
        return $body.GetILAsByteArray()
    } catch { return $null }
}

$hits = 0
foreach ($t in $types) {
    foreach ($m in $t.GetMethods($flags)) {
        $il = Get-IL $m
        if (-not $il) { continue }
        for ($i = 0; $i -lt $il.Length - 4; $i++) {
            if ($il[$i] -eq 0x28 -or $il[$i] -eq 0x6F) {
                $tok = [BitConverter]::ToInt32($il, $i + 1) -band 0xFFFFFFFF
                if ($tok -eq $token) {
                    $hits++
                    Write-Host ("`nCALLER: {0}.{1}" -f $t.FullName, $m.Name)
                    Write-Host ("  IL ({0} bytes): {1}" -f $il.Length, ([BitConverter]::ToString($il)))
                    break
                }
            }
        }
    }
}
Write-Host ("`ncallers found: {0}" -f $hits)
