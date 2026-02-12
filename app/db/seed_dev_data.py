from sqlalchemy import select

from app.db.session import SessionLocal
from app.models import BaseFont, User


DEFAULT_BASE_FONTS = ["Noto Sans KR", "Nanum Gothic", "Pretendard"]


def seed_dev_data() -> None:
    db = SessionLocal()
    try:
        user = db.scalar(select(User).where(User.user_id == "dev-user-001"))
        if not user:
            db.add(User(user_id="dev-user-001", email="dev@example.com", nickname="개발테스트유저"))

        for name in DEFAULT_BASE_FONTS:
            exists = db.scalar(select(BaseFont).where(BaseFont.name == name))
            if not exists:
                db.add(BaseFont(name=name))

        db.commit()
        print("Seed complete: dev user + base fonts")
    finally:
        db.close()


if __name__ == "__main__":
    seed_dev_data()
