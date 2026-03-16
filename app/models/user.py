from datetime import datetime
from sqlalchemy import DateTime, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base_class import Base


class User(Base):
    __tablename__ = "users"

    user_id: Mapped[str] = mapped_column(String(50), primary_key=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    nickname: Mapped[str] = mapped_column(String(30), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, server_default=func.now())

    handwritings = relationship("Handwriting", back_populates="user", cascade="all, delete-orphan")
    generation_jobs = relationship("GenerationJob", back_populates="user", cascade="all, delete-orphan")
    download_records = relationship("DownloadRecord", back_populates="user", cascade="all, delete-orphan")
    ratings = relationship("Rating", back_populates="user", cascade="all, delete-orphan")

