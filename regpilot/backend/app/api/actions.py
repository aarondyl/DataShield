"""合规整改动作查询接口。"""

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models import ComplianceAction
from app.schemas.action import ActionOut

router = APIRouter(prefix="/actions", tags=["actions"])


@router.get("", response_model=list[ActionOut])
def list_actions(db: Session = Depends(get_db)) -> list[ActionOut]:
    """全部整改动作（含 run_id），按生成时间倒序。"""
    actions = db.scalars(select(ComplianceAction).order_by(ComplianceAction.id.desc())).all()
    return [ActionOut.model_validate(a) for a in actions]
