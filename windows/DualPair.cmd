@echo off
rem Opens DualPair for Windows (DualPair.ps1 in the same folder). Asks for administrator rights.
start "" powershell.exe -NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -File "%~dp0DualPair.ps1"
