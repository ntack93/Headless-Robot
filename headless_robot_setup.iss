; Headless Robot Installer Script

[Setup]
; Application information
AppId={{5E7A2D80-1C4F-4B9A-8F55-E48D39C7F2B3}}
AppName=Headless Robot
AppVersion=1.0
AppVerName=Headless Robot 1.0
AppPublisher=Noah
AppPublisherURL=https://github.com/noah/headlessrobot
AppSupportURL=https://github.com/noah/headlessrobot/issues
AppUpdatesURL=https://github.com/noah/headlessrobot/releases

; Modern Windows versions only (Windows 10 or higher)
MinVersion=10.0

; Use modern architecture identifiers - FIXED
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible

; Use commonpf for installation directory
DefaultDirName={commonpf}\Headless Robot
DefaultGroupName=Headless Robot
OutputBaseFilename=HeadlessRobot_Setup
Compression=lzma2
SolidCompression=yes
WizardStyle=modern

; Request admin privileges but allow standard user
PrivilegesRequired=admin
PrivilegesRequiredOverridesAllowed=commandline dialog
UninstallDisplayIcon={app}\HeadlessRobot.exe
UsedUserAreasWarning=no

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked

[Files]
; Main application files
Source: "dist\HeadlessRobot\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "dist\HeadlessRobot\HeadlessRobot.exe"; DestDir: "{app}"; Flags: ignoreversion

; VC++ Redistributable
Source: "redist\vc_redist.x64.exe"; DestDir: "{tmp}"; Flags: deleteafterinstall; Check: not VCRedistInstalled

[Icons]
Name: "{group}\Headless Robot"; Filename: "{app}\HeadlessRobot.exe"; Comment: "Launch Headless Robot"
Name: "{group}\{cm:UninstallProgram,Headless Robot}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\Headless Robot"; Filename: "{app}\HeadlessRobot.exe"; Tasks: desktopicon

[Run]
; Install Visual C++ Redistributable if needed
Filename: "{tmp}\vc_redist.x64.exe"; Parameters: "/quiet /norestart"; StatusMsg: "Installing Visual C++ Redistributable..."; Check: not VCRedistInstalled; Flags: waituntilterminated

; Run the application after installation
Filename: "{app}\HeadlessRobot.exe"; Description: "{cm:LaunchProgram,Headless Robot}"; Flags: nowait postinstall skipifsilent

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