from datetime import datetime
from sqlalchemy import BigInteger, DateTime, ForeignKey, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base_class import Base


class DownloadRecord(Base):
    __tablename__ = "download_records"

    download_id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    downloaded_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, server_default=func.now())
    user_id: Mapped[str] = mapped_column(ForeignKey("users.user_id", ondelete="CASCADE"), nullable=False)
    generated_font_id: Mapped[int] = mapped_column(
        ForeignKey("generated_fonts.generated_font_id", ondelete="CASCADE"), nullable=False
    )

    user = relationship("User", back_populates="download_records")
    generated_font = relationship("GeneratedFont", back_populates="download_records")

