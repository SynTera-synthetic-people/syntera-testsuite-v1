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

### Docker
```bash
docker-compose -f deployment/docker-compose.yml up -d
```

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

