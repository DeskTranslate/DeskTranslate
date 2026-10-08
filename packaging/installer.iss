#define AppVersion "2.0.0b1"
[Setup]
AppId={{BA24C20E-62C5-4C3B-80B4-19B02C0DBBDB}
AppName=DeskTranslate 2
AppVersion={#AppVersion}
AppPublisher=DeskTranslate
AppPublisherURL=https://github.com/DeskTranslate/DeskTranslate
DefaultDirName={localappdata}\Programs\DeskTranslate
DefaultGroupName=DeskTranslate
PrivilegesRequired=lowest
MinVersion=10.0.19041
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
OutputDir=..\dist
OutputBaseFilename=DeskTranslate-2.0.0b1-Setup-x64
SetupIconFile=..\build\icon.ico
UninstallDisplayIcon={app}\DeskTranslate.exe
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
DisableProgramGroupPage=yes
CloseApplications=yes
[Files]
Source: "..\dist\DeskTranslate\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs
[Icons]
Name: "{group}\DeskTranslate 2"; Filename: "{app}\DeskTranslate.exe"
Name: "{autodesktop}\DeskTranslate 2"; Filename: "{app}\DeskTranslate.exe"; Tasks: desktopicon
[Tasks]
Name: "desktopicon"; Description: "Create a desktop shortcut"; Flags: unchecked
[Run]
Filename: "{app}\DeskTranslate.exe"; Description: "Launch DeskTranslate 2"; Flags: nowait postinstall skipifsilent
