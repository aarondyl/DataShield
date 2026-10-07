"""Opaque, revocable evaluation sessions for browser previews."""
from datetime import datetime
from sqlalchemy import DateTime,ForeignKey,String,func
from sqlalchemy.orm import Mapped,mapped_column
from app.db.base import Base
class EvaluationSession(Base):
    __tablename__="evaluation_sessions"
    id:Mapped[int]=mapped_column(primary_key=True)
    token_hash:Mapped[str]=mapped_column(String(64),unique=True,index=True,nullable=False)
    evaluation_user_id:Mapped[str]=mapped_column(String(64),nullable=False,index=True)
    company_id:Mapped[int]=mapped_column(ForeignKey("companies.id",ondelete="CASCADE"),nullable=False,index=True)
    edition:Mapped[str]=mapped_column(String(20),nullable=False)
    created_at:Mapped[datetime]=mapped_column(DateTime,server_default=func.now(),nullable=False)
    expires_at:Mapped[datetime]=mapped_column(DateTime,nullable=False,index=True)
    revoked_at:Mapped[datetime|None]=mapped_column(DateTime)
    user_id:Mapped[int|None]=mapped_column(ForeignKey("users.id"),nullable=True)
