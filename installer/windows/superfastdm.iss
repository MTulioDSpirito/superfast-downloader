; superfastdm.iss — Inno Setup script do SuperFast DM (Windows)
; Compile com o Inno Setup (File > Compile) -> output\SuperFastDM-Setup.exe
; Requer: Inno Setup 6 (https://jrsoftware.org/isinfo.php)

#define MyAppName "SuperFast DM"
#define MyAppVersion "1.1"
#define MyAppPublisher "SuperFast DM"
#define MyAppURL "https://github.com/MTulioDSpirito/superfast-downloader"
#define MyAppExeName "SuperFastDM.bat"

[Setup]
AppId={{B7C2A9F1-3E5D-4A8B-9C6F-1D2E8A4B7C90}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
AppPublisherURL={#MyAppURL}
AppSupportURL={#MyAppURL}
DefaultDirName={autopf}\SuperFastDM
DefaultGroupName={#MyAppName}
DisableProgramGroupPage=yes
OutputDir=output
OutputBaseFilename=SuperFastDM-Setup
SetupIconFile=superfastdm.ico
UninstallDisplayIcon={app}\superfastdm.ico
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
ArchitecturesInstallIn64BitMode=x64compatible
PrivilegesRequired=admin
PrivilegesRequiredOverridesAllowed=dialog

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"
Name: "brazilianportuguese"; MessagesFile: "compiler:Languages\BrazilianPortuguese.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"

[Files]
; código do app (stdlib) — copiado na raiz do diretório de instalação
Source: "..\..\app\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs
; launcher + ícone + utilidades
Source: "SuperFastDM.bat"; DestDir: "{app}"; Flags: ignoreversion
Source: "stop-superfastdm.bat"; DestDir: "{app}"; Flags: ignoreversion
Source: "superfastdm.ico"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{group}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"
Name: "{group}\Parar o SuperFast DM"; Filename: "{app}\stop-superfastdm.bat"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "{cm:LaunchProgram,{#StringChange(MyAppName, '&', '&&')}}"; Flags: nowait postinstall skipifsilent
