#ifndef Payload
  #error Payload must point to a verified build
#endif
#ifndef OutputRoot
  #error OutputRoot is required
#endif
#ifndef ProductVersion
  #define ProductVersion "0.9.0-rc.1"
#endif
[Setup]
AppId={{9F7A96A3-86C8-4538-AC32-3C02E511B658}
AppName=Pauselith Preview
AppVersion={#ProductVersion}
AppVerName=Pauselith {#ProductVersion} (Preview)
VersionInfoVersion=0.9.0.1
AppPublisher=William Campos
DefaultDirName={localappdata}\Programs\KiyoCutPreview
DefaultGroupName=KiyoCut Preview
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
MinVersion=10.0
UsePreviousAppDir=yes
UsePreviousTasks=yes
CloseApplications=no
RestartApplications=no
UninstallDisplayIcon={app}\KiyoCut.exe
OutputDir={#OutputRoot}
OutputBaseFilename=KiyoCut-{#ProductVersion}-windows-x64-setup
Compression=lzma2/fast
SolidCompression=yes
WizardStyle=modern
SetupLogging=yes
InfoBeforeFile={#Payload}\DISTRIBUTION_STATUS.txt
[Tasks]
Name: desktopicon; Description: "Create a desktop shortcut"; Flags: unchecked
[Files]
Source: "{#Payload}\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs; Excludes: "portable.mode,data\*,jobs\*,logs\*,ajustes_usuario.json,__pycache__\*"
[Icons]
Name: "{group}\KiyoCut"; Filename: "{app}\KiyoCut.exe"; WorkingDir: "{app}"
Name: "{group}\Uninstall KiyoCut"; Filename: "{uninstallexe}"
Name: "{autodesktop}\KiyoCut Preview"; Filename: "{app}\KiyoCut.exe"; WorkingDir: "{app}"; Tasks: desktopicon
[Code]
function InitializeSetup(): Boolean;
var Framework: Cardinal;
begin
  Result := RegQueryDWordValue(HKLM, 'Software\Microsoft\NET Framework Setup\NDP\v4\Full', 'Release', Framework) and (Framework >= 533320);
  if not Result then
    MsgBox('Pauselith requires Microsoft .NET Framework 4.8.1. Install the Windows component from Microsoft, then run setup again.', mbError, MB_OK);
end;

function PrepareToInstall(var NeedsRestart: Boolean): String;
var Entry: TFindRec; Content: AnsiString; Occupied: Boolean;
begin
  Result := ''; Occupied := False;
  if FindFirst(ExpandConstant('{app}\*'), Entry) then begin
    try
      repeat
        if (Entry.Name <> '.') and (Entry.Name <> '..') then Occupied := True;
      until not FindNext(Entry);
    finally FindClose(Entry); end;
  end;
  if Occupied then
    if not LoadStringFromFile(ExpandConstant('{app}\kiyocut-preview.marker'), Content) or (Trim(String(Content)) <> '9F7A96A3-86C8-4538-AC32-3C02E511B658') then
      Result := 'Choose an empty folder. Setup will not replace an existing unrelated installation.';
end;
