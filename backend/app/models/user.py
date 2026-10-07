"""注册用户账号模型（邮箱注册登录）。"""
from datetime import datetime
from sqlalchemy import Boolean,DateTime,ForeignKey,Integer,String,func
from sqlalchemy.orm import Mapped,mapped_column
from app.db.base import Base
class User(Base):
    __tablename__="users"
    id:Mapped[int]=mapped_column(primary_key=True,autoincrement=True)
    email:Mapped[str]=mapped_column(String(320),unique=True,index=True,nullable=False)
    password_hash:Mapped[str]=mapped_column(String(500),nullable=False)
    display_name:Mapped[str]=mapped_column(String(200),nullable=False)
    company_id:Mapped[int]=mapped_column(ForeignKey("companies.id"),nullable=False)
    edition:Mapped[str]=mapped_column(String(20),default="developer",nullable=False)
    email_verified:Mapped[bool]=mapped_column(Boolean,default=False,nullable=False)
    disabled:Mapped[bool]=mapped_column(Boolean,default=False,nullable=False)
    created_at:Mapped[datetime]=mapped_column(DateTime,server_default=func.now(),nullable=False)
    last_login_at:Mapped[datetime|None]=mapped_column(DateTime)
