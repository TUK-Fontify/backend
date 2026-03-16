from sqlalchemy import select

from app.db.session import SessionLocal
from app.models import FontFamily, FontFile, User


DEFAULT_FONT_FILES = [
    ("Noto Sans KR", 400, "normal", "static/fonts/noto-sans-kr/NotoSansKR-Regular.ttf"),
    ("Noto Sans KR", 700, "normal", "static/fonts/noto-sans-kr/NotoSansKR-Bold.ttf"),
    ("Nanum Gothic", 400, "normal", "static/fonts/nanum-gothic/NanumGothic-Regular.ttf"),
    ("Pretendard", 400, "normal", "static/fonts/pretendard/Pretendard-Regular.ttf"),
]


def seed_dev_data() -> None:
    db = SessionLocal()
    try:
        user = db.scalar(select(User).where(User.user_id == "dev-user-001"))
        if not user:
            db.add(User(user_id="dev-user-001", email="dev@example.com", nickname="개발테스트유저"))

        for family_name, weight, style, file_path in DEFAULT_FONT_FILES:
            family = db.scalar(select(FontFamily).where(FontFamily.name == family_name))
            if not family:
                family = FontFamily(name=family_name)
                db.add(family)
                db.flush()

            exists = db.scalar(
                select(FontFile).where(
                    FontFile.font_family_id == family.font_family_id,
                    FontFile.weight == weight,
                    FontFile.style == style,
                )
            )
            if not exists:
                db.add(
                    FontFile(
                        font_family_id=family.font_family_id,
                        weight=weight,
                        style=style,
                        file_path=file_path,
                    )
                )

        db.commit()
        print("Seed complete: dev user + font families/files")
    finally:
        db.close()


if __name__ == "__main__":
    seed_dev_data()
