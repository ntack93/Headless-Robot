@echo off
:: Headless Robot Build Script
echo Building Headless Robot...
echo.

echo Step 1: Clean previous builds
rmdir /s /q "dist\HeadlessRobot" 2>nul
rmdir /s /q "build\headless_installer" 2>nul

echo Step 2: Ensure required packages are installed
py -3.12 -m pip install --upgrade colorama asyncio telnetlib3 openai beautifulsoup4 boto3 pydub pytube bs4

echo Step 3: Building with PyInstaller (Python 3.12)
py -3.12 -m PyInstaller headless_robot_installer.spec

echo Step 4: Checking build output
if not exist "dist\HeadlessRobot\HeadlessRobot.exe" (
  echo Build failed: Executable not found
  exit /b 1
)

echo Step 5: Verify both Python files are included
if not exist "dist\HeadlessRobot\UltronCLI.py" (
  echo Warning: UltronCLI.py not included in the build
)
if not exist "dist\HeadlessRobot\UltronPreAlpha.py" (
  echo Warning: UltronPreAlpha.py not included in the build
)

echo Step 6: Create config directory
mkdir "dist\HeadlessRobot\config" 2>nul

echo Step 7: Creating redist directory
mkdir "redist" 2>nul

echo Step 8: Checking for VC++ Redistributable files
if not exist "redist\vc_redist.x64.exe" (
  echo WARNING: VC++ Redistributable x64 missing from redist folder
  echo Download from: https://aka.ms/vs/17/release/vc_redist.x64.exe
)

echo Step 9: Fixing permissions
icacls "dist\HeadlessRobot\*" /grant Everyone:(OI)(CI)F

echo Step 10: Building installer with InnoSetup
"C:\Program Files (x86)\Inno Setup 6\ISCC.exe" headless_robot_setup.iss

echo Build process complete!
if exist "Output\HeadlessRobot_Setup.exe" (
  echo Installer created successfully at: Output\HeadlessRobot_Setup.exe
) else (
  echo WARNING: Installer may not have been created successfully
)