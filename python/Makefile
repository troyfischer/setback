.PHONY: test test-unit test-integration test-all clean dev-up dev-down dev-rebuild db-upgrade db-current db-revision

DEV_ENV = \
	APP_ENV=dev \
	ENABLE_DEV_AUTH=1 \
	CADDYFILE=./Caddyfile.local \
	BASE_URL=http://localhost \
	CLIENT_ORIGIN=http://localhost:8081 \
	SESSION_SECRET=dev-session-secret-1234567890abcdef \
	JWT_SECRET=dev-jwt-secret-1234567890abcdef \
	GOOGLE_CLIENT_ID=dev-google-client-id \
	GOOGLE_CLIENT_SECRET=dev-google-client-secret \
	POSTGRES_PASSWORD=dev-postgres-password

COMPOSE = $(DEV_ENV) docker compose

init:
	uv sync --all-groups

db-upgrade:
	uv run alembic upgrade head

db-current:
	uv run alembic current

db-revision:
	@if [ -z "$(MESSAGE)" ]; then \
		echo "Error: MESSAGE parameter required"; \
		echo "Usage: make db-revision MESSAGE=\"describe change\""; \
		exit 1; \
	fi
	uv run alembic revision --autogenerate -m "$(MESSAGE)"

utest:
	uv run pytest tests/unit -v

itest:
	@echo "Stopping any existing containers..."
	@$(COMPOSE) down -v 2>/dev/null || true
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
	$(COMPOSE) up -d

dev-rebuild:
	$(COMPOSE) up -d --build

dev-down:
	$(COMPOSE) down

clean:
	$(COMPOSE) down -v
	docker system prune -f

lint:
	uv run ruff check --fix src tests

format:
	uv run ruff format src tests

typecheck:
	uv run mypy src
