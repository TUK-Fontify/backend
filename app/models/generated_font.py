from datetime import datetime
from sqlalchemy import BigInteger, DateTime, ForeignKey, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base_class import Base


class GeneratedFont(Base):
    __tablename__ = "generated_fonts"

    generated_font_id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    file_url: Mapped[str] = mapped_column(String(255), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, server_default=func.now())
    job_id: Mapped[int] = mapped_column(
        ForeignKey("generation_jobs.job_id", ondelete="CASCADE"), nullable=False, unique=True
    )

    generation_job = relationship("GenerationJob", back_populates="generated_font")
    download_records = relationship("DownloadRecord", back_populates="generated_font", cascade="all, delete-orphan")
    ratings = relationship("Rating", back_populates="generated_font", cascade="all, delete-orphan")

