from pathlib import Path
import psycopg2

BASE_DIR = Path(r"C:/Users/USER/Desktop/english_only_google_fonts")

conn = psycopg2.connect(
    host="localhost",
    database="font",
    user="postgres",
    password="postgres",
    port="5432"
)

cur = conn.cursor()

families = set()

# 폴더 이름 = family 이름
for family_dir in BASE_DIR.iterdir():
    if family_dir.is_dir():
        family_name = family_dir.name.lower()
        families.add(family_name)

for family_name in families:
    cur.execute("""
        INSERT INTO font_family(name)
        VALUES(%s)
        ON CONFLICT(name)
        DO NOTHING
    """, (family_name,))

conn.commit()

print(f"{len(families)}개 family 저장 완료")