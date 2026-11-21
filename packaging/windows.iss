#ifndef AppVersion
  #define AppVersion "0.1.0"
#endif

[Setup]
AppId=FranklinMartins.DiskMapStudio
AppName=DiskMap Studio
AppVersion={#AppVersion}
AppPublisher=Franklin Leandro Martins
DefaultDirName={localappdata}\Programs\DiskMap Studio
DefaultGroupName=DiskMap Studio
OutputDir=..\artifacts
OutputBaseFilename=diskmap-studio-{#AppVersion}-windows-x64-setup
SetupIconFile=icon.ico
PrivilegesRequired=lowest
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
Compression=lzma2
SolidCompression=yes
WizardStyle=modern

[Languages]
Name: "brazilianportuguese"; MessagesFile: "compiler:Languages\BrazilianPortuguese.isl"

[Files]
Source: "..\dist\DiskMapStudio\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "licenses\*"; DestDir: "{app}\licenses"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\DiskMap Studio"; Filename: "{app}\DiskMapStudio.exe"
