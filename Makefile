.PHONY: up migrate test integration eval-run eval-score eval-sync hooks

ADAPTER ?= phase1

up:
	docker compose up -d --build

migrate:
	alembic upgrade head

test:
	pytest

integration:
	pytest -m integration

eval-run:
	REPOSITORY_BACKEND=memory python -m eval.harness.run --adapter $(ADAPTER)

eval-score:
	python -m eval.harness.score $(RUN)

eval-sync:
	python -m eval.harness.sync

hooks:
	ln -sf "$(CURDIR)/scripts/check_status_updated.sh" "$$(git rev-parse --git-path hooks)/commit-msg"
