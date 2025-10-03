# -*- mode: python ; coding: utf-8 -*-

from PyInstaller.utils.hooks import collect_submodules

# Collect hidden imports for python-can
hidden = [
    "can",
    "can.interfaces",
    "can.interfaces.socketcan",
    "can.interfaces.socketcan_native",
    "can.interfaces.kvaser",
]
hidden += collect_submodules("can.interfaces")

a = Analysis(
    ["backend/__main__.py"],
    pathex=["backend"],
    binaries=[],
    datas=[
        ("backend/static", "static"),   # UI build
        ("backend/presets.json", "."),  # ship defaults
        ("backend/groups.json", "."),   # ship defaults
    ],
    hiddenimports=hidden,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=None)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name="can-tool",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
