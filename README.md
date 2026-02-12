# SynTera Test Suite - Production Ready

Complete statistical validation framework for synthetic data.

## Quick Start

### Local Development

**Option 1: Using Virtual Environment (Recommended)**
```bash
# Create virtual environment
python -m venv venv

# Activate virtual environment
# On Windows:
venv\Scripts\activate
# On Linux/Mac:
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Run the server
python backend/main.py
```

**Option 2: Using System Python**
```bash
# Install dependencies
pip install -r requirements.txt

# Run the server
python backend/main.py
```

The server will start on http://localhost:8000

**No PostgreSQL?** Use SQLite for local dev: set `DATABASE_URL=sqlite:///./syntera.db` in your `.env` (or copy from `.env.example`). The app will create `syntera.db` in the project root.

**Windows:** If `python -m uvicorn backend.main:app --reload` fails with "PermissionError" or "No pyvenv.cfg file", run without reload: `python backend/main.py` or `python -m uvicorn backend.main:app`.

### Docker
```bash
docker-compose -f deployment/docker-compose.yml up -d
```

### Production: "Request Entity Too Large" (413)

If you see **413 Request Entity Too Large** when uploading files or pasting large report text (e.g. Market Research), the limit is usually set by your **reverse proxy** (e.g. Nginx), not the app.

- **Nginx:** In your `server` or `http` block add: `client_max_body_size 50M;` then reload nginx. See `deployment/nginx.conf.example`.
- **Other proxies:** Increase the allowed request body size (e.g. 50MB) for the app’s location.

## Features
- 8 Statistical tests
- RESTful API
- Interactive Dashboard
- PostgreSQL Database
- Docker & K8s Ready
- 97.8% Accuracy

## API
- POST /api/surveys/ - Create
- GET /api/surveys/ - List
- POST /api/validation/compare/{id} - Validate
- GET /health - Health check

Visit http://localhost:8000

