# -*- mode: python ; coding: utf-8 -*-


a = Analysis(
    ['D:\\05_Code\\python\\bugzila\\fetch_buginfo_by_API_UI.py'],
    pathex=[],
    binaries=[],
    datas=[('D:\\05_Code\\python\\bugzila\\paths.json', '.')],
    hiddenimports=[],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='fetch_buginfo_by_API_UI',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=['D:\\05_Code\\python\\bugzila\\favicon.ico'],
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='fetch_buginfo_by_API_UI',
)
