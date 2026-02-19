from sqlalchemy import BigInteger, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base_class import Base


class FontFamily(Base):
    __tablename__ = "font_families"

    font_family_id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False, unique=True)

    font_files = relationship("FontFile", back_populates="font_family", cascade="all, delete-orphan")
