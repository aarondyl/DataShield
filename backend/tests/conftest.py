"""pytest 全局配置。

在任何 app 模块被导入之前固定测试环境：
- DATABASE_URL 指向独立的测试 SQLite 文件（每次运行前删除，保证干净）；
- LLM_PROVIDER=mock（确定性输出）、EMBEDDING_PROVIDER=local（离线哈希向量）；
- RUN_SEED=true（启动时写入种子数据）。

注意：os.environ 的设置必须发生在 import app.* 之前，因此本文件顶部不放任何 app 导入。
"""

import os
import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent.parent
TEST_DB = BACKEND_DIR / "tests" / "test_datashield.db"

# 每次测试会话使用全新的数据库文件
if TEST_DB.exists():
    TEST_DB.unlink()

os.environ["DATABASE_URL"] = f"sqlite:///{TEST_DB.as_posix()}"
os.environ["LLM_PROVIDER"] = "mock"
os.environ["EMBEDDING_PROVIDER"] = "local"
os.environ["RUN_SEED"] = "true"
os.environ["LLM_API_KEY"] = ""

# 保证以任意工作目录运行 pytest 时都能 import app.*
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))
