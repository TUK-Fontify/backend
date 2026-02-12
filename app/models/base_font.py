from sqlalchemy import BigInteger, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base_class import Base


class BaseFont(Base):
    __tablename__ = "base_fonts"

    base_font_id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)

    generation_jobs = relationship("GenerationJob", back_populates="base_font")
