# -*- mode: python ; coding: utf-8 -*-


a = Analysis(
    ['mesh_extractor_gui.py'],
    pathex=[],
    binaries=[],
    datas=[('image-Photoroom.png', '.')],
    hiddenimports=['efmi_export', 'efmi_export.data_model', 'efmi_export.tbn_encoding', 'efmi_export.metadata', 'efmi_export.buffer_builder', 'efmi_export.ini_template', 'efmi_export.exporter', 'metadata_generator'],
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
    a.binaries,
    a.datas,
    [],
    name='MeshExtractor',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=['app_icon.ico'],
)
