"""DataShield Desktop Local FastAPI sidecar 的唯一打包入口。

不在这里复制配置、端口或 token 协议：它们均由当前权威的
``app.entrypoints.local.run_local`` 提供。PyInstaller 只将此文件打成
Desktop 壳启动的 sidecar，且不携带任何 provider credential。
"""

from app.entrypoints.local import run_local


if __name__ == "__main__":
    run_local()
