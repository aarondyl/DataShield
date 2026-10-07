"""DataShield 桌面版后端入口（供 Electron 内嵌 / PyInstaller 打包使用）。

与常规 ``uvicorn app.main:app`` 启动的区别：

- 强制 ``DESKTOP_MODE=true``：放宽 Origin 校验、关闭 secure cookie、CORS 放开；
- SQLite 数据库放到用户数据目录（环境变量 ``DATASHIELD_DATA_DIR`` 指定，
  默认 ``./desktop-data``，由 Electron 主进程传入 ``app.getPath('userData')``）；
- 固定监听 ``127.0.0.1:18321``，仅本机回环，不对外暴露。

直接运行::

    DATASHIELD_DATA_DIR=./desktop-data python desktop_entry.py
"""

import os

os.environ.setdefault("DESKTOP_MODE", "true")

import shutil
import sys
from pathlib import Path

data_dir = Path(os.environ.get("DATASHIELD_DATA_DIR", "./desktop-data")).resolve()
data_dir.mkdir(parents=True, exist_ok=True)
os.environ["DATABASE_URL"] = f"sqlite:///{(data_dir / 'datashield.db').as_posix()}"
# 桌面版默认离线可跑
os.environ.setdefault("LLM_PROVIDER", "mock")
os.environ.setdefault("EMBEDDING_PROVIDER", "local")

# 法规文本/快照等数据文件：代码里以相对路径 data/... 访问。打包后 bundle 内是只读副本
# （PyInstaller onedir 的 _internal/data），安装到 Program Files 后不可写，而种子流程会
# 复制/写入 data/sources、data/snapshots，因此首次启动把 data/ 拷贝到用户数据目录，
# 并把工作目录切过去，让所有相对路径落到可写位置。
_bundled_data = (
    Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent)) / "data"
)
_working_data = data_dir / "data"
if _bundled_data.is_dir() and not (_working_data / "regulations").is_dir():
    shutil.copytree(_bundled_data, _working_data, dirs_exist_ok=True)
if _working_data.is_dir():
    os.chdir(data_dir)

import uvicorn

if __name__ == "__main__":
    uvicorn.run("app.main:app", host="127.0.0.1", port=18321, log_level="info")
