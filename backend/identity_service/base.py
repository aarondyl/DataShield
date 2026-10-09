from sqlalchemy.orm import DeclarativeBase


class IdentityBase(DeclarativeBase):
    """Separate metadata: identity migrations cannot create tenant/product tables."""
