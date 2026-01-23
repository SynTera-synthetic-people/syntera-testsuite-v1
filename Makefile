help:
	@echo "SynTera Commands"

install:
	pip install -r requirements.txt

dev:
	python backend/main.py

test:
	pytest

docker-run:
	docker-compose -f deployment/docker-compose.yml up -d

clean:
	find . -type d -name __pycache__ -exec rm -r {} +
	find . -type f -name "*.pyc" -delete

