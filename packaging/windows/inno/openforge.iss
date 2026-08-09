; OpenForge — Inno Setup (v5 line). Filename: openforge.iss ; content: OpenForge.
#define AppName "OpenForge"
#define AppVersion "5.0.2"
#define AppPublisher "Dearly Febriano Irwansyah"
#define AppURL "https://github.com/neuralforgeio/openforge"
[Setup]
AppName={#AppName}
AppVersion={#AppVersion}
AppPublisher={#AppPublisher}
AppPublisherURL={#AppURL}
DefaultDirName={autopf}\OpenForge
DefaultGroupName=OpenForge
OutputBaseFilename=OpenForge-Setup-{#AppVersion}
Compression=lzma2
SolidCompression=yes
[Files]
Source: "..\\..\\dist\\*"; DestDir: "{app}"; Flags: recursesubdirs
