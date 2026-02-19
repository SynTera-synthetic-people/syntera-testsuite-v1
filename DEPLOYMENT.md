# Deployment (AWS Production / Staging)

## Where to provide OpenAI & Claude API keys

The app reads API keys in this order:

1. **Environment variables** (recommended for production)
2. **`.env` file** in the project root (optional; do not commit real keys)

### Variable names

| Purpose | Variable | Example |
|--------|----------|--------|
| OpenAI (Market Research) | `OPENAI_API_KEY` | `sk-proj-...` |
| OpenAI model | `OPENAI_MODEL` | `gpt-4o` (default) |
| Claude (Market Research) | `ANTHROPIC_API_KEY` | `sk-ant-api03-...` |
| Claude model | `ANTHROPIC_MODEL` | `claude-sonnet-4-20250514` (default) |

### Option 1: Environment variables (recommended on AWS)

Set these in your runtime environment so the backend never needs a `.env` file.

- **ECS (Fargate / EC2)**  
  In the **Task Definition** → **Container** → **Environment**: add  
  `OPENAI_API_KEY`, `ANTHROPIC_API_KEY` (and optionally `OPENAI_MODEL`, `ANTHROPIC_MODEL`).

- **EC2 (systemd / shell)**  
  Export in the service or startup script:
  ```bash
  export OPENAI_API_KEY="sk-proj-..."
  export ANTHROPIC_API_KEY="sk-ant-api03-..."
  ```
  Or use an env file (e.g. `/opt/syntera/app.env`) that is loaded by your process manager and **not** committed to git.

- **Lambda**  
  In the **Function** → **Configuration** → **Environment variables**, add  
  `OPENAI_API_KEY` and `ANTHROPIC_API_KEY`.

- **Elastic Beanstalk**  
  **Configuration** → **Software** → **Environment properties**: add the same keys.

### Option 2: AWS Secrets Manager / Parameter Store

Do **not** paste keys into code. Store them in Secrets Manager (or SSM Parameter Store) and inject as environment variables when the container/task starts.

**Example (Secrets Manager → env vars at startup):**

- Create a secret (e.g. `syntera/prod/api-keys`) with keys `OPENAI_API_KEY` and `ANTHROPIC_API_KEY`.
- In your ECS task definition or EC2 user-data/startup script, fetch the secret and set:
  ```bash
  export OPENAI_API_KEY="$(aws secretsmanager get-secret-value --secret-id syntera/prod/api-keys --query 'SecretString' --output text | jq -r '.OPENAI_API_KEY')"
  export ANTHROPIC_API_KEY="$(aws secretsmanager get-secret-value --secret-id syntera/prod/api-keys --query 'SecretString' --output text | jq -r '.ANTHROPIC_API_KEY')"
  ```
- Then start the backend (e.g. `uvicorn` or `gunicorn`) in the same shell so it sees these env vars.

**Alternative:** Use ECS **secrets** (not env vars) that reference Secrets Manager; ECS will inject them as environment variables into the container.

### Option 3: `.env` file on the server (less ideal)

If you deploy with a `.env` file on the host:

- Create `.env` in the **project root** (same directory that contains `backend/` and `config/`).
- Add the same variables as in `.env.example` and set real values.
- Restrict file permissions and ensure `.env` is in `.gitignore` (it already is).

Prefer **environment variables** or **Secrets Manager → env** for production/staging so keys are not stored in repo or in a loose file on disk.

## Other settings

- `SECRET_KEY`: use a strong random value in production (JWT/session signing).
- `DATABASE_URL`: for production, use your RDS or other DB URL.
- `ENVIRONMENT`: set to `staging` or `production` as needed.

See `.env.example` for the full list of optional variables.

## Server deploy script and `git pull`

If your server runs a deploy script that does `git pull origin main` inside the app directory, you may see:

```text
error: Your local changes to the following files would be overwritten by merge:
    backend/routers/__pycache__/validation.cpython-312.pyc
    ml_engine/__pycache__/comparison_engine.cpython-312.pyc
Please commit your changes or stash them before you merge.
```

Those files are Python cache and are no longer tracked in the repo. To fix the deploy, **before** `git pull` in your server script, discard local changes under `__pycache__`:

**Option A – run the script (from repo root):**
```bash
bash scripts/discard-pycache-before-pull.sh
git pull origin main
```

**Option B – one-liner in your deploy script:**
```bash
git restore backend/routers/__pycache__/ ml_engine/__pycache__/ 2>/dev/null || git checkout -- backend/routers/__pycache__/ ml_engine/__pycache__/ 2>/dev/null || true
git pull origin main
```

After the pull, `__pycache__` is ignored by `.gitignore` and will not block future pulls.
