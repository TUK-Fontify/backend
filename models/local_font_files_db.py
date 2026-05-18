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

for file in BASE_DIR.rglob("*.ttf"):

    # 예:
    # english_only_google_fonts/worksans/WorkSans[wght].ttf

    family_name = file.parent.name.lower()
    file_path = str(file.resolve())   # 절대경로 저장
    # file_path = str(file)            # 상대경로 저장 원하면 이거

    cur.execute("""
        SELECT font_family_id
        FROM font_family
        WHERE name = %s
    """, (family_name,))

    result = cur.fetchone()

    if result is None:
        print(f"{family_name} 없음")
        continue

    family_id = result[0]

    cur.execute("""
        INSERT INTO font_files(
            file_path,
            font_family_id
        )
        VALUES(%s, %s)
        ON CONFLICT DO NOTHING
    """, (
        file_path,
        family_id
    ))

conn.commit()

print("완료")