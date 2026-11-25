; Instalador por usuario (no pide permisos de administrador). Lo compila scripts\crear_release.bat (que pasa AppVersion, DistDir y la carpeta de salida)
#ifndef DistDir
  #define DistDir "..\dist\TallyMonitor"
#endif
#ifndef AppVersion
  #define AppVersion "0.0.0"
#endif
#if FileExists("..\src\tally_monitor\assets\logo.ico")
  #define HasIcon
#endif
[Setup]
AppId={{B3C5E2A1-7D4F-4E8A-9A55-7A1F0C2D9E11}
AppName=Tally Monitor
AppVersion={#AppVersion}
AppPublisher=Tally Monitor
DefaultDirName={localappdata}\Programs\TallyMonitor
DefaultGroupName=Tally Monitor
PrivilegesRequired=lowest
OutputBaseFilename=TallyMonitor-Setup-{#AppVersion}
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
#ifdef HasIcon
SetupIconFile=..\src\tally_monitor\assets\logo.ico
#endif
LicenseFile=..\LICENSE
UninstallDisplayIcon={app}\TallyMonitor.exe
ArchitecturesInstallIn64BitMode=x64compatible
CloseApplications=yes

[Languages]
Name: "spanish"; MessagesFile: "compiler:Languages\Spanish.isl"

[Files]
Source: "{#DistDir}\*"; DestDir: "{app}"; Flags: recursesubdirs ignoreversion
Source: "..\LICENSE"; DestDir: "{app}"; Flags: ignoreversion
Source: "..\THIRD_PARTY_LICENSES.md"; DestDir: "{app}"; Flags: ignoreversion
Source: "..\PRIVACIDAD.md"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{group}\Tally Monitor"; Filename: "{app}\TallyMonitor.exe"
Name: "{autodesktop}\Tally Monitor"; Filename: "{app}\TallyMonitor.exe"; Tasks: desktopicon

[Tasks]
Name: "desktopicon"; Description: "Crear un acceso directo en el escritorio"; Flags: unchecked

[Run]
Filename: "{app}\TallyMonitor.exe"; Description: "Abrir Tally Monitor"; Flags: nowait postinstall skipifsilent

[Code]
procedure CurUninstallStepChanged(CurUninstallStep: TUninstallStep);
begin
  if CurUninstallStep = usPostUninstall then
    if MsgBox('¿Querés borrar también tus datos (encuestas descargadas, copias de seguridad y API Keys guardadas)?' + #13#10 +
              'Si elegís "No", se conservan para una futura instalación.', mbConfirmation, MB_YESNO or MB_DEFBUTTON2) = IDYES then
      DelTree(ExpandConstant('{localappdata}\TallyMonitor'), True, True, True);
end;
