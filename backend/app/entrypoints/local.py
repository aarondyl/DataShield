"""本地用户智能体入口：仅回环监听，私有数据置于用户应用目录。"""
import os
import secrets
import json
import socket
from pathlib import Path

os.environ.setdefault("RUNTIME_MODE", "local")
os.environ.setdefault("RUNTIME_TOKEN", secrets.token_urlsafe(32))
from app.core.config import get_settings

settings = get_settings()
Path(settings.local_data_dir).mkdir(parents=True, exist_ok=True)


def allocate_loopback_listener(attempts: int = 3) -> socket.socket:
    """保留一个内核分配的 loopback 端口，供 Uvicorn 直接复用。"""
    last_error: OSError | None = None
    for _ in range(attempts):
        listener = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            listener.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            listener.bind(("127.0.0.1", 0))
            listener.listen(socket.SOMAXCONN)
            listener.set_inheritable(False)
            return listener
        except OSError as exc:
            last_error = exc
            listener.close()
    raise RuntimeError("无法分配本地回环监听端口") from last_error


def write_runtime_descriptor(port: int) -> Path:
    """向同一用户的 Desktop 壳交付回环地址和短期 token，不写入仓库或日志。"""
    destination = settings.local_runtime_descriptor_path
    temporary = destination.with_suffix(".json.tmp")
    temporary.write_text(json.dumps({
        "base_url": f"http://127.0.0.1:{port}",
        "runtime_token": settings.runtime_token,
        "pid": os.getpid(),
    }), encoding="utf-8")
    try:
        temporary.chmod(0o600)
    except OSError:
        # Windows ACL 由用户目录继承；不因 chmod 不可用而阻止本地应用启动。
        pass
    temporary.replace(destination)
    return destination


def run_local() -> None:
    """以已绑定的随机回环 socket 启动，避免端口探测与监听之间的竞争。"""
    import uvicorn

    listener = allocate_loopback_listener()
    port = listener.getsockname()[1]
    write_runtime_descriptor(port)
    server = uvicorn.Server(uvicorn.Config("app.main:app", log_level="info"))
    try:
        server.run(sockets=[listener])
    finally:
        listener.close()

if __name__ == "__main__":
    run_local()
