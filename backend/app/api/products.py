"""产品管理接口：POST / GET 列表（支持 ?company_id= 过滤）/ GET{id} / PUT{id}。"""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models import Company, Product
from app.schemas.product import ProductCreate, ProductOut, ProductUpdate

router = APIRouter(prefix="/products", tags=["products"])


@router.post("", response_model=ProductOut, status_code=201)
def create_product(payload: ProductCreate, db: Session = Depends(get_db)) -> Product:
    """创建产品（企业必须已存在）。"""
    if db.get(Company, payload.company_id) is None:
        raise HTTPException(status_code=404, detail="所属企业不存在，请先创建企业")
    product = Product(**payload.model_dump())
    db.add(product)
    db.commit()
    db.refresh(product)
    return product


@router.get("", response_model=list[ProductOut])
def list_products(
    company_id: int | None = Query(None, description="按企业过滤"),
    db: Session = Depends(get_db),
) -> list[Product]:
    """产品列表，可选按企业 ID 过滤。"""
    stmt = select(Product).order_by(Product.id)
    if company_id is not None:
        stmt = stmt.where(Product.company_id == company_id)
    return list(db.scalars(stmt).all())


@router.get("/{product_id}", response_model=ProductOut)
def get_product(product_id: int, db: Session = Depends(get_db)) -> Product:
    """产品详情。"""
    product = db.get(Product, product_id)
    if product is None:
        raise HTTPException(status_code=404, detail="产品不存在")
    return product


@router.put("/{product_id}", response_model=ProductOut)
def update_product(product_id: int, payload: ProductUpdate, db: Session = Depends(get_db)) -> Product:
    """更新产品（仅更新请求中传入的字段）。"""
    product = db.get(Product, product_id)
    if product is None:
        raise HTTPException(status_code=404, detail="产品不存在")
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(product, field, value)
    db.commit()
    db.refresh(product)
    return product
