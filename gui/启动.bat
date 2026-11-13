@echo off
rem No console window: hand off to the VBS launcher (wscript), then exit.
start "" wscript.exe //nologo "%~dp0启动.vbs"
exit /b
