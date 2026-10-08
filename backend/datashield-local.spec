# -*- mode: python ; coding: utf-8 -*-
"""只为 Tauri sidecar 打包 Local FastAPI。

构建机命令（Windows）::

    pyinstaller --noconfirm datashield-local.spec

不收集 .env、SQLite、workspace、日志或任意 API Key。用户数据由 Local
Runtime 在 %LOCALAPPDATA%/DataShield 创建，绝不位于安装目录。
"""

from PyInstaller.utils.hooks import collect_submodules


hiddenimports = collect_submodules("app") + collect_submodules("uvicorn")
datas = [
    ("alembic", "alembic"),
    ("alembic.ini", "."),
    ("data/fixtures", "data/fixtures"),
    ("data/regulations", "data/regulations"),
]

a = Analysis(
    ["desktop_sidecar.py"],
    pathex=["."],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    excludes=["pytest", "_pytest"],
    noarchive=False,
)
pyz = PYZ(a.pure)
exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="datashield-local",
    console=False,
)
coll = COLLECT(exe, a.binaries, a.datas, name="datashield-local")
