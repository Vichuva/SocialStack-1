.PHONY: dev prod test lint migrate shell

dev:
	docker-compose up --build

prod:
	docker-compose -f docker-compose.yml -f docker-compose.prod.yml up --build -d

test:
	docker-compose run --rm api pytest tests/ -v --cov=socialstack --cov-report=term-missing

lint:
	docker-compose run --rm api ruff check src/ tests/ && ruff format --check src/ tests/

migrate:
	docker-compose run --rm api alembic upgrade head

migration:
	docker-compose run --rm api alembic revision --autogenerate -m "$(MSG)"

shell:
	docker-compose run --rm api python

logs:
	docker-compose logs -f api worker-default worker-images worker-publishing

stop:
	docker-compose down

reset:
	docker-compose down -v
