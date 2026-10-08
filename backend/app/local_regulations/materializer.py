"""将公开法规 Bundle 物化为本地业务 SQLite 的真实法规实体。"""
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.models import Regulation, RegulationVersion, LegalUnit, Requirement

def materialize_bundle(db: Session, bundle: dict) -> dict[str, int]:
    reg=bundle["regulation"]; ver=bundle["version"]
    row=db.scalar(select(Regulation).where(Regulation.official_identifier==reg["key"]))
    if row is None:
        row=Regulation(name=reg["name"],jurisdiction=reg.get("jurisdiction",""),official_identifier=reg["key"],status=reg.get("status","in_force")); db.add(row); db.flush()
    version_number=int(ver.get("number",1))
    version=db.scalar(select(RegulationVersion).where(RegulationVersion.regulation_id==row.id,RegulationVersion.version_number==version_number))
    if version is None:
        version=RegulationVersion(regulation_id=row.id,version_number=version_number,normalized_text="",content_hash=ver.get("content_hash",ver["key"]),is_current=bool(ver.get("is_current",True))); db.add(version); db.flush()
    row.current_version_id=version.id
    units={}
    for item in bundle.get("legal_units",[]):
        unit=db.scalar(select(LegalUnit).where(LegalUnit.version_id==version.id,LegalUnit.path==item.get("path","")))
        if unit is None:
            unit=LegalUnit(version_id=version.id,unit_type="article",unit_number=item.get("unit_number",""),heading=item.get("heading",""),text=item.get("text",""),path=item.get("path","")); db.add(unit); db.flush()
        units[item["key"]]=unit.id
    reqs={}
    for item in bundle.get("requirements",[]):
        unit_id=units.get(item.get("legal_unit_key")); req=Requirement(regulation_id=row.id,version_id=version.id,legal_unit_id=unit_id,requirement_type=item.get("type","obligation"),action_type=item.get("action",""),summary=item.get("summary",""),conditions_json=item.get("conditions",[]),exceptions_json=item.get("exceptions",[]),confidence=.8,status=item.get("status","ACTIVE")); db.add(req); db.flush(); reqs[item["key"]]=req.id
    return {"regulation_id":row.id,"version_id":version.id,**{f"requirement:{k}":v for k,v in reqs.items()}}
