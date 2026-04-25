# SynTera Test Suite — Installation guide (local development)

This guide is for someone **new to the repo** who wants a **working localhost** with the web UI and API. It assumes basic familiarity with a terminal (PowerShell on Windows, or bash on macOS/Linux).

**Related docs:** [PRODUCT_WALKTHROUGH.md](PRODUCT_WALKTHROUGH.md), [ARCHITECTURE.md](ARCHITECTURE.md).

---

## 1. What you will have at the end

- **PostgreSQL** running and reachable.
- **Python 3.11+** virtual environment with dependencies installed.
- A **`.env`** file with at least `DATABASE_URL` and `SECRET_KEY`.
- The app responding at **`http://localhost:8000`** with **`GET /health`** returning JSON.

---

## 2. Prerequisites

| Requirement | Notes |
|-------------|--------|
| **Git** | To clone the repository. |
| **Python 3.11 or newer** | Matches `Dockerfile` (`python:3.11-slim`). 3.12 is commonly used on dev machines. |
| **PostgreSQL 14+** (recommended) | The app uses **`psycopg2`** and SQLAlchemy; local or Docker Postgres both work. |
| **(Optional)** Docker Desktop | Easiest way to run Postgres without a global install. |
| **(Optional)** OpenAI / Anthropic API keys | Only for **Market research** and **Simulation** LLM features. |
| **(Optional)** AWS credentials | Only for **Industry surveys** S3 listing. |

**Heavy Python deps:** `requirements.txt` includes **PyTorch** and **sentence-transformers**. First `pip install` can take several minutes and several GB of disk space. If you only need API + DB without ML-heavy paths, your team may maintain a slimmer requirements file in the future; today the repo expects the full file.

---

## 3. Clone the repository

```bash
git clone <YOUR_REPO_URL>
cd syntera-test-suite-v5
```

Use the URL from your Git host (for example GitHub).

---

## 4. Choose how to run PostgreSQL

### Option A — Docker Compose (recommended for newcomers)

The repo includes **`deployment/docker-compose.yml`** with **Postgres 16** and an **app** service.

From the project root:

```bash
docker compose -f deployment/docker-compose.yml up -d db
```

This starts only the **`db`** service (Postgres) on port **5432** with:

- User: `syntera`
- Password: `password`
- Database: `syntera`

**Connection string for `.env`:**

```env
DATABASE_URL=postgresql://syntera:password@127.0.0.1:5432/syntera
```

Wait until `pg_isready` succeeds (Compose defines a healthcheck; ~10–30 seconds first time).

### Option B — Postgres already installed on your machine

Create a database and user, then set `DATABASE_URL` accordingly, for example:

```env
DATABASE_URL=postgresql://myuser:mypass@127.0.0.1:5432/mydb
```

If your host requires SSL (common on managed cloud dev DBs), append query params as required, e.g. `?sslmode=require`.

---

## 5. Python virtual environment

### Windows (PowerShell)

```powershell
python -m venv venv
.\venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
```

### macOS / Linux

```bash
python3 -m venv venv
source venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
```

If `pip install` fails on **torch**, ensure you have enough disk space and a stable network; on some corporate networks you may need an internal PyPI mirror.

---

## 6. Environment file (`.env`)

1. Copy the example file:

   ```bash
   cp .env.example .env
   ```

   On Windows PowerShell: `Copy-Item .env.example .env`

2. Edit **`.env`** in the project root (same folder as `README.md`).

**Minimum required for a successful boot:**

```env
ENVIRONMENT=development
DEBUG=false
DATABASE_URL=postgresql://syntera:password@127.0.0.1:5432/syntera
SECRET_KEY=use-a-long-random-string-here-not-the-default
```

- **`DATABASE_URL`** must point to a running Postgres instance (see section 4).
- **`SECRET_KEY`** signs JWTs; use a long random value in any shared or production-like environment.

**Optional keys** (see `.env.example` for full list):

- `OPENAI_API_KEY`, `ANTHROPIC_API_KEY` — Market research / simulation.
- `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`, `S3_INDUSTRY_BUCKET`, … — Industry surveys tab.

> **Security:** Never commit `.env` to Git. It is listed in `.gitignore`.

> **Note:** `.env.example` in the repo may contain duplicate blocks from merges; when in doubt, keep a **single** `DATABASE_URL` line pointing at the database you actually started.

---

## 7. Start the application

From the **project root** (directory that contains `backend/`, `config/`, `app/`):

```bash
python backend/main.py
```

Or with uvicorn directly:

```bash
python -m uvicorn backend.main:app --host 127.0.0.1 --port 8000
```

**Windows note:** If `--reload` causes permission or `pyvenv.cfg` errors, avoid reload (as above) or use `make run` from the `Makefile`.

On startup the app:

1. Loads `.env`.
2. Runs **`init_db()`** — creates tables and applies safe **`ALTER ... IF NOT EXISTS`** migrations.

You should see log lines indicating the server is listening on **port 8000** (unless you override uvicorn).

---

## 8. Verify it works

1. **Health**

   ```bash
   curl http://127.0.0.1:8000/health
   ```

   Expect: `{"status":"healthy","service":"syntera-test-suite"}` (exact keys may vary slightly).

2. **Browser**

   Open **`http://localhost:8000`**. You should get the main HTML shell and static assets from `/static/...`.

3. **Optional: Test Lab DB audit** (validates schema expectations against your DB)

   ```powershell
   $env:DATABASE_URL="postgresql://syntera:password@127.0.0.1:5432/syntera"
   python scripts/audit_test_lab_db.py
   ```

   Or: `make audit-test-lab-db` after exporting `DATABASE_URL`.

---

## 9. Full stack with Docker (app + database)

To run the **pre-built image** from Compose (app + db):

```bash
docker compose -f deployment/docker-compose.yml up -d
```

The compose file sets `DATABASE_URL` for the app container to talk to the `db` service. Open **`http://localhost:8000`**.

To rebuild the app image after code changes, your team typically uses `docker compose build app` (see `Dockerfile` in repo root).

---

## 10. Users and login

- The app authenticates against the **`users`** table in the same Postgres database (see `backend/models/user.py` and `auth` router).
- There is **no default seeded user** in production-style configs; your environment provider must create users in the database or you use an existing shared auth database.

If login fails, confirm:

1. DB connectivity (`DATABASE_URL`).
2. User row exists and `is_active` is true.
3. Password hash matches (bcrypt).

---

## 11. Common problems

| Symptom | Things to check |
|---------|------------------|
| `DATABASE_URL` empty / connection refused | Postgres not running; wrong host/port; SSL params. |
| `ModuleNotFoundError: config` or `backend` | Run from **project root**, or use `python backend/main.py` which adjusts `sys.path`. |
| Port 8000 in use | Stop other apps or run uvicorn with `--port 8001` and open that port. |
| `413 Request Entity Too Large` behind nginx | Increase `client_max_body_size` (see `README.md`). |
| Very slow first `pip install` | Torch download size; use SSD and stable network. |
| Industry surveys empty / errors | AWS env vars missing or bucket permissions. |
| Market research errors | Missing `OPENAI_API_KEY` / `ANTHROPIC_API_KEY`. |

---

## 12. Makefile shortcuts

| Command | Purpose |
|---------|---------|
| `make install` | `pip install -r requirements.txt` |
| `make dev` | Uvicorn with `--reload` |
| `make run` | Uvicorn without reload (Windows-friendly) |
| `make audit-test-lab-db` | Run DB audit script |
| `make docker-run` | `docker compose up` using `deployment/docker-compose.yml` |

---

## 13. Next steps

- Read [PRODUCT_WALKTHROUGH.md](PRODUCT_WALKTHROUGH.md) to learn the UI flow.
- Read [ARCHITECTURE.md](ARCHITECTURE.md) to see how routers and services fit together.
- For schema rules, see [TEST_LAB_DATABASE_SCHEMA.md](TEST_LAB_DATABASE_SCHEMA.md).
