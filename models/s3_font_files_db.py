import boto3
import psycopg2

BUCKET = "fontify-986995923828-ap-northeast-2-an"
PREFIX = "english_only_google_fonts"

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

s3 = boto3.client("s3")


paginator = s3.get_paginator("list_objects_v2")

for page in paginator.paginate(
    Bucket=BUCKET,
    Prefix=PREFIX
):

    if "Contents" not in page:
        continue


    for obj in page["Contents"]:

        key = obj["Key"]

        # 예:
        # english_only_google_fonts/worksans/WorkSans[wght].ttf

        parts = key.split("/")


        # 파일 아니면 스킵
        if len(parts) < 3:
            continue


        family_name = parts[1]

        file_name = parts[-1]


        # family_id 조회
        cur.execute("""
            SELECT font_family_id
            FROM font_family
            WHERE name = %s
        """, (family_name,))

        result = cur.fetchone()


        if result is None:
            print(
                f"{family_name} 없음"
            )
            continue


        family_id = result[0]


        path = (
            f"{BASE_URL}/"
            f"{key}"
        )

        # 중복 방지
        cur.execute("""
            INSERT INTO font_files(
                file_path,
                font_family_id
            )
            VALUES(%s,%s)
            ON CONFLICT DO NOTHING
        """, (
            path,
            family_id
        ))


conn.commit()

print("완료")