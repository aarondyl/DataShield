"""演示脚本：全局法规智能层 Definition of Done 全流程巡检。

前置：服务已启动（``uvicorn app.main:app --port 8000``）。

用法::

    python scripts/demo_regintel.py            # 巡检知识库与检索（DoD 1-7）
    python scripts/demo_regintel.py --change   # 先模拟 PIPL 来源更新，再演示变化闭环（DoD 8-17）
    python scripts/demo_regintel.py --reset    # 还原 PIPL 来源文件（演示后清理）

只通过公开 HTTP API 演示，不直接触碰数据库。
"""

from __future__ import annotations

import json
import shutil
import sys
from pathlib import Path

import httpx

BASE = "http://127.0.0.1:8000/api"
BACKEND_ROOT = Path(__file__).resolve().parents[1]

_passed = 0


def ok(step: str, detail: str = "") -> None:
    global _passed
    _passed += 1
    print(f"  ✓ {_passed}. {step}" + (f" —— {detail}" if detail else ""))


def main() -> None:
    change_mode = "--change" in sys.argv
    if "--reset" in sys.argv:
        shutil.copyfile(BACKEND_ROOT / "data/regulations/pipl.txt", BACKEND_ROOT / "data/sources/pipl.txt")
        print("已还原 data/sources/pipl.txt 为原始快照")
        return

    client = httpx.Client(base_url=BASE, timeout=120)

    print("== 全局法规智能层 DoD 巡检 ==")

    # 1. PostgreSQL + pgvector 本地运行（docker compose）/ 本机降级 SQLite
    health = client.get("/health").json()
    ok("数据库运行", f"db={health['db']}（docker compose 环境为 postgresql+pgvector）")

    # 2. 三部 MVP 法规入库
    regs = client.get("/v1/regulations").json()
    names = {r["name"] for r in regs}
    assert {"GDPR（通用数据保护条例）", "个人信息保护法", "数据安全法"} <= names
    ok("法规入库", "、".join(f"{r['name']}({r['article_count']}条/{r['requirement_count']}义务)" for r in regs))

    # 3-4. 查看 Regulation / Version
    pipl = next(r for r in regs if r["name"] == "个人信息保护法")
    versions = client.get(f"/v1/regulations/{pipl['id']}/versions").json()
    ok("查看 Regulation", f"{pipl['official_identifier']} / {pipl['authority']} / 当前版本 v{pipl['current_version_number']}")
    ok("查看 Version", f"共 {len(versions)} 个版本，最新 hash={versions[-1]['content_hash'][:12]}…")

    # 5-6. 查看 Article / Paragraph + Requirement
    reqs = client.get("/v1/requirements", params={"regulation_id": pipl["id"]}).json()
    unit = client.get(f"/v1/legal-units/{reqs[0]['legal_unit_id']}").json()
    ok("查看 Article/Paragraph", f"{unit['path']}（{len(unit['text'])} 字）")
    ok("查看 Requirement", f"示例：{reqs[0]['subject_type']} 应当/不得 …（confidence={reqs[0]['confidence']}，status={reqs[0]['status']}）")

    # 7. 语义法条检索
    results = client.post(
        "/v1/legal-search", json={"query": "向境外提供个人信息应当具备什么条件", "jurisdictions": ["CN"], "top_k": 5}
    ).json()["results"]
    assert any(r["article"] == "第三十八条" for r in results), "跨境条款未命中"
    ok("语义检索", f"top1={results[0]['regulation_name']}{results[0]['article']}（score={results[0]['similarity_score']}）")

    if not change_mode:
        print("\n加 --change 运行变化检测闭环演示（DoD 8-17）")
        return

    # 8. 人工模拟 source 更新
    fixture = BACKEND_ROOT / "data/fixtures/pipl_update.txt"
    live = BACKEND_ROOT / "data/sources/pipl.txt"
    original = live.read_text(encoding="utf-8")
    live.write_text(fixture.read_text(encoding="utf-8"), encoding="utf-8")
    ok("人工模拟 source 更新", "pipl_update.txt → data/sources/pipl.txt（修改第十三条 / 删除第十六条 / 新增第六十六条之一）")

    try:
        source_id = next(s["id"] for s in client.get("/v1/sources").json() if s["fetch_url"].endswith("pipl.txt"))
        # 9-11. 变化检测 → 新版本 → RegulationChange
        run = client.post(f"/v1/sources/{source_id}/ingest").json()
        assert run["status"] == "COMPLETED" and run["changes_count"] == 3
        ok("检测到 change 并创建新 RegulationVersion", f"v{run['from_version_id']} → v{run['to_version_id']}，{run['changes_count']} 处条级变化")

        changes = client.get("/v1/changes", params={"regulation_id": pipl["id"]}).json()
        ok("创建 RegulationChange", "；".join(f"{c['change_type']} {c['article']}[{c['materiality']}]" for c in changes))

        # 12-14. Requirement 更新 + 增量 embedding + 旧 chunk 失效
        modified = next(c for c in changes if c["change_type"] == "MODIFIED")
        assert modified["requirement_ids"]
        ok("更新相应 Requirement", f"第十三条新义务 {len(modified['requirement_ids'])} 条；摘要：{modified['semantic_summary'][:40]}…")
        versions = client.get(f"/v1/regulations/{pipl['id']}/versions").json()
        v1 = versions[0]
        history = client.post(
            "/v1/legal-search", json={"query": "第十六条 拒绝提供产品或者服务", "top_k": 10, "current_only": False}
        ).json()["results"]
        old_hits = [h for h in history if h["article"] == "第十六条" and h["version_id"] == v1["id"]]
        current = client.post(
            "/v1/legal-search", json={"query": "第十六条 拒绝提供产品或者服务", "top_k": 10}
        ).json()["results"]
        assert old_hits and not [h for h in current if h["article"] == "第十六条" and h["version_id"] == v1["id"]]
        ok("只对变更 chunk 重新 embedding，旧 chunk inactive", f"v1 第十六条仅历史可查（{len(old_hits)} 条），当前检索已不含")

        # 15-16. 检索最新内容 + 追溯官方来源
        fresh = client.post("/v1/legal-search", json={"query": "人工智能生成合成内容应当显著标识", "top_k": 1}).json()["results"][0]
        unit = client.get(f"/v1/legal-units/{fresh['legal_unit_id']}").json()
        assert unit["official_source_url"].startswith("https://")
        ok("检索到最新内容并可追溯官方来源", f"{fresh['article']} → {unit['official_source_url']}")

        # 17. regulation.change.ready 事件
        events = client.get("/v1/events").json()
        event = next(e for e in events if e["id"] == run["event_id"])
        ok("输出 regulation.change.ready", f"{event['event_id']} materiality={event['payload']['materiality']} topics={event['payload']['topics']}")

        # 版本未变 → NO_CHANGE
        rerun = client.post(f"/v1/sources/{source_id}/ingest").json()
        assert rerun["status"] == "NO_CHANGE"
        ok("重复抓取版本检测", "hash 一致 → NO_CHANGE，不产生新版本")
    finally:
        live.write_text(original, encoding="utf-8")
        print("\n（已还原 data/sources/pipl.txt；数据库中的 v2 版本保留可演示历史）")

    print(f"\n全部 {_passed} 项 DoD 巡检通过 ✅")
    print("提示：如需恢复单版本初始状态，删除 backend/datashield.db 后重启服务即可。")


if __name__ == "__main__":
    main()
