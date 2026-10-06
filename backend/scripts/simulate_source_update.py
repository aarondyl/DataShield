"""演示脚本：模拟官方来源更新（人工修改「当前在线来源」文件）。

用法::

    python scripts/simulate_source_update.py pipl

把 ``data/fixtures/pipl_update.txt`` 覆盖到 ``data/sources/pipl.txt``
（相当于官网内容发生了变化），随后调用
``POST /api/v1/sources/{id}/ingest`` 即可触发：版本检测 → 条级 diff →
义务更新 → 增量 embedding → regulation.change.ready 事件。
"""

from __future__ import annotations

import shutil
import sys
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1]


def main() -> None:
    code = sys.argv[1] if len(sys.argv) > 1 else "pipl"
    fixture = BACKEND_ROOT / "data" / "fixtures" / f"{code}_update.txt"
    live = BACKEND_ROOT / "data" / "sources" / f"{code}.txt"
    if not fixture.exists():
        raise SystemExit(f"更新 fixture 不存在：{fixture}")
    if not live.exists():
        raise SystemExit(f"当前来源文件不存在（请先启动一次服务完成种子入库）：{live}")
    shutil.copyfile(fixture, live)
    print(f"已模拟 {code} 官方来源更新：{fixture.name} → {live.relative_to(BACKEND_ROOT)}")
    print("下一步：POST /api/v1/sources/{source_id}/ingest 触发变化检测流水线")


if __name__ == "__main__":
    main()
