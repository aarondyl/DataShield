"""云端法规服务入口。"""
import os
os.environ.setdefault("RUNTIME_MODE", "cloud")
if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000)
