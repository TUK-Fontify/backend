# backend

FastAPI starter structure with PostgreSQL.

## Setup

```bash
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
```

## Configure env

Fill `.env` values for PostgreSQL connection.

## Initialize DB tables

```bash
python -m app.db.init_db
```

## Seed dev data (before Firebase)

```bash
python -m app.db.seed_dev_data
```

This creates:
- `dev-user-001` user
- sample base fonts

## Run server

```bash
python run.py
```

## Pre-Firebase test flow

1. Call `POST /api/v1/auth/dev-login` (works only when `DEV_BYPASS_AUTH=true`)
2. For protected APIs, set header: `x-user-id: dev-user-001`
3. Test in order:
   - `POST /api/v1/handwriting/upload`
   - `POST /api/v1/handwriting/create`
   - `GET /api/v1/generation/{job_id}`

## API docs

- Swagger UI: http://127.0.0.1:8000/docs
- ReDoc: http://127.0.0.1:8000/redoc
