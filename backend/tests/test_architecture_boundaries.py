"""架构边界的静态回归检查。

这些检查防止云端法规模块重新依赖租户或产品理解领域；运行时模式测试在后续阶段覆盖路由和数据库初始化。
"""

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_regintel_does_not_import_private_tenant_or_understanding_domains():
    prohibited = ("app.tenant", "app.understanding", "ProductTwin", "Finding", "Remediation", "Feedback")
    offenders: list[str] = []
    for path in (ROOT / "app" / "regintel").glob("*.py"):
        text = path.read_text(encoding="utf-8")
        for name in prohibited:
            if name in text:
                offenders.append(f"{path.relative_to(ROOT)}: {name}")
    assert not offenders, "云端法规模块不得依赖私有领域：\n" + "\n".join(offenders)


def test_architecture_document_records_the_three_data_boundaries():
    document = (ROOT.parent / "docs" / "云端法规与本地智能体架构.md").read_text(encoding="utf-8")
    for phrase in ("云端法规服务", "本地用户智能体", "Web 托管模式", "不携带产品事实"):
        assert phrase in document
