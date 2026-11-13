' Launch the 8BitDo Zero 2 key-mapping GUI with NO console window.
Option Explicit
Dim fso, sh, base, script, pyw, cmd
Set fso = CreateObject("Scripting.FileSystemObject")
Set sh = CreateObject("WScript.Shell")
base = fso.GetParentFolderName(WScript.ScriptFullName)
script = base & "\zero2_kb_gui.py"
pyw = sh.ExpandEnvironmentStrings("%LOCALAPPDATA%") & "\hermes\hermes-agent\venv\Scripts\pythonw.exe"
If Not fso.FileExists(pyw) Then
    pyw = sh.ExpandEnvironmentStrings("%WINDIR%") & "\pyw.exe"
End If
If Not fso.FileExists(pyw) Then
    pyw = "pythonw.exe"
End If
sh.CurrentDirectory = base
cmd = """" & pyw & """ """ & script & """"
On Error Resume Next
sh.Run cmd, 0, False
If Err.Number <> 0 Then
    MsgBox "Cannot start pythonw: " & Err.Description, 16, "8BitDo Zero 2"
End If
