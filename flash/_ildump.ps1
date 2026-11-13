# Tiny IL disassembler for the .NET updater (32-bit PS 5.1, pure ASCII).
# Usage: -TypeName HttpDownload [-Method Name]
param(
    [Parameter(Mandatory = $true)][string]$Exe,
    [string]$TypeName = 'HttpDownload',
    [string]$Method = ''
)
$ErrorActionPreference = 'Stop'
Add-Type -AssemblyName System.Reflection
$asm = [System.Reflection.Assembly]::Load([System.IO.File]::ReadAllBytes($Exe))
$types = $asm.GetTypes()
$flags = [System.Reflection.BindingFlags]'Public,NonPublic,Static,Instance'

function Get-OpMap {
    $map = @{}
    foreach ($f in [System.Reflection.Emit.OpCodes].GetFields([System.Reflection.BindingFlags]'Public,Static')) {
        $op = $f.GetValue($null)
        $val = [int]$op.Value
        if ($op.Size -eq 1) { $map[("1:{0}" -f $val)] = $op }
        else { $map[("2:{0}" -f $val)] = $op }
    }
    return $map
}
$opmap = Get-OpMap

function Decode-IL([byte[]]$il, [System.Reflection.Module]$mod) {
    $i = 0
    $out = New-Object System.Collections.ArrayList
    while ($i -lt $il.Length) {
        $start = $i
        $b = $il[$i]
        if ($b -eq 0xFE) { $key = "2:" + $il[$i + 1]; $i += 2 } else { $key = "1:" + $b; $i += 1 }
        $op = $opmap[$key]
        if (-not $op) { [void]$out.Add(("{0:x4}: ?? {1:x2}" -f $start, $b)); continue }
        $operand = ''
        $size = 0
        $tok = 0
        switch ($op.OperandType.ToString()) {
            'InlineNone' { }
            'ShortInlineI' { $operand = $il[$i]; $size = 1 }
            'ShortInlineVar' { $operand = $il[$i]; $size = 1 }
            'InlineVar' { $operand = [BitConverter]::ToUInt16($il, $i); $size = 2 }
            'InlineI' { $operand = [BitConverter]::ToInt32($il, $i); $size = 4 }
            'InlineI8' { $operand = [BitConverter]::ToInt64($il, $i); $size = 8 }
            'ShortInlineR' { $size = 4; $operand = 'float' }
            'InlineR' { $size = 8; $operand = 'double' }
            'ShortInlineBrTarget' { $v = [int]$il[$i]; if ($v -ge 128) { $v -= 256 }; $operand = ('IL_{0:x4}' -f ($i + 1 + $v)); $size = 1 }
            'InlineBrTarget' { $operand = ('IL_{0:x4}' -f ($i + 4 + [BitConverter]::ToInt32($il, $i))); $size = 4 }
            'InlineSwitch' { $n = [BitConverter]::ToInt32($il, $i); $operand = "switch[$n]"; $size = 4 + 4 * $n }
            default {
                $tok = [BitConverter]::ToInt32($il, $i)
                $size = 4
                try {
                    if ($op.OperandType.ToString() -match 'Method') { $operand = $mod.ResolveMethod($tok).DeclaringType.Name + '::' + $mod.ResolveMethod($tok).Name }
                    elseif ($op.OperandType.ToString() -match 'Field') { $operand = $mod.ResolveField($tok).Name }
                    elseif ($op.OperandType.ToString() -match 'Type') { $operand = $mod.ResolveType($tok).Name }
                    elseif ($op.OperandType.ToString() -match 'String') { $operand = '"' + $mod.ResolveString($tok) + '"' }
                    elseif ($op.OperandType.ToString() -match 'Sig') { $operand = 'sig' }
                    else { $operand = ('0x{0:x8}' -f $tok) }
                } catch { $operand = ('0x{0:x8}' -f $tok) }
            }
        }
        $i += $size
        [void]$out.Add(("{0:x4}: {1,-10} {2}" -f $start, $op.Name, $operand))
    }
    return $out
}

$matched = $types | Where-Object { $_.Name -eq $TypeName -or $_.Name -like "*$TypeName*" }
if (-not $matched) { Write-Host "types matching:"; $types | Where-Object { $_.Name -match 'Download|Http' } | ForEach-Object { Write-Host ("  " + $_.FullName) }; exit 1 }
Write-Host ("== type {0} ==" -f ($matched | ForEach-Object { $_.FullName }) -join ', ')
foreach ($t in $matched) {
    Write-Host ("`n== {0} ==" -f $t.FullName)
    foreach ($m in $t.GetMethods($flags)) {
        if ($Method -and $m.Name -notmatch $Method) { continue }
        $body = $null
        try { $body = $m.GetMethodBody() } catch { }
        if (-not $body) { continue }
        $il = $body.GetILAsByteArray()
        Write-Host ("`n--- {0}.{1}({2}) ---" -f $t.Name, $m.Name, (($m.GetParameters() | ForEach-Object { $_.ParameterType.Name }) -join ','))
        if ($il.Length -gt 1500) { Write-Host ("  (IL {0} bytes, showing first 1500)" -f $il.Length); $il = $il[0..1499] }
        Decode-IL $il $asm.ManifestModule | ForEach-Object { Write-Host ('  ' + $_) }
    }
}

