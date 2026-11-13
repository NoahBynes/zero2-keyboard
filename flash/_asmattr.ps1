param([string]$Exe)
Add-Type -AssemblyName System.Reflection
$asm=[System.Reflection.Assembly]::Load([System.IO.File]::ReadAllBytes($Exe))
foreach ($attr in $asm.GetCustomAttributes($false)) {
  $t = $attr.GetType().Name
  if ($t -match 'Company|Product|Title|Guid|FileVersion|Version') {
    $v = $null
    try { $v = $attr.Company } catch {}
    if (-not $v) { try { $v = $attr.Product } catch {} }
    if (-not $v) { try { $v = $attr.Title } catch {} }
    if (-not $v) { try { $v = $attr.Version } catch {} }
    Write-Output ("{0} = {1}" -f $t, $v)
  }
}
Write-Output ("Location = " + $asm.Location)
Write-Output ("FullName = " + $asm.FullName)
