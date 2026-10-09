"""确定性入库流水线（Global Ingestion Loop）。

Scheduler → Fetch → Normalize → Hash → 对比当前版本 → （有变化）创建新版本 →
结构解析 → 条级 Diff → Requirement Extraction → 持久化 → Chunking →
增量 Embedding → 更新向量索引 → 发布 regulation.change.ready 事件。

不是自由行动的大模型 Agent，而是确定性 workflow：
能用确定性程序完成的步骤（哈希、diff、版本号）绝不交给 LLM。
"""

from __future__ import annotations

from datetime import UTC, datetime


def _utcnow() -> datetime:
    """naive UTC 时间（与 server_default=func.now() 的口径一致）。"""
    return datetime.now(UTC).replace(tzinfo=None)

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.llm import get_llm_client_safe
from app.models import (
    IngestionRun,
    LegalChunk,
    LegalUnit,
    Regulation,
    RegulationArticle,
    RegulationChange,
    RegulationVersion,
    RegulatorySource,
    Requirement,
    SourceSnapshot,
)
from app.rag.embeddings import embed_texts_with_fallback, get_embedding_provider
from app.rag.retrieval import index_chunks as index_legacy_chunks
from app.regintel.adapters import BACKEND_ROOT, get_adapter
from app.regintel.chunking import build_chunk_payloads
from app.regintel.diffing import diff_articles
from app.regintel.events import persist_change_ready_event
from app.regintel.normalization import content_hash
from app.regintel.parsing import ParsedUnit, article_key, article_units, parse_legal_text
from app.regintel.requirements import extract_requirements
from app.regintel.retrieval import deactivate_legal_chunks, index_legal_chunks

#: 原始快照落盘目录（相对 backend 根目录）
SNAPSHOT_DIR = "data/snapshots"


def _write_snapshot(source_id: int, digest: str, text: str) -> str:
    """把规范化文本写入快照文件（按内容哈希去重），返回相对路径。"""
    dirpath = BACKEND_ROOT / SNAPSHOT_DIR / str(source_id)
    dirpath.mkdir(parents=True, exist_ok=True)
    path = dirpath / f"{digest[:12]}.txt"
    if not path.exists():
        path.write_text(text, encoding="utf-8")
    return path.relative_to(BACKEND_ROOT).as_posix()


def _embedding_model_name() -> str:
    """当前 embedding provider 标识（写入 chunk 以便审计）。"""
    return get_embedding_provider().provider_name


def _supersede_requirements(db: Session, old_unit_id: int, now: datetime) -> None:
    """把旧条款下的义务标记为 SUPERSEDED（保留历史，绝不删除）。"""
    rows = db.scalars(
        select(Requirement).where(
            Requirement.legal_unit_id == old_unit_id,
            Requirement.status != "SUPERSEDED",
        )
    ).all()
    for row in rows:
        row.status = "SUPERSEDED"
        row.effective_to = now


def _deactivate_chunks(db: Session, old_unit_id: int) -> set[int]:
    """把旧条款下的 chunk 置为 is_active=false，返回被停用的 chunk id 集合。"""
    rows = db.scalars(
        select(LegalChunk).where(
            LegalChunk.legal_unit_id == old_unit_id,
            LegalChunk.is_active.is_(True),
        )
    ).all()
    for row in rows:
        row.is_active = False
    return {row.id for row in rows}


def _extract_and_add_requirements(
    db: Session,
    regulation: Regulation,
    version: RegulationVersion,
    unit_row: LegalUnit,
    *,
    language: str,
    default_subject: str,
    use_llm: bool,
) -> list[int]:
    """对一个条款做义务提取并写库，返回新 requirement id 列表。"""
    items = extract_requirements(
        unit_row.unit_number,
        unit_row.text,
        language=language,
        default_subject=default_subject,
        use_llm=use_llm,
    )
    ids: list[int] = []
    for item in items:
        row = Requirement(
            regulation_id=regulation.id,
            version_id=version.id,
            legal_unit_id=unit_row.id,
            requirement_type=item.get("requirement_type") or "obligation",
            subject_type=item.get("subject_type") or "",
            action_type=item.get("action_type") or "",
            object_type=item.get("object_type") or "",
            conditions_json=item.get("conditions") or [],
            exceptions_json=item.get("exceptions") or [],
            summary=item.get("summary") or "",
            confidence=float(item.get("confidence") or 0.0),
            status=item.get("status") or "ACTIVE",
            effective_from=version.effective_from,
        )
        db.add(row)
        db.flush()
        ids.append(row.id)
    return ids


def _chunk_and_embed(
    db: Session,
    regulation: Regulation,
    version: RegulationVersion,
    unit_row: LegalUnit,
    parsed: ParsedUnit,
) -> list[dict]:
    """对一个条款做结构 chunking + embedding + 写库，返回待索引的 chunk dict 列表。"""
    effective_from = version.effective_from.date().isoformat() if version.effective_from else None
    payloads = build_chunk_payloads(
        [
            {
                "legal_unit_id": unit_row.id,
                "unit_number": unit_row.unit_number,
                "heading": unit_row.heading,
                "text": unit_row.text,
                "paragraphs": parsed.paragraphs,
                "path": unit_row.path,
                "metadata": {
                    "jurisdiction": regulation.jurisdiction,
                    "regulation": regulation.name,
                    "version_id": version.id,
                    "version_number": version.version_number,
                    "effective_from": effective_from,
                    "is_current": True,
                },
            }
        ]
    )
    embeddings = embed_texts_with_fallback([p["content"] for p in payloads])
    model_name = _embedding_model_name()
    chunks: list[dict] = []
    for payload, embedding in zip(payloads, embeddings):
        row = LegalChunk(
            regulation_id=regulation.id,
            version_id=version.id,
            legal_unit_id=unit_row.id,
            content=payload["content"],
            embedding=embedding,
            embedding_model=model_name,
            token_count=payload["token_count"],
            metadata_json=payload["metadata"],
            is_active=True,
        )
        db.add(row)
        db.flush()
        chunks.append(
            {
                "chunk_id": row.id,
                "regulation_id": regulation.id,
                "regulation_name": regulation.name,
                "version_id": version.id,
                "legal_unit_id": unit_row.id,
                "article": unit_row.unit_number,
                "title": unit_row.heading,
                "content": row.content,
                "source_url": regulation.canonical_source_url or regulation.source_url,
                "jurisdiction": regulation.jurisdiction,
                "embedding": embedding,
            }
        )
    return chunks


def _rule_change_summary(change) -> str:
    """变化的规则式语义摘要（确定性兜底）。"""
    if change.change_type == "ADDED":
        return f"新增条款{change.unit_number}。"
    if change.change_type == "REMOVED":
        return f"删除条款{change.unit_number}。"
    if change.change_type == "RENUMBERED":
        return f"条款重新编号：{change.old_unit_number} → {change.unit_number}（文本未变）。"
    return f"{change.unit_number}内容发生修改（文本相似度 {change.similarity:.0%}）。"


def _llm_change_summary(change) -> str | None:
    """LLM 变化语义摘要（仅 api provider 启用；任何失败返回 None 走规则摘要）。"""
    if get_settings().llm_provider != "api":
        return None
    try:
        client = get_llm_client_safe()
        data = client.chat_json(
            "你是法规变化摘要器。用一句中文概括法条变化的实质影响，只输出 JSON：{\"summary\": \"...\"}。",
            f"变化类型：{change.change_type}\n旧文本：{change.old_text[:1500]}\n新文本：{change.new_text[:1500]}",
            context={"task": "change_summary"},
        )
        summary = str(data.get("summary") or "").strip()
        return summary or None
    except Exception:
        return None


def _sync_legacy_articles(
    db: Session,
    regulation: Regulation,
    chunk_dicts: list[dict],
) -> None:
    """把当前版本的 chunk 同步到旧 regulation_articles 表（长条款按片段多行存放）。

    复用 legal chunk 的文本与向量（不重复 embedding），
    使分析工作流（agents）与旧法规中心页面继续检索真实法条。
    """
    db.query(RegulationArticle).filter(RegulationArticle.regulation_id == regulation.id).delete()
    rows: list[RegulationArticle] = []
    for chunk in chunk_dicts:
        row = RegulationArticle(
            regulation_id=regulation.id,
            article_number=chunk["article"],
            title=(chunk.get("title") or "")[:300],
            content=chunk["content"],
            topic=None,
            embedding=chunk.get("embedding"),
        )
        db.add(row)
        rows.append(row)
    db.flush()
    index_legacy_chunks(
        [
            {
                "chunk_id": row.id,
                "regulation_id": regulation.id,
                "regulation_name": regulation.name,
                "article_number": row.article_number,
                "title": row.title,
                "content": row.content,
                "source_url": regulation.source_url,
                "jurisdiction": regulation.jurisdiction,
                "topic": row.topic,
                "embedding": list(row.embedding) if row.embedding else None,
            }
            for row in rows
        ]
    )


def run_ingestion(
    db: Session,
    source: RegulatorySource,
    *,
    use_llm: bool | None = None,
    default_subject: str = "",
    language: str = "zh",
    sync_legacy: bool = False,
) -> IngestionRun:
    """执行一次完整的法规入库/更新流水线，返回运行记录（绝不抛出，失败记为 FAILED）。

    :param use_llm: 是否用 LLM 增强义务提取与变化摘要；None 时按 LLM_PROVIDER=api 判定
    :param default_subject: 规则提取的默认义务主体（如 个人信息处理者）
    :param language: 义务提取主语言（zh / en）
    :param sync_legacy: 首版入库后是否同步旧 regulation_articles 表（种子数据使用）
    """
    run = IngestionRun(source_id=source.id, regulation_id=source.regulation_id, status="RUNNING")
    db.add(run)
    db.commit()
    db.refresh(run)
    try:
        _run_pipeline(db, source, run, use_llm=use_llm, default_subject=default_subject,
                      language=language, sync_legacy=sync_legacy)
    except Exception as exc:  # 流水线失败不拖垮服务，运行记录标记 FAILED
        db.rollback()
        run.status = "FAILED"
        run.error = str(exc)[:500]
        run.finished_at = _utcnow()
        db.commit()
    db.refresh(run)
    return run


def _run_pipeline(
    db: Session,
    source: RegulatorySource,
    run: IngestionRun,
    *,
    use_llm: bool | None,
    default_subject: str,
    language: str,
    sync_legacy: bool,
) -> None:
    now = _utcnow()
    if use_llm is None:
        use_llm = get_settings().llm_provider == "api"

    # ---- 1. Fetch → Normalize → Hash ----
    adapter = get_adapter(source)
    raw = adapter.fetch()
    normalized = adapter.extract_content(raw)
    if not normalized:
        raise ValueError("抓取内容为空")
    digest = content_hash(normalized)
    source.last_checked_at = now

    regulation = db.get(Regulation, source.regulation_id)
    if regulation is None:
        raise ValueError("来源未关联法规（source.regulation_id 为空）")

    # ---- 2. 保存原始快照（按内容哈希去重）----
    existing_snapshot = db.scalar(
        select(SourceSnapshot).where(
            SourceSnapshot.source_id == source.id, SourceSnapshot.content_hash == digest
        )
    )
    if existing_snapshot is not None:
        snapshot_uri = existing_snapshot.snapshot_uri
    else:
        snapshot_uri = _write_snapshot(source.id, digest, normalized)
        db.add(
            SourceSnapshot(
                source_id=source.id,
                regulation_id=regulation.id,
                snapshot_uri=snapshot_uri,
                content_hash=digest,
                content_length=len(normalized.encode("utf-8")),
            )
        )

    # ---- 3. 版本检测：SHA256 与当前版本一致则 NO_CHANGE ----
    current: RegulationVersion | None = None
    if regulation.current_version_id:
        current = db.get(RegulationVersion, regulation.current_version_id)
    if current is None:
        current = db.scalar(
            select(RegulationVersion).where(
                RegulationVersion.regulation_id == regulation.id,
                RegulationVersion.is_current.is_(True),
            )
        )
    run.from_version_id = current.id if current else None
    if current is not None and current.content_hash == digest:
        source.last_success_at = now
        run.status = "NO_CHANGE"
        run.to_version_id = current.id
        run.finished_at = _utcnow()
        db.commit()
        return

    # ---- 4. 结构解析 + 创建新版本（Version, never overwrite）----
    units = parse_legal_text(normalized, source.parser_type)
    articles = article_units(units)
    if not articles:
        raise ValueError("未能从文本中解析出任何法律条款")

    version = RegulationVersion(
        regulation_id=regulation.id,
        version_number=(current.version_number + 1) if current else 1,
        published_at=regulation.published_at,
        effective_from=regulation.effective_at,
        source_url=source.base_url or regulation.canonical_source_url,
        raw_document_uri=snapshot_uri,
        normalized_text=normalized,
        content_hash=digest,
        retrieved_at=now,
        is_current=True,
        review_status="UNREVIEWED",
    )
    db.add(version)
    db.flush()

    # 法律单元树落库（父节点一定先于子节点出现，两遍插入即可拿到父 id）
    unit_rows: list[LegalUnit] = []
    for parsed in units:
        row = LegalUnit(
            version_id=version.id,
            parent_unit_id=None,
            unit_type=parsed.unit_type,
            unit_number=parsed.unit_number,
            heading=parsed.heading,
            text=parsed.text,
            path=parsed.path,
            order_index=parsed.order_index,
        )
        db.add(row)
        unit_rows.append(row)
    db.flush()
    for parsed, row in zip(units, unit_rows):
        if parsed.parent_index is not None:
            row.parent_unit_id = unit_rows[parsed.parent_index].id
    db.flush()

    old_unit_map: dict[str, LegalUnit] = {}
    if current is not None:
        old_units = db.scalars(
            select(LegalUnit).where(
                LegalUnit.version_id == current.id, LegalUnit.unit_type == "article"
            )
        ).all()
        old_unit_map = {article_key(u.unit_number): u for u in old_units}
    parsed_by_key: dict[str, tuple[LegalUnit, ParsedUnit]] = {}
    for parsed, row in zip(units, unit_rows):
        if parsed.unit_type == "article":
            parsed_by_key[article_key(row.unit_number)] = (row, parsed)

    # ---- 5. 条级 Diff ----
    changes = (
        diff_articles(
            {k: (u.unit_number, u.text) for k, u in old_unit_map.items()},
            {k: (u.unit_number, u.text) for k, (u, _) in parsed_by_key.items()},
        )
        if current is not None
        else []
    )

    new_chunk_dicts: list[dict] = []
    deactivated_chunk_ids: set[int] = set()
    change_rows: list[RegulationChange] = []
    new_requirement_ids: list[int] = []
    changed_keys = {article_key(c.unit_number) for c in changes if c.change_type != "REMOVED"}

    if current is None:
        # ---- 首版：全量提取 + 全量 chunk/embedding ----
        for key, (unit_row, parsed) in parsed_by_key.items():
            new_requirement_ids.extend(
                _extract_and_add_requirements(
                    db, regulation, version, unit_row,
                    language=language, default_subject=default_subject, use_llm=use_llm,
                )
            )
            new_chunk_dicts.extend(_chunk_and_embed(db, regulation, version, unit_row, parsed))
    else:
        # ---- 更新版：只处理发生变化的条款（增量）----
        for change in changes:
            old_unit = old_unit_map.get(article_key(change.old_unit_number or change.unit_number))
            new_pair = parsed_by_key.get(article_key(change.unit_number))
            requirement_ids: list[int] = []

            if change.change_type in ("MODIFIED", "REMOVED", "RENUMBERED") and old_unit is not None:
                _supersede_requirements(db, old_unit.id, now)
                deactivated_chunk_ids |= _deactivate_chunks(db, old_unit.id)
            if change.change_type != "REMOVED" and new_pair is not None:
                unit_row, parsed = new_pair
                requirement_ids = _extract_and_add_requirements(
                    db, regulation, version, unit_row,
                    language=language, default_subject=default_subject, use_llm=use_llm,
                )
                new_requirement_ids.extend(requirement_ids)
                new_chunk_dicts.extend(_chunk_and_embed(db, regulation, version, unit_row, parsed))

            summary = _llm_change_summary(change) or _rule_change_summary(change)
            change_row = RegulationChange(
                regulation_id=regulation.id,
                from_version_id=current.id,
                to_version_id=version.id,
                legal_unit_id=(new_pair[0].id if new_pair else (old_unit.id if old_unit else None)),
                change_type=change.change_type,
                old_text=change.old_text,
                new_text=change.new_text,
                semantic_summary=summary,
                materiality=change.materiality,
                requirement_ids=requirement_ids,
            )
            db.add(change_row)
            change_rows.append(change_row)

        # 未变化条款：义务复制到新版本（不重新提取）；chunk 保持有效，不重新 embedding
        for key, old_unit in old_unit_map.items():
            if key in changed_keys or key not in parsed_by_key:
                continue
            new_unit_row = parsed_by_key[key][0]
            carried = db.scalars(
                select(Requirement).where(
                    Requirement.legal_unit_id == old_unit.id,
                    Requirement.status.in_(["ACTIVE", "NEEDS_REVIEW"]),
                )
            ).all()
            for old_req in carried:
                db.add(
                    Requirement(
                        regulation_id=regulation.id,
                        version_id=version.id,
                        legal_unit_id=new_unit_row.id,
                        requirement_type=old_req.requirement_type,
                        subject_type=old_req.subject_type,
                        action_type=old_req.action_type,
                        object_type=old_req.object_type,
                        conditions_json=old_req.conditions_json,
                        exceptions_json=old_req.exceptions_json,
                        summary=old_req.summary,
                        confidence=old_req.confidence,
                        status=old_req.status,
                        effective_from=old_req.effective_from,
                    )
                )

    # ---- 6. 版本切换：旧版本失效，新版本成为当前版本 ----
    if current is not None:
        current.is_current = False
        if current.effective_to is None:
            current.effective_to = now
    regulation.current_version_id = version.id
    db.flush()

    # ---- 7. 向量索引更新（新增 chunk 进索引，失效 chunk 出索引）----
    index_legal_chunks(new_chunk_dicts)
    deactivate_legal_chunks(deactivated_chunk_ids)

    # ---- 8. 首版同步旧 regulation_articles 表（供分析工作流检索真实法条）----
    if sync_legacy and current is None:
        _sync_legacy_articles(db, regulation, new_chunk_dicts)

    # ---- 9. 一切就绪后才发布 regulation.change.ready 事件 ----
    event = None
    if change_rows:
        event = persist_change_ready_event(db, regulation, version, change_rows, new_requirement_ids)

    source.last_success_at = now
    run.status = "COMPLETED"
    run.to_version_id = version.id
    run.changes_count = len(change_rows)
    run.requirements_count = len(new_requirement_ids)
    run.chunks_count = len(new_chunk_dicts)
    run.event_id = event.id if event else None
    run.finished_at = _utcnow()
    db.commit()
