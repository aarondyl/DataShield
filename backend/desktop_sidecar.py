"""DataShield Desktop Local FastAPI sidecar 的唯一打包入口。

不在这里复制配置、端口或 token 协议：它们均由当前权威的
``app.entrypoints.local.run_local`` 提供。PyInstaller 只将此文件打成
Desktop 壳启动的 sidecar，且不携带任何 provider credential。
"""

import os
import sys
from pathlib import Path

# PyInstaller --windowed has no console streams. Uvicorn's logging formatter
# calls isatty(), so leaving stdout/stderr as None crashes before readiness.
# Do not attach a console or log tokens; use the OS null device instead.
log_destination = os.devnull
if os.getenv("DATASHIELD_SIDECAR_DIAGNOSTICS") == "1" and os.getenv("LOCAL_DATA_DIR"):
    diagnostic_dir = Path(os.environ["LOCAL_DATA_DIR"])
    diagnostic_dir.mkdir(parents=True, exist_ok=True)
    log_destination = str(diagnostic_dir / "sidecar-startup.log")
if sys.stdout is None:
    sys.stdout = open(log_destination, "a", encoding="utf-8", buffering=1)
if sys.stderr is None:
    sys.stderr = open(log_destination, "a", encoding="utf-8", buffering=1)

from app.entrypoints.local import run_local


if __name__ == "__main__":
    run_local()
