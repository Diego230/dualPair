; Installer for DualPair for Windows (Inno Setup 6.3+). Built by CI:  iscc installer\DualPair.iss
#define AppVersion "0.4.1"

[Setup]
AppId={{8F2C4D3B-6E1A-4F7B-9C2D-1A5B3E7F9D10}
AppName=DualPair
AppVersion={#AppVersion}
AppVerName=DualPair {#AppVersion}
AppPublisher=DualPair
DefaultDirName={autopf}\DualPair
DefaultGroupName=DualPair
DisableProgramGroupPage=yes
PrivilegesRequired=admin
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
OutputDir=..\..\dist
OutputBaseFilename=DualPair-Setup-{#AppVersion}
SetupIconFile=..\app\DualPair.ico
UninstallDisplayIcon={app}\DualPair.exe
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
MinVersion=10.0

[Languages]
Name: "it"; MessagesFile: "compiler:Languages\Italian.isl"
Name: "en"; MessagesFile: "compiler:Default.isl"

[CustomMessages]
it.OpenApp=Apri DualPair
en.OpenApp=Open DualPair
it.Notices=DualPair (avvisi)
en.Notices=DualPair (notices)
it.Setting=Configurazione di DualPair...
en.Setting=Setting up DualPair...

[Files]
Source: "..\app\bin\Release\net48\DualPair.exe"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{group}\DualPair"; Filename: "{app}\DualPair.exe"
; at logon: tells the user if Linux sent keys or changed the clock (runs without administrator rights)
Name: "{commonstartup}\{cm:Notices}"; Filename: "{app}\DualPair.exe"; Parameters: "--notify"

[Run]
; creates the SYSTEM task "DualPair\Agent" and the protected %ProgramData%\DualPair folder
Filename: "{app}\DualPair.exe"; Parameters: "--install"; Flags: runhidden waituntilterminated; StatusMsg: "{cm:Setting}"
Filename: "{app}\DualPair.exe"; Description: "{cm:OpenApp}"; Flags: postinstall nowait skipifsilent shellexec

[UninstallRun]
; removes the task and %ProgramData%\DualPair (it holds backups of old keys)
Filename: "{app}\DualPair.exe"; Parameters: "--uninstall"; Flags: runhidden waituntilterminated; RunOnceId: "DualPairUninstall"
