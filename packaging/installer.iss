#define MyAppName "Omnivert"
; The version is passed in, never guessed. This used to fall back to a hardcoded string
; that went stale two releases running, and because the version names the output file, a
; local build of 0.1.5 silently produced Omnivert-Setup-0.1.3.exe. CI always passes the
; flag (release.yml), so this only ever fires for a hand-run compile, where being told is
; better than being surprised. Pass it as:
;   ISCC.exe /DMyAppVersion=x.y.z packaging\installer.iss
#ifndef MyAppVersion
  #error MyAppVersion is not defined. Pass /DMyAppVersion=x.y.z (see README, Packaging).
#endif
#define MyAppPublisher "Omnivert"
#define MyAppExeName "Omnivert.exe"

[Setup]
AppId={{6AA4DC6C-DD15-4CD2-9ECB-36887540712E}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
DefaultDirName={localappdata}\Programs\Omnivert
DefaultGroupName={#MyAppName}
DisableProgramGroupPage=yes
OutputDir=..\dist\installer
OutputBaseFilename=Omnivert-Setup-{#MyAppVersion}
Compression=lzma
SolidCompression=yes
WizardStyle=modern
PrivilegesRequired=lowest
CloseApplications=yes
RestartApplications=no
UninstallDisplayIcon={app}\{#MyAppExeName}
SetupIconFile=omnivert.ico
LicenseFile=..\LICENSE

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "Create a desktop shortcut"; GroupDescription: "Additional shortcuts:"; Flags: unchecked

[InstallDelete]
; Wipe the previous release's payload before laying down this one.
;
; Inno only ADDS and overwrites; it never removes a file that a newer release stopped
; shipping. PyInstaller's onedir layout renames files, drops dependencies, and puts the
; version in every dist-info directory name, so without this an upgrade quietly
; accumulates the release before it.
;
; Measured upgrading 0.1.3 to 0.1.6 before this existed: 17 packages ended up with TWO
; dist-info directories, markitdown-0.1.6.dist-info from June sitting beside
; markitdown-0.1.7.dist-info from the new build. importlib.metadata.version() then
; returned the OLDER one, so the Capabilities dialog told the user they were running an
; engine the build does not contain, and every dependency version in that dialog was
; equally unreliable. Conversions still worked, because the code was new and only the
; metadata was stale, which is exactly why nothing caught it before an install test did.
;
; Only _internal is removed. Omnivert.exe is overwritten by [Files] below, and settings
; live in %LOCALAPPDATA%\Omnivert rather than here, so nothing the user owns is touched.
Type: filesandordirs; Name: "{app}\_internal"

[Files]
Source: "..\dist\Omnivert\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon

[Run]
; Refresh the Windows icon cache so an in-place update repaints Start/desktop/taskbar
; shortcuts with the new logo immediately, instead of serving the previously cached icon.
Filename: "{sys}\ie4uinit.exe"; Parameters: "-show"; Flags: runhidden skipifdoesntexist
Filename: "{app}\{#MyAppExeName}"; Description: "Launch {#MyAppName}"; Flags: nowait postinstall skipifsilent
