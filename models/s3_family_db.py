import boto3
import psycopg2

BUCKET = "fontify-986995923828-ap-northeast-2-an"
PREFIX = "english_only_google_fonts/"

conn = psycopg2.connect(
    host="localhost",
    database="font",
    user="postgres",
    password="postgres",
    port="5432"
)

cur = conn.cursor()

s3 = boto3.client(
    "s3",
    region_name="ap-northeast-2"
)

families = set()

paginator = s3.get_paginator("list_objects_v2")

for page in paginator.paginate(
    Bucket=BUCKET,
    Prefix=PREFIX
):

    if "Contents" not in page:
        continue

    for obj in page["Contents"]:

        key = obj["Key"]

        relative_key = key.removeprefix(PREFIX)
        parts = relative_key.split("/")

        if len(parts) < 2:
            continue

        family_name = parts[0].lower()
        families.add(family_name)

for family_name in sorted(families):

    cur.execute("""
        INSERT INTO font_family(name)
        VALUES(%s)
        ON CONFLICT(name)
        DO NOTHING
    """, (family_name,))

conn.commit()

print(f"{len(families)}개 family 저장 완료")