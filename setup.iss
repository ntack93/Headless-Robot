; filepath: c:\Users\Noah\OneDrive\Documents\TT\setup.iss
; Teleconference Terminal Installer Script

[Setup]
; Application information
AppId={{2F8A3E90-4B2D-4A8C-B5F1-38C7EF8D09E4}}
AppName=Teleconference Terminal
AppVersion=1.0
AppVerName=Teleconference Terminal 1.0
AppPublisher=ntack93
AppPublisherURL=https://github.com/ntack93/TT
AppSupportURL=https://github.com/ntack93/TT/issues
AppUpdatesURL=https://github.com/ntack93/TT/releases

; Modern Windows versions only (Windows 10 or higher)
MinVersion=10.0

; Use modern architecture identifiers
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible

; Use commonpf for installation directory
DefaultDirName={commonpf}\Teleconference Terminal
DefaultGroupName=Teleconference Terminal
OutputBaseFilename=TeleconferenceTerminal_Setup
Compression=lzma2
SolidCompression=yes
WizardStyle=modern

; Request admin privileges but allow standard user
PrivilegesRequired=admin
PrivilegesRequiredOverridesAllowed=commandline dialog
UninstallDisplayIcon={app}\TeleconferenceTerminal.exe
UsedUserAreasWarning=no

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked

[Files]
; Main application files
Source: "dist\TeleconferenceTerminal\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "dist\TeleconferenceTerminal\TeleconferenceTerminal.exe"; DestDir: "{app}"; Flags: ignoreversion

; Explicitly include VLC files
Source: "dist\TeleconferenceTerminal\libvlc.dll"; DestDir: "{app}"; Flags: ignoreversion
Source: "dist\TeleconferenceTerminal\libvlccore.dll"; DestDir: "{app}"; Flags: ignoreversion
Source: "dist\TeleconferenceTerminal\plugins\*"; DestDir: "{app}\plugins"; Flags: ignoreversion recursesubdirs createallsubdirs

; Sound files - place in both root and _internal directory for compatibility
Source: "TT\chat.wav"; DestDir: "{app}"; Flags: ignoreversion
Source: "TT\directed.wav"; DestDir: "{app}"; Flags: ignoreversion
Source: "TT\chat.wav"; DestDir: "{app}\_internal"; Flags: ignoreversion
Source: "TT\directed.wav"; DestDir: "{app}\_internal"; Flags: ignoreversion

; Modern Visual C++ Redistributable
Source: "redist\vc_redist.x64.exe"; DestDir: "{tmp}"; Flags: deleteafterinstall; Check: not VCRedistInstalled

[Icons]
Name: "{group}\Teleconference Terminal"; Filename: "{app}\TeleconferenceTerminal.exe"; Comment: "Launch Teleconference Terminal"
Name: "{group}\{cm:UninstallProgram,Teleconference Terminal}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\Teleconference Terminal"; Filename: "{app}\TeleconferenceTerminal.exe"; Tasks: desktopicon

[Run]
; Install Visual C++ Redistributable if needed
Filename: "{tmp}\vc_redist.x64.exe"; Parameters: "/quiet /norestart"; StatusMsg: "Installing Visual C++ Redistributable..."; Check: not VCRedistInstalled; Flags: waituntilterminated

; Run the application after installation
Filename: "{app}\TeleconferenceTerminal.exe"; Description: "{cm:LaunchProgram,Teleconference Terminal}"; Flags: nowait postinstall skipifsilent

[UninstallDelete]
Type: filesandordirs; Name: "{app}\*.json"
Type: dirifempty; Name: "{app}"

[Dirs]
Name: "{app}\config"; Permissions: everyone-modify

[Code]
// Check if Visual C++ Redistributable is already installed
function VCRedistInstalled: Boolean;
begin
  // Check for VC++ 2015-2022 Redistributable
  Result := RegKeyExists(HKEY_LOCAL_MACHINE, 'SOFTWARE\Microsoft\VisualStudio\14.0\VC\Runtimes\x64') or
            RegKeyExists(HKEY_LOCAL_MACHINE, 'SOFTWARE\WOW6432Node\Microsoft\VisualStudio\14.0\VC\Runtimes\x64');
end;