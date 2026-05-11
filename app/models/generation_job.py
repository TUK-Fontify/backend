from datetime import datetime
from sqlalchemy import BigInteger, CheckConstraint, DateTime, ForeignKey, Integer, Numeric, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base_class import Base


class GenerationJob(Base):
    __tablename__ = "generation_jobs"
    __table_args__ = (
        CheckConstraint(
            "(font_file_id IS NOT NULL AND handwriting_id IS NULL) "
            "OR (font_file_id IS NULL AND handwriting_id IS NOT NULL)",
            name="chk_generation_job_one_source",
        ),
    )

    job_id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="PENDING")
    progress: Mapped[int] = mapped_column(Integer, default=0)
    similarity_percent: Mapped[float | None] = mapped_column(Numeric(5, 2), nullable=True)
    fail_reason: Mapped[str | None] = mapped_column(String(255), nullable=True)
    requested_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, server_default=func.now())
    finished_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    user_id: Mapped[str] = mapped_column(ForeignKey("users.user_id", ondelete="CASCADE"), nullable=False)
    # Either font_file_id or handwriting_id may be null depending on the generation type.
    font_file_id: Mapped[int | None] = mapped_column(ForeignKey("font_files.font_file_id"), nullable=True)
    handwriting_id: Mapped[int | None] = mapped_column(ForeignKey("handwritings.handwriting_id"), nullable=True)

    user = relationship("User", back_populates="generation_jobs")
    font_file = relationship("FontFile", back_populates="generation_jobs")
    handwriting = relationship("Handwriting", back_populates="generation_jobs")
    generated_font = relationship("GeneratedFont", back_populates="generation_job", uselist=False)

