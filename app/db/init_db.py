from sqlalchemy import text

import app.models  # noqa: F401
from app.db.base_class import Base
from app.db.schema_compat import repair_schema
from app.db.session import engine


TRIGGER_SQL = """
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS set_updated_at ON users;

CREATE TRIGGER set_updated_at
BEFORE UPDATE ON users
FOR EACH ROW
EXECUTE FUNCTION update_updated_at_column();
"""


def init_db() -> None:
    Base.metadata.create_all(bind=engine)
    repair_schema(engine)
    with engine.begin() as conn:
        conn.execute(text(TRIGGER_SQL))


if __name__ == "__main__":
    init_db()
    print("Database tables and trigger are ready.")
