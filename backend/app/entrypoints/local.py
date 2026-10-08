"""本地用户智能体入口：仅回环监听，私有数据置于用户应用目录。"""
import os
import secrets
from pathlib import Path

os.environ.setdefault("RUNTIME_MODE", "local")
os.environ.setdefault("RUNTIME_TOKEN", secrets.token_urlsafe(32))
from app.core.config import get_settings

settings = get_settings()
Path(settings.local_data_dir).mkdir(parents=True, exist_ok=True)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host="127.0.0.1", port=18321)
