"""SQLAlchemy 2.x Declarative Base，所有 ORM 模型统一继承。"""

from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    """项目统一的声明式基类。"""

    pass
