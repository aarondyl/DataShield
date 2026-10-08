"""本地用户智能体入口：仅回环监听，私有数据置于用户应用目录。"""
import os
import secrets
import json
from pathlib import Path

os.environ.setdefault("RUNTIME_MODE", "local")
os.environ.setdefault("RUNTIME_TOKEN", secrets.token_urlsafe(32))
from app.core.config import get_settings

settings = get_settings()
Path(settings.local_data_dir).mkdir(parents=True, exist_ok=True)


def write_runtime_descriptor() -> Path:
    """向同一用户的 Desktop 壳交付回环地址和短期 token，不写入仓库或日志。"""
    destination = settings.local_runtime_descriptor_path
    temporary = destination.with_suffix(".json.tmp")
    temporary.write_text(json.dumps({
        "base_url": "http://127.0.0.1:18321",
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

if __name__ == "__main__":
    import uvicorn
    write_runtime_descriptor()
    uvicorn.run("app.main:app", host="127.0.0.1", port=18321)
