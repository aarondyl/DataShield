"""The single compatibility boundary between tenants, companies and products."""

from sqlalchemy.orm import Session

from app.models import Company, Product


class TenantOwnershipError(ValueError):
    """Base error for tenant/product ownership resolution."""


class TenantNotFoundError(TenantOwnershipError):
    pass


class ProductNotFoundError(TenantOwnershipError):
    pass


class TenantProductMismatchError(TenantOwnershipError):
    pass


def resolve_tenant(db: Session, tenant_id: int) -> Company:
    """Resolve the current Company-backed tenant compatibility identity."""

    tenant = db.get(Company, tenant_id)
    if tenant is None:
        raise TenantNotFoundError(f"Tenant {tenant_id} does not exist")
    return tenant


def resolve_tenant_product(db: Session, tenant_id: int, product_id: int) -> Product:
    """Resolve a tenant-owned product through the current Company mapping.

    For the MVP, ``tenant_id`` maps to ``Company.id``. Keeping that assumption
    here lets a future Tenant model replace it without changing agent nodes.
    """

    resolve_tenant(db, tenant_id)
    product = db.get(Product, product_id)
    if product is None:
        raise ProductNotFoundError(f"Product {product_id} does not exist")
    if product.company_id != tenant_id:
        raise TenantProductMismatchError(
            f"Product {product_id} does not belong to tenant {tenant_id}"
        )
    return product
