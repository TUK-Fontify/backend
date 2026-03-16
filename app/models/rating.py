from datetime import datetime
from sqlalchemy import BigInteger, CheckConstraint, DateTime, ForeignKey, Integer, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base_class import Base


class Rating(Base):
    __tablename__ = "ratings"
    __table_args__ = (
        CheckConstraint("score BETWEEN 1 AND 5", name="ck_ratings_score_range"),
        UniqueConstraint("user_id", "generated_font_id", name="unique_user_font"),
    )

    rating_id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    score: Mapped[int] = mapped_column(Integer, nullable=False)
    comment: Mapped[str | None] = mapped_column(String(255), nullable=True)
    rated_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, server_default=func.now())
    user_id: Mapped[str] = mapped_column(ForeignKey("users.user_id", ondelete="CASCADE"), nullable=False)
    generated_font_id: Mapped[int] = mapped_column(
        ForeignKey("generated_fonts.generated_font_id", ondelete="CASCADE"), nullable=False
    )

    user = relationship("User", back_populates="ratings")
    generated_font = relationship("GeneratedFont", back_populates="ratings")

