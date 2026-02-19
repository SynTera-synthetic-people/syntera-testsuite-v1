#!/bin/bash
# Discard local __pycache__ changes so 'git pull' does not abort.
# Run this from the app repo root before 'git pull origin main'.
# (Those files are no longer tracked; .gitignore ignores them.)
git restore backend/routers/__pycache__/ ml_engine/__pycache__/ 2>/dev/null || \
git checkout -- backend/routers/__pycache__/ ml_engine/__pycache__/ 2>/dev/null || true
