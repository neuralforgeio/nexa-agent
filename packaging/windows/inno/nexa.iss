;; D-05: Inno Setup script (STUB) for a Windows .exe installer.
#define AppName "Nexa Agent"
#define AppVersion "4.12.0"
[Setup]
AppName={#AppName}
AppVersion={#AppVersion}
DefaultDirName={autopf}\OpenForgeAgent
DefaultGroupName=Nexa Agent
OutputBaseFilename=OpenForgeAgent-Setup-{#AppVersion}
Compression=lzma2
SolidCompression=yes
[Files]
; STUB: point at the real built tree once the app is packaged.
Source: "..\\..\\dist\\*"; DestDir: "{app}"; Flags: recursesubdirs
