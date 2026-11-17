.PHONY: up migrate test integration

up:
	docker compose up -d --build

migrate:
	alembic upgrade head

test:
	pytest

integration:
	pytest -m integration
