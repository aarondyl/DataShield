"""跨数据库方言的向量列类型。

PostgreSQL 下使用 pgvector 的 ``Vector(dim)`` 类型（配合 cosine distance 检索）；
SQLite 下降级为 JSON 列存储 ``list[float]``（由本地内存向量检索消费）。

ORM 侧通过 ``with_variant`` 声明同一个 Mapped 字段兼容两种后端，
Alembic 初始迁移中也按 ``op.get_bind().dialect.name`` 做同样的方言判断。
"""

from sqlalchemy import JSON
from sqlalchemy.engine.interfaces import Dialect
from sqlalchemy.types import TypeEngine

from app.core.config import get_settings


def embedding_type() -> TypeEngine:
    """返回向量列的类型对象：pg 为 Vector(dim)，sqlite 变体为 JSON。"""
    from pgvector.sqlalchemy import Vector

    dim = get_settings().embedding_dim
    return Vector(dim).with_variant(JSON(), "sqlite")


def is_sqlite_dialect(dialect: Dialect) -> bool:
    """判断方言是否为 SQLite。"""
    return dialect.name == "sqlite"
