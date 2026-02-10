help:
	@echo "SynTera Commands"

install:
	pip install -r requirements.txt

dev:
	python -m uvicorn backend.main:app --reload

# Run without reload (use on Windows if --reload causes PermissionError)
run:
	python -m uvicorn backend.main:app --host 127.0.0.1 --port 8000

test:
	pytest

docker-run:
	docker-compose -f deployment/docker-compose.yml up -d

clean:
	find . -type d -name __pycache__ -exec rm -r {} +
	find . -type f -name "*.pyc" -delete

