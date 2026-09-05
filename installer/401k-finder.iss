; Inno Setup script for 401K Finder Pro.
;
; Build the PyInstaller folder first (build.ps1 -Installer does both):
;   pyinstaller installer\401k-finder.spec --noconfirm
;   iscc installer\401k-finder.iss
;
; Produces dist\installer\401KFinderPro-Setup-<version>.exe

#define AppName "401K Finder Pro"
#define AppPublisher "401K Finder Pro"
#define AppExeName "401KFinderPro.exe"
#define CliExeName "401k-finder.exe"
#define AppId "{{9F1C2A64-7B3D-4E58-9C21-5D0A6E4F7B12}"

; Overridden by build.ps1 with /DAppVersion=...
#ifndef AppVersion
  #define AppVersion "1.0.0"
#endif

#define SourceDir "..\dist\401K Finder Pro"

[Setup]
AppId={#AppId}
AppName={#AppName}
AppVersion={#AppVersion}
AppVerName={#AppName} {#AppVersion}
AppPublisher={#AppPublisher}
DefaultDirName={autopf}\{#AppName}
DefaultGroupName={#AppName}
OutputDir=..\dist\installer
OutputBaseFilename=401KFinderPro-Setup-{#AppVersion}
Compression=lzma2/max
SolidCompression=yes
WizardStyle=modern
; "x64compatible" only exists from Inno Setup 6.3. On 6.0-6.2 it is an unknown
; value and aborts the compile, so select the spelling the compiler understands.
#if Ver >= EncodeVer(6,3,0,0)
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
#else
ArchitecturesAllowed=x64
ArchitecturesInstallIn64BitMode=x64
#endif

; Installing per-user by default means no administrator prompt, which matters
; because this is a research tool people often run on managed workstations.
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=dialog

UninstallDisplayName={#AppName} {#AppVersion}
UninstallDisplayIcon={app}\{#AppExeName}
DisableProgramGroupPage=yes
SetupLogging=yes

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "Create a &desktop shortcut"; GroupDescription: "Additional shortcuts:"

[Files]
; Naming the two executables explicitly makes the compile fail early and
; clearly if PyInstaller did not produce them. The wildcard then brings in
; _internal and everything else.
Source: "{#SourceDir}\{#AppExeName}"; DestDir: "{app}"; Flags: ignoreversion
Source: "{#SourceDir}\{#CliExeName}"; DestDir: "{app}"; Flags: ignoreversion
Source: "{#SourceDir}\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "..\README.md"; DestDir: "{app}"; DestName: "README.txt"; Flags: ignoreversion
Source: "..\docs\WINDOWS_APPLICATION.md"; DestDir: "{app}\docs"; Flags: ignoreversion skipifsourcedoesntexist
Source: "..\docs\DEPLOY.md"; DestDir: "{app}\docs"; Flags: ignoreversion skipifsourcedoesntexist

[Icons]
Name: "{group}\{#AppName}"; Filename: "{app}\{#AppExeName}"
Name: "{group}\Uninstall {#AppName}"; Filename: "{uninstallexe}"
; A shortcut that opens a prompt in the install folder, so the bundled
; command line is reachable without the user editing PATH.
Name: "{group}\{#AppName} command line"; Filename: "{cmd}"; Parameters: "/K 401k-finder.exe --help"; WorkingDir: "{app}"
Name: "{autodesktop}\{#AppName}"; Filename: "{app}\{#AppExeName}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#AppExeName}"; Description: "Start {#AppName}"; Flags: nowait postinstall skipifsilent

[UninstallDelete]
; The build's own leftovers only. The user's downloaded DOL data and database
; live in %LOCALAPPDATA% and are deliberately left in place. Re-downloading
; them takes hours, and an uninstall should not silently discard that work.
Type: filesandordirs; Name: "{app}\_internal\__pycache__"

[Messages]
BeveledLabel={#AppName}: U.S. Department of Labor Form 5500 research

[Code]
function InitializeSetup(): Boolean;
begin
  Result := True;
end;

// The bulk data can be moved to an external drive, in which case the pointer
// in {localappdata} names where it went. Read it so the uninstaller can say
// what it is about to remove and what it is going to leave behind.
function RelocatedStorage(PointerFile: String): String;
var
  Raw: AnsiString;
  Text: String;
  Marker, Colon, Opening, Closing: Integer;
begin
  Result := '';

  if not LoadStringFromFile(PointerFile, Raw) then
    Exit;

  Text := String(Raw);
  Marker := Pos('"path"', Text);
  if Marker = 0 then
    Exit;

  Colon := Marker + Length('"path"');
  Opening := Colon;
  while (Opening <= Length(Text)) and (Text[Opening] <> '"') do
    Opening := Opening + 1;
  if Opening > Length(Text) then
    Exit;

  Closing := Opening + 1;
  while (Closing <= Length(Text)) and (Text[Closing] <> '"') do
  begin
    // The pointer is written by json.dumps, so a Windows path arrives with
    // its backslashes doubled.
    if (Text[Closing] = '\') and (Closing < Length(Text)) then
      Closing := Closing + 1;
    Closing := Closing + 1;
  end;
  if Closing > Length(Text) then
    Exit;

  Result := Copy(Text, Opening + 1, Closing - Opening - 1);
  StringChange(Result, '\\', '\');
end;

procedure CurUninstallStepChanged(CurUninstallStep: TUninstallStep);
var
  DataDir, Elsewhere, Question: String;
begin
  if CurUninstallStep <> usPostUninstall then
    Exit;

  DataDir := ExpandConstant('{localappdata}\401K Finder Pro');
  if not DirExists(DataDir) then
    Exit;

  Elsewhere := RelocatedStorage(DataDir + '\storage.json');

  if Elsewhere <> '' then
  begin
    Question :=
      'Delete the settings, logs and licence key kept on this machine?' + #13#10 + #13#10
      + DataDir + #13#10 + #13#10
      + 'The plan database and downloaded Department of Labor data are not in '
      + 'that folder. They were moved to:' + #13#10 + #13#10
      + '    ' + Elsewhere + #13#10 + #13#10
      + 'That location is left untouched. Removing the folder above also '
      + 'removes the licence key and the record of where the data was moved, '
      + 'so a future installation has to be activated again and pointed back '
      + 'at that drive. Choose No to keep it.';
  end
  else
  begin
    Question :=
      'Also delete the downloaded Department of Labor data, the plan database '
      + 'and the licence key?' + #13#10 + #13#10
      + DataDir + #13#10 + #13#10
      + 'The data is public and can be downloaded again, but re-importing it '
      + 'can take several hours, and the licence key would have to be entered '
      + 'again. Choose No to keep it.';
  end;

  if MsgBox(Question, mbConfirmation, MB_YESNO or MB_DEFBUTTON2) = IDYES then
    DelTree(DataDir, True, True, True);
end;
