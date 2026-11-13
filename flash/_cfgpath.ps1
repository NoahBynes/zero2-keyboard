Add-Type -AssemblyName System.Configuration
$asm = [System.Configuration.ConfigurationManager].Assembly
$t = $asm.GetType("System.Configuration.ClientConfigPaths")
$flags = [System.Reflection.BindingFlags]"NonPublic,Static,Public"
$m = $t.GetMethod("GetCurrent", $flags)
$p = $m.Invoke($null, @($true))
Write-Output ("UserConfigFilename=" + $p.UserConfigFilename)
Write-Output ("CompanyName=" + $p.CompanyName)
Write-Output ("ConfigFilePath=" + $p.ConfigFilePath)
