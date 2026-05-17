from pathlib import Path
import psycopg2

FONT_ROOT = Path(
    r"C:/Users/USER/Desktop/english_only_google_fonts"
)

BASE_URL = (
    "https://fontify-986995923828-ap-northeast-2-an.s3.ap-northeast-2.amazonaws.com/"
    "english_only_google_fonts"
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

    if not family_dir.is_dir():
        continue

    family_name = family_dir.name


    # family_id 조회
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


    # family 안 파일들 순회
    for file in family_dir.iterdir():

        if not file.is_file():
            continue

        file_name = file.name


        path = (
            f"{BASE_URL}/"
            f"{family_name}/"
            f"{file_name}"
        )


        cur.execute("""
            INSERT INTO font_files(
                file_path,
                font_family_id
            )
            VALUES(%s,%s)
        """, (
            path,
            family_id
        ))


conn.commit()

print("완료")