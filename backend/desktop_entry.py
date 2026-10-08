"""DataShield 桌面版后端入口（供 Electron 内嵌 / PyInstaller 打包使用）。

与常规 ``uvicorn app.main:app`` 启动的区别：

- 强制 ``DESKTOP_MODE=true``：放宽 Origin 校验、关闭 secure cookie、CORS 放开；
- SQLite 数据库放到用户数据目录（环境变量 ``DATASHIELD_DATA_DIR`` 指定，
  默认 ``./desktop-data``，由 Electron 主进程传入 ``<appData>/DataShield``）；
- 启动前备份现有数据库并执行 ``alembic upgrade head``；迁移失败则恢复备份、
  把异常写入 ``<数据目录>/logs/migration-error.log`` 并以退出码 1 结束；
- 固定监听 ``127.0.0.1:18321``，仅本机回环，不对外暴露。

直接运行::

    DATASHIELD_DATA_DIR=./desktop-data python desktop_entry.py
"""

import os

os.environ.setdefault("DESKTOP_MODE", "true")

import logging
import shutil
import sys
import time
import traceback
from pathlib import Path

data_dir = Path(os.environ.get("DATASHIELD_DATA_DIR", "./desktop-data")).resolve()
data_dir.mkdir(parents=True, exist_ok=True)
logs_dir = data_dir / "logs"
logs_dir.mkdir(parents=True, exist_ok=True)
db_path = data_dir / "datashield.db"
os.environ["DATABASE_URL"] = f"sqlite:///{db_path.as_posix()}"
# 桌面版默认离线可跑；打包时若生成了内置 LLM 凭证（deploy/gen_bundled_key.py，
# 文件被 gitignore 仅存在于构建机），则默认启用真实模型。环境变量始终优先。
os.environ.setdefault("LLM_PROVIDER", "mock")
os.environ.setdefault("EMBEDDING_PROVIDER", "local")
try:
    from app.core.bundled_key import get_bundled_llm_key

    if not os.environ.get("LLM_API_KEY"):
        os.environ["LLM_API_KEY"] = get_bundled_llm_key()
        os.environ["LLM_PROVIDER"] = "api"
        os.environ.setdefault("LLM_BASE_URL", "https://api.deepseek.com/v1")
        os.environ.setdefault("LLM_MODEL", "deepseek-flash")
except ImportError:
    pass  # 源码仓库内没有内置凭证（该文件不入库），保持 mock 演示模式

# 产品理解子系统的服务端凭证：首次启动生成并持久化到数据目录
# （该凭证经 os.getenv 读取；每次随机生成会让历史分析任务的归属校验失效，故持久化）
_key_file = data_dir / "understanding.key"
if not os.environ.get("UNDERSTANDING_API_KEY"):
    import secrets as _secrets

    if _key_file.exists():
        os.environ["UNDERSTANDING_API_KEY"] = _key_file.read_text(encoding="utf-8").strip()
    else:
        os.environ["UNDERSTANDING_API_KEY"] = _secrets.token_urlsafe(32)
        _key_file.write_text(os.environ["UNDERSTANDING_API_KEY"], encoding="utf-8")

# PyInstaller onedir 模式下打包资源在 sys._MEIPASS；源码运行时在 backend/ 目录
_bundle_root = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent))


def _backup_db() -> Path | None:
    """启动前把现有 sqlite 库复制为 datashield.db.bak-<时间戳>，仅保留最近 3 份。"""
    if not db_path.exists():
        return None
    backup = data_dir / f"datashield.db.bak-{time.strftime('%Y%m%d-%H%M%S')}"
    shutil.copy2(db_path, backup)
    for old in sorted(data_dir.glob("datashield.db.bak-*"))[:-3]:
        old.unlink(missing_ok=True)
    return backup


def _run_migrations() -> None:
    """alembic upgrade head（编程调用，兼容打包后的 alembic 目录定位）。"""
    import sqlite3

    from alembic import command
    from alembic.config import Config

    cfg = Config(str(_bundle_root / "alembic.ini"))
    cfg.set_main_option("script_location", str(_bundle_root / "alembic"))
    if db_path.exists():
        # 旧版桌面端的库由 init_db 的 create_all 建立、无 alembic_version 表：
        # 先标记为 head（模型与 0010 迁移链一致），避免 0001 重复建表导致迁移失败
        with sqlite3.connect(db_path) as conn:
            tables = {row[0] for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        if tables and "alembic_version" not in tables:
            command.stamp(cfg, "head")
    command.upgrade(cfg, "head")


def _migrate_or_restore() -> None:
    backup = _backup_db()
    try:
        _run_migrations()
    except Exception:
        if backup is not None:
            shutil.copy2(backup, db_path)
        with open(logs_dir / "migration-error.log", "a", encoding="utf-8") as fh:
            fh.write(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] 数据库迁移失败，已恢复备份\n")
            fh.write(traceback.format_exc())
            fh.write("\n")
        sys.exit(1)


_migrate_or_restore()

# 法规文本/快照等数据文件：代码里以相对路径 data/... 访问。打包后 bundle 内是只读副本
# （PyInstaller onedir 的 _internal/data），安装到 Program Files 后不可写，而种子流程会
# 复制/写入 data/sources、data/snapshots，因此首次启动把 data/ 拷贝到用户数据目录，
# 并把工作目录切过去，让所有相对路径落到可写位置。
_bundled_data = _bundle_root / "data"
_working_data = data_dir / "data"
if _bundled_data.is_dir() and not (_working_data / "regulations").is_dir():
    shutil.copytree(_bundled_data, _working_data, dirs_exist_ok=True)
if _working_data.is_dir():
    os.chdir(data_dir)

import uvicorn

if __name__ == "__main__":
    # 打包后 console 输出不可见（Electron 以 stdio:'ignore' spawn），日志同时落数据目录
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
        handlers=[
            logging.FileHandler(logs_dir / "backend.log", encoding="utf-8"),
            logging.StreamHandler(),
        ],
    )
    uvicorn.run("app.main:app", host="127.0.0.1", port=18321, log_level="info")
