from pathlib import Path
import psycopg2

FONT_ROOT = Path(
    r"C:/Users/USER/Desktop/english_only_google_fonts"
)

conn = psycopg2.connect(
    host="localhost",
    database="font",
    user="postgres",
    password="postgres",
    port="5432"
)

cur = conn.cursor()

for family_dir in FONT_ROOT.iterdir():

    # 폴더만 처리
    if not family_dir.is_dir():
        continue

    family_name = family_dir.name.lower()

    cur.execute("""
        INSERT INTO font_family (name)
        VALUES (%s)
        ON CONFLICT (name)
        DO NOTHING
    """, (family_name,))


conn.commit()