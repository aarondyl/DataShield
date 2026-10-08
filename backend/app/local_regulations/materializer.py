"""将云端公开 Bundle 幂等物化为本地 ORM 实体。"""
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import LegalUnit, LocalRegulationBinding, Regulation, RegulationVersion, Requirement


def _binding(db: Session, entity_type: str, key: str):
    return db.scalar(select(LocalRegulationBinding).where(
        LocalRegulationBinding.entity_type == entity_type,
        LocalRegulationBinding.entity_key == key,
    ))


def _bind(db: Session, entity_type: str, key: str, local_id: int) -> None:
    row = _binding(db, entity_type, key)
    if row is None:
        db.add(LocalRegulationBinding(entity_type=entity_type, entity_key=key, local_id=local_id))
    elif row.local_id != local_id:
        raise ValueError(f"稳定键 {entity_type}:{key} 被映射到不一致的本地主键")


def materialize_bundle(db: Session, bundle: dict) -> dict[str, int]:
    """物化一个 Bundle，但不提交；调用者必须和缓存 cursor 共用事务。"""
    reg, ver = bundle["regulation"], bundle["version"]
    row = _binding(db, "regulation", reg["key"])
    regulation = db.get(Regulation, row.local_id) if row else None
    if regulation is None:
        regulation = Regulation(name=reg.get("name", reg["key"]), official_identifier=reg["key"])
        db.add(regulation); db.flush()
    regulation.name = reg.get("name", regulation.name) or regulation.name
    regulation.jurisdiction = reg.get("jurisdiction", regulation.jurisdiction)
    regulation.status = reg.get("status", regulation.status)
    _bind(db, "regulation", reg["key"], regulation.id)

    row = _binding(db, "version", ver["key"])
    version = db.get(RegulationVersion, row.local_id) if row else None
    if version is None:
        version = RegulationVersion(regulation_id=regulation.id, version_number=int(ver.get("number", 1)), normalized_text="", content_hash=ver.get("content_hash", ver["key"]))
        db.add(version); db.flush()
    if version.regulation_id != regulation.id:
        raise ValueError("版本稳定键归属的法规不一致")
    version.content_hash = ver.get("content_hash", version.content_hash)
    version.is_current = bool(ver.get("is_current", False))
    _bind(db, "version", ver["key"], version.id)
    if version.is_current:
        db.execute(RegulationVersion.__table__.update().where(
            RegulationVersion.regulation_id == regulation.id,
            RegulationVersion.id != version.id,
        ).values(is_current=False))
        regulation.current_version_id = version.id

    units: dict[str, int] = {}
    for item in bundle.get("legal_units", []):
        row = _binding(db, "legal_unit", item["key"])
        unit = db.get(LegalUnit, row.local_id) if row else None
        if unit is None:
            unit = LegalUnit(version_id=version.id, unit_type="article")
            db.add(unit); db.flush()
        if unit.version_id != version.id:
            raise ValueError("法律单元稳定键归属的版本不一致")
        unit.unit_type, unit.unit_number = item.get("unit_type", "article"), item.get("unit_number", "")
        unit.heading, unit.text, unit.path = item.get("heading", ""), item.get("text", ""), item.get("path", "")
        _bind(db, "legal_unit", item["key"], unit.id); units[item["key"]] = unit.id

    reqs: dict[str, int] = {}
    for item in bundle.get("requirements", []):
        unit_id = units.get(item.get("legal_unit_key"))
        if item.get("legal_unit_key") and unit_id is None:
            raise ValueError("Requirement 引用了 Bundle 中不存在的法律单元")
        row = _binding(db, "requirement", item["key"])
        req = db.get(Requirement, row.local_id) if row else None
        if req is None:
            req = Requirement(regulation_id=regulation.id, version_id=version.id, legal_unit_id=unit_id)
            db.add(req); db.flush()
        if req.regulation_id != regulation.id or req.version_id != version.id:
            raise ValueError("Requirement 稳定键归属的法规或版本不一致")
        req.legal_unit_id = unit_id
        req.requirement_type, req.action_type = item.get("type", "obligation"), item.get("action", "")
        req.summary, req.status = item.get("summary", ""), item.get("status", "NEEDS_REVIEW")
        req.conditions_json, req.exceptions_json = item.get("conditions", []), item.get("exceptions", [])
        req.confidence = float(item.get("confidence", 0.0))
        _bind(db, "requirement", item["key"], req.id); reqs[item["key"]] = req.id
    db.flush()
    return {"regulation_id": regulation.id, "version_id": version.id, **{f"requirement:{k}": v for k, v in reqs.items()}}
