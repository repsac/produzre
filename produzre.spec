# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec for building a standalone Produzre executable.

Usage:
    pyinstaller produzre.spec

Output:
    dist/produzre       (macOS / Linux)
    dist/produzre.exe   (Windows)
"""

import os
from pathlib import Path

block_cipher = None

# ---------------------------------------------------------------------------
# Collect resource data files (recipes, personas, engines.yml)
# ---------------------------------------------------------------------------
resource_datas = []
resources_root = Path("produzre") / "resources"
for root, dirs, files in os.walk(resources_root):
    for f in files:
        if f.endswith((".yaml", ".yml")) and not f.startswith("."):
            src = os.path.join(root, f)
            # Destination preserves the produzre/resources/... structure
            dst = root
            resource_datas.append((src, dst))

a = Analysis(
    ["produzre_entry.py"],
    pathex=["."],
    binaries=[],
    datas=resource_datas,
    hiddenimports=[],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name="produzre",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True,
    disable_windowed_traceback=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
