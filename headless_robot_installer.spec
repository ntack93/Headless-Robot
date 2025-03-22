# -*- mode: python ; coding: utf-8 -*-

block_cipher = None

a = Analysis(
    ['UltronPreAlpha.py'],  # Changed main script to UltronPreAlpha.py
    pathex=['c:\\Users\\Noah\\OneDrive\\Documents\\Headless Robot'],
    binaries=[],
    datas=[
        # Include UltronCLI.py as a data file, not the main script
        ('UltronCLI.py', '.'),
        ('api_keys.json', '.') if os.path.exists('api_keys.json') else None,
    ],
    hiddenimports=[
        'colorama', 'asyncio', 'telnetlib3', 'openai', 'boto3', 'botocore',
        'json', 'sys', 'requests', 'urllib3', 'idna', 'chardet',
        'io', 'traceback', 'shutil', 'tempfile', 'pathlib', 'bs4',
        'concurrent.futures', 'email', 'imaplib', 'platform', 'time',
        'logging', 'signal', 'importlib', 'queue', 'threading', 're',
        'os', 'email.mime', 'email.mime.text', 'email.utils'
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

# Filter out None entries from datas
a.datas = [data for data in a.datas if data is not None]

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='HeadlessRobot',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=True,  # This is a console application
    icon='headless_robot.ico' if os.path.exists('headless_robot.ico') else None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='HeadlessRobot',
)