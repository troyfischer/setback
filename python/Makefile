.PHONY: test test-unit test-integration test-all clean dev-up dev-down dev-rebuild

init:
	uv sync --all-extras

utest:
	uv run pytest tests/unit -v

itest:
	@echo "Stopping any existing containers..."
	@docker compose down -v 2>/dev/null || true
	uv run pytest tests/integration -v

itest-remote:
	@if [ -z "$(URL)" ]; then \
		echo "Error: URL parameter required"; \
		echo "Usage: make itest-remote URL=https://setback.troyfischer.net"; \
		exit 1; \
	fi
	TEST_BASE_URL=$(URL) uv run pytest tests/integration -v

test-all:
	uv run pytest tests -v

dev-up:
	ENABLE_DEV_AUTH=1 CADDYFILE=./Caddyfile.local docker compose up -d

dev-rebuild:
	ENABLE_DEV_AUTH=1 CADDYFILE=./Caddyfile.local docker compose up -d --build

dev-down:
	docker compose down

clean:
	docker compose down -v
	docker system prune -f

lint:
	uv run ruff check --fix src tests

format:
	uv run ruff format src tests

typecheck:
	uv run mypy src
