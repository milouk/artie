# -*- mode: python ; coding: utf-8 -*-


a = Analysis(
    ['src/app.py'],
    pathex=[],
    binaries=[
        # Bundle libdrm/libgbm so SDL2's dynamically-loaded kmsdrm driver
        # can find them inside PyInstaller's temp extraction dir. Without
        # these, SDL2 falls back to the offscreen driver on muOS devices
        # that don't expose libdrm via a standard library path.
        ('/usr/lib/aarch64-linux-gnu/libdrm.so.2', '.'),
        ('/usr/lib/aarch64-linux-gnu/libgbm.so.1', '.'),
    ],
    datas=[],
    hiddenimports=[],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=['PIL._avif'],
    noarchive=False,
    optimize=0,
)

# Exclude system SDL2 — pygame-ce bundles its own hash-named copy.
# The system's libSDL2-2.0.so.0 (often older) causes a version conflict.
a.binaries = [b for b in a.binaries if b[0] != 'libSDL2-2.0.so.0']

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='app',
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
