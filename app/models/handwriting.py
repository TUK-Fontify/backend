from datetime import datetime
from sqlalchemy import BigInteger, DateTime, ForeignKey, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base_class import Base


class Handwriting(Base):
    __tablename__ = "handwritings"

    handwriting_id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    image_url: Mapped[str] = mapped_column(String(255), nullable=False)
    submitted_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, server_default=func.now())
    user_id: Mapped[str] = mapped_column(ForeignKey("users.user_id", ondelete="CASCADE"), nullable=False)

    user = relationship("User", back_populates="handwritings")
    generation_jobs = relationship("GenerationJob", back_populates="handwriting")

