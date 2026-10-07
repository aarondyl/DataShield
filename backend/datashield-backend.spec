# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller 打包配置：DataShield 桌面版内嵌 FastAPI 后端（onedir 模式）。

构建::

    cd backend
    pyinstaller datashield-backend.spec --distpath dist --workpath build

产出 ``dist/datashield-backend/datashield-backend.exe``，由 Electron 主进程作为
extraResources 携带并 spawn。
"""

from PyInstaller.utils.hooks import collect_submodules

hiddenimports = (
    collect_submodules("app")
    + collect_submodules("uvicorn")
    + [
        "pgvector",
        "psycopg",
        "psycopg_binary",
    ]
)

datas = [
    ("data", "data"),
    ("alembic", "alembic"),
    ("alembic.ini", "."),
]

a = Analysis(
    ["desktop_entry.py"],
    pathex=[],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=["pytest", "_pytest"],
    noarchive=False,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="datashield-backend",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=True,
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    name="datashield-backend",
)
