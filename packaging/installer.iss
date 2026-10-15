#ifndef AppVersion
  #error AppVersion must be supplied by tools/build.py
#endif
[Setup]
AppId={{BA24C20E-62C5-4C3B-80B4-19B02C0DBBDB}
AppName=DeskTranslate 2
AppVersion={#AppVersion}
VersionInfoVersion={#FileVersion}
AppPublisher=DeskTranslate
AppPublisherURL=https://github.com/DeskTranslate/DeskTranslate
DefaultDirName={localappdata}\Programs\DeskTranslate
DefaultGroupName=DeskTranslate
PrivilegesRequired=lowest
MinVersion=10.0.19041
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
OutputDir=..\dist
OutputBaseFilename=DeskTranslate-{#AppVersion}-Setup-x64
SetupIconFile=..\build\icon.ico
UninstallDisplayIcon={app}\DeskTranslate.exe
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
DisableProgramGroupPage=yes
CloseApplications=yes
#ifdef SignedBuild
SignTool=DeskTranslate
SignedUninstaller=yes
#endif
[Files]
Source: "..\dist\DeskTranslate\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs
[Icons]
Name: "{group}\DeskTranslate 2"; Filename: "{app}\DeskTranslate.exe"
Name: "{autodesktop}\DeskTranslate 2"; Filename: "{app}\DeskTranslate.exe"; Tasks: desktopicon
[Tasks]
Name: "desktopicon"; Description: "Create a desktop shortcut"; Flags: unchecked
[Run]
Filename: "{app}\DeskTranslate.exe"; Description: "Launch DeskTranslate 2"; Flags: nowait postinstall skipifsilent

[Code]
function GetFileAttributes(Path: String): LongWord;
  external 'GetFileAttributesW@kernel32.dll stdcall';

function NoReparsePoints(Path: String): Boolean;
var
  Entry: TFindRec;
begin
  Result := False;
  if (GetFileAttributes(Path) and $400) <> 0 then exit;
  if FindFirst(AddBackslash(Path) + '*', Entry) then begin
    try
      repeat
        if (Entry.Name <> '.') and (Entry.Name <> '..') then begin
          if (Entry.Attributes and $400) <> 0 then exit;
          if (Entry.Attributes and FILE_ATTRIBUTE_DIRECTORY) <> 0 then
            if not NoReparsePoints(AddBackslash(Path) + Entry.Name) then exit;
        end;
      until not FindNext(Entry);
    finally
      FindClose(Entry);
    end;
  end;
  Result := True;
end;

function PrepareToInstall(var NeedsRestart: Boolean): String;
var
  AppPath, ParentPath, PreviousLocation: String;
  Marker: AnsiString;
  Owned: Boolean;
begin
  Result := '';
  AppPath := RemoveBackslashUnlessRoot(ExpandFileName(ExpandConstant('{app}')));
  ParentPath := AppPath;
  while Length(ParentPath) > 3 do begin
    if DirExists(ParentPath) and ((GetFileAttributes(ParentPath) and $400) <> 0) then begin
      Result := 'Choose an installation folder without directory links or junctions.';
      exit;
    end;
    PreviousLocation := ExtractFileDir(ParentPath);
    if PreviousLocation = ParentPath then break;
    ParentPath := PreviousLocation;
  end;
  if not DirExists(AddBackslash(AppPath) + '_internal') then exit;
  Owned := LoadStringFromFile(AddBackslash(AppPath) + 'managed-runtime.txt', Marker) and
    (Trim(String(Marker)) = 'DeskTranslate managed runtime v1');
  if not Owned then
    if RegQueryStringValue(HKCU, 'Software\Microsoft\Windows\CurrentVersion\Uninstall\{BA24C20E-62C5-4C3B-80B4-19B02C0DBBDB}_is1', 'InstallLocation', PreviousLocation) then
      Owned := CompareText(RemoveBackslashUnlessRoot(ExpandFileName(PreviousLocation)), AppPath) = 0;
  if not Owned then begin
    Result := 'This folder contains an unrecognized runtime. Choose an empty folder to keep existing files safe.';
    exit;
  end;
  if not NoReparsePoints(AddBackslash(AppPath) + '_internal') then
    Result := 'The existing runtime contains a directory link. Remove the link or choose an empty installation folder.';
end;

procedure CurStepChanged(CurStep: TSetupStep);
var
  RuntimePath: String;
begin
  if CurStep = ssInstall then begin
    RuntimePath := AddBackslash(ExpandFileName(ExpandConstant('{app}'))) + '_internal';
    if DirExists(RuntimePath) then begin
      if not NoReparsePoints(RuntimePath) then
        RaiseException('Runtime cleanup refused a directory link.');
      if not DelTree(RuntimePath, True, True, True) then
        RaiseException('The previous runtime is in use. Close DeskTranslate and retry installation.');
    end;
  end;
end;
