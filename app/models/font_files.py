from sqlalchemy import BigInteger, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base_class import Base


class FontFile(Base):
    __tablename__ = "font_files"
    __table_args__ = (
        UniqueConstraint("font_family_id", name="unique_family_weight_style"),
    )

    font_file_id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    font_family_id: Mapped[int] = mapped_column(
        ForeignKey("font_family.font_family_id", ondelete="CASCADE"), nullable=False
    )
    file_path: Mapped[str] = mapped_column(String(255), nullable=False)

    font_family = relationship("FontFamily", back_populates="font_files")
    generation_jobs = relationship("GenerationJob", back_populates="font_file")
