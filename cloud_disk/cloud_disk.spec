# -*- mode: python ; coding: utf-8 -*-

import sys
import os

# 获取当前目录作为项目路径
project_path = os.path.dirname(os.path.abspath('.'))

# 分析主程序
a = Analysis(
    ['run.py'],
    pathex=[project_path],
    binaries=[],
    datas=[
        ('templates', 'templates'),
        ('app/static', 'app/static'),
        ('icon.ico', '.'),
    ],
    hiddenimports=[
        'engineio.async_drivers.threading',
        'socketio',
        'flask_socketio',
        'ttkbootstrap',
        'psutil',
        'pystray',
        'PIL',
        'bidict',
        'simple_websocket',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=None,  # 在新版本中可能不需要block_cipher
    noarchive=False,
)

# 配置PE文件
pyz = PYZ(a.pure, a.zipped_data, cipher=None)

# 创建EXE
exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='cloud_disk',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,  # 设为False以隐藏控制台窗口
    disable_windowed_traceback=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon='icon.ico',
)