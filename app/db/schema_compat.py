from sqlalchemy import text
from sqlalchemy.engine import Engine


SCHEMA_COMPAT_SQL = """
DO $$
BEGIN
    IF to_regclass('public.font_family') IS NOT NULL
       AND to_regclass('public.font_families') IS NOT NULL THEN
        INSERT INTO font_families (font_family_id, name)
        SELECT font_family_id, name
        FROM font_family
        ON CONFLICT DO NOTHING;
    END IF;
END $$;

ALTER TABLE IF EXISTS font_files DROP CONSTRAINT IF EXISTS fk_font_family;
ALTER TABLE IF EXISTS font_files DROP CONSTRAINT IF EXISTS font_files_font_family_id_fkey;

DELETE FROM font_files ff
WHERE NOT EXISTS (
    SELECT 1
    FROM font_families f
    WHERE f.font_family_id = ff.font_family_id
);

DO $$
BEGIN
    IF to_regclass('public.font_files') IS NOT NULL
       AND to_regclass('public.font_families') IS NOT NULL
       AND NOT EXISTS (
           SELECT 1
           FROM pg_constraint
           WHERE conrelid = 'font_files'::regclass
             AND conname = 'fk_font_files_font_families'
       ) THEN
        ALTER TABLE font_files
        ADD CONSTRAINT fk_font_files_font_families
        FOREIGN KEY (font_family_id)
        REFERENCES font_families(font_family_id)
        ON DELETE CASCADE;
    END IF;
END $$;

ALTER TABLE IF EXISTS generation_jobs
    ALTER COLUMN font_file_id DROP NOT NULL,
    ALTER COLUMN handwriting_id DROP NOT NULL;

ALTER TABLE IF EXISTS generation_jobs
    DROP CONSTRAINT IF EXISTS chk_generation_job_one_source;

ALTER TABLE IF EXISTS generation_jobs
    ADD CONSTRAINT chk_generation_job_one_source
    CHECK (
        (font_file_id IS NOT NULL AND handwriting_id IS NULL)
        OR
        (font_file_id IS NULL AND handwriting_id IS NOT NULL)
    )
    NOT VALID;
"""


def repair_schema(engine: Engine) -> None:
    with engine.begin() as conn:
        conn.execute(text(SCHEMA_COMPAT_SQL))
