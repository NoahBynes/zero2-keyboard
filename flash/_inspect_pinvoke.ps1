# Inspect P/Invoke declarations inside the .NET updater assembly (32-bit PS 5.1).
# Pure ASCII.
param(
    [Parameter(Mandatory = $true)][string]$Exe
)
$ErrorActionPreference = 'Stop'
Add-Type -AssemblyName System.Reflection
$bytes = [System.IO.File]::ReadAllBytes($Exe)
$asm = [System.Reflection.Assembly]::Load($bytes)
Write-Host ("assembly: " + $asm.FullName)
try {
    $types = $asm.GetTypes()
} catch [System.Reflection.ReflectionTypeLoadException] {
    Write-Host "partial type load:"
    $_.Exception.LoaderExceptions | ForEach-Object { Write-Host ("  " + $_.Message) }
    $types = $_.Exception.Types | Where-Object { $_ -ne $null }
}
Write-Host ("types: {0}" -f $types.Count)

$flags = ([System.Reflection.BindingFlags]::Public -bor
          [System.Reflection.BindingFlags]::NonPublic -bor
          [System.Reflection.BindingFlags]::Static -bor
          [System.Reflection.BindingFlags]::Instance)
$found = 0
foreach ($t in $types) {
    $methods = $null
    try { $methods = $t.GetMethods($flags) } catch { continue }
    foreach ($m in $methods) {
        $att = $m.GetCustomAttributes([System.Runtime.InteropServices.DllImportAttribute], $false)
        if (-not $att -or $att.Count -eq 0) { continue }
        $a = $att[0]
        $params = ($m.GetParameters() | ForEach-Object { $_.ParameterType.Name + " " + $_.Name }) -join ', '
        Write-Host ("[{0}.{1}] -> {2}!{3} : {4}({5})" -f $t.FullName, $m.Name, $a.Value, $a.EntryPoint, $m.ReturnType.Name, $params)
        $found++
    }
}
Write-Host ("P/Invoke methods found: {0}" -f $found)
