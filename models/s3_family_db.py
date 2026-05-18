import boto3
import psycopg2

BUCKET = "fontify-986995923828-ap-northeast-2-an"

conn = psycopg2.connect(
    host="localhost",
    database="font",
    user="postgres",
    password="postgres",
    port="5432"
)

cur = conn.cursor()

s3 = boto3.client("s3")

families = set()

paginator = s3.get_paginator("list_objects_v2")

for page in paginator.paginate(Bucket=BUCKET):

    if "Contents" not in page:
        continue

    for obj in page["Contents"]:

        key = obj["Key"]

        # 예:
        # english_only_google_fonts/worksans/WorkSans[wght].ttf

        parts = key.split("/")

        if len(parts) < 3:
            continue

        family_name = parts[1].lower()

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