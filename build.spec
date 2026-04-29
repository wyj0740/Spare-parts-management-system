# -*- mode: python ; coding: utf-8 -*-
"""
备品备件管理系统 - PyInstaller 打包配置
Author: wyj
License: MIT License
"""

block_cipher = None

a = Analysis(
    ['app.py'],
    pathex=[],
    binaries=[],
    datas=[
        ('templates', 'templates'),
        ('static', 'static'),
        ('config.ini', '.'),
    ],
    hiddenimports=[
        'flask',
        'flask_sqlalchemy',
        'pandas',
        'openpyxl',
        'sqlalchemy.ext.baked',
        'pickle',
        'numpy',
        'numpy.core',
        'numpy.core._methods',
        'numpy.lib',
        'numpy.lib.format',
        'numpy.linalg',
        'numpy.matrixlib',
        'numpy.matrixlib.defmatrix',
        'pandas._libs',
        'pandas._libs.tslibs',
        'pandas._libs.tslibs.base',
        'config',
        'models',
        'routes',
        'routes.common',
        'routes.auth',
        'routes.pages',
        'routes.spare_parts',
        'routes.records',
        'routes.folders',
        'routes.backup',
        'routes.export',
        'routes.audit',
        'routes.settings',
        'utils',
        'utils.helpers',
        'utils.folder_manager',
        'utils.logger',
        'utils.backup_manager',
        'db_migration',
        'dateutil',
        'dateutil.relativedelta',
        'werkzeug.security',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        'matplotlib',
        'scipy',
        'tkinter',
        'PyQt5',
        'PyQt6',
        'PySide2',
        'PySide6',
        'IPython',
        'jupyter',
        'notebook',
    ],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='备品备件管理系统',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,  # 不显示控制台窗口
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='备品备件管理系统',
)
