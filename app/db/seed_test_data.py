from sqlalchemy import select

from app.db.schema_compat import repair_schema
from app.db.session import SessionLocal
from app.db.session import engine
from app.models import FontFamily, FontFile, User


TEST_USER_ID = "test-user-001"
TEST_USER_EMAIL = "test@example.com"
TEST_USER_NICKNAME = "Test User"

FONT_FAMILY_NAME = "Nanum Gothic"
FONT_WEIGHT = 400
FONT_STYLE = "normal"
FONT_FILE_PATH = "backend/models/NanumGothic.ttf"


def seed_user(db) -> None:
    user = db.scalar(select(User).where(User.user_id == TEST_USER_ID))
    if user:
        user.email = TEST_USER_EMAIL
        user.nickname = TEST_USER_NICKNAME
        print(f"Updated test user: {TEST_USER_ID}")
        return

    db.add(
        User(
            user_id=TEST_USER_ID,
            email=TEST_USER_EMAIL,
            nickname=TEST_USER_NICKNAME,
        )
    )
    print(f"Created test user: {TEST_USER_ID}")


def seed_font_file(db) -> None:
    family = db.scalar(select(FontFamily).where(FontFamily.name == FONT_FAMILY_NAME))
    if not family:
        family = FontFamily(name=FONT_FAMILY_NAME)
        db.add(family)
        db.flush()

    font_file = db.scalar(
        select(FontFile).where(
            FontFile.font_family_id == family.font_family_id,
            FontFile.weight == FONT_WEIGHT,
            FontFile.style == FONT_STYLE,
        )
    )

    if font_file:
        font_file.file_path = FONT_FILE_PATH
        print(f"Updated font file: {FONT_FAMILY_NAME} -> {FONT_FILE_PATH}")
        return

    db.add(
        FontFile(
            font_family_id=family.font_family_id,
            weight=FONT_WEIGHT,
            style=FONT_STYLE,
            file_path=FONT_FILE_PATH,
        )
    )
    print(f"Created font file: {FONT_FAMILY_NAME} -> {FONT_FILE_PATH}")


def seed_test_data() -> None:
    repair_schema(engine)

    db = SessionLocal()
    try:
        seed_user(db)
        seed_font_file(db)
        db.commit()
        print("Test data seed complete.")
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    seed_test_data()
