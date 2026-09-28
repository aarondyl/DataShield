"""企业管理接口：POST / GET 列表 / GET{id} / PUT{id}。"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models import Company
from app.schemas.company import CompanyCreate, CompanyOut, CompanyUpdate

router = APIRouter(prefix="/companies", tags=["companies"])


@router.post("", response_model=CompanyOut, status_code=201)
def create_company(payload: CompanyCreate, db: Session = Depends(get_db)) -> Company:
    """创建企业档案。"""
    company = Company(**payload.model_dump())
    db.add(company)
    db.commit()
    db.refresh(company)
    return company


@router.get("", response_model=list[CompanyOut])
def list_companies(db: Session = Depends(get_db)) -> list[Company]:
    """企业列表。"""
    return list(db.scalars(select(Company).order_by(Company.id)).all())


@router.get("/{company_id}", response_model=CompanyOut)
def get_company(company_id: int, db: Session = Depends(get_db)) -> Company:
    """企业详情。"""
    company = db.get(Company, company_id)
    if company is None:
        raise HTTPException(status_code=404, detail="企业不存在")
    return company


@router.put("/{company_id}", response_model=CompanyOut)
def update_company(company_id: int, payload: CompanyUpdate, db: Session = Depends(get_db)) -> Company:
    """更新企业档案（仅更新请求中传入的字段）。"""
    company = db.get(Company, company_id)
    if company is None:
        raise HTTPException(status_code=404, detail="企业不存在")
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(company, field, value)
    db.commit()
    db.refresh(company)
    return company
