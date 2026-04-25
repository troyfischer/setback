# Testing Guide

This directory contains the test suite for the Setback game server.

## Test Types

### Unit Tests (`tests/unit/`)
- **Fast**: Use in-memory mocks (FakeRedis, SQLite)
- **Isolated**: Test individual components
- **No Docker**: Use FastAPI TestClient directly
- **Run with**: `make utest` or `pytest tests/unit`

### Integration Tests (`tests/integration/`)
- **Slower**: Spin up full Docker environment
- **Real services**: PostgreSQL, Redis, Caddy
- **End-to-end**: Test complete workflows
- **Run with**: `make itest` or `pytest tests/integration`

## Running Tests

```bash
# Unit tests (fast, for development)
make utest

# Integration tests (local Docker)
make itest

# Integration tests (remote server)
make itest-remote URL=https://setback.troyfischer.net

# All tests
make test-all

# Run specific test file
pytest tests/unit/test_server.py -v

# Run specific test function
pytest tests/unit/test_server.py::test_game -v

# Run with markers
pytest -m unit
pytest -m integration
```

## Testing Against Live Server

To verify a deployment, run integration tests against the live server:

```bash
make itest-remote URL=https://setback.troyfischer.net
```

Or with environment variable:

```bash
TEST_BASE_URL=https://setback.troyfischer.net pytest tests/integration -v
```

## Development Workflow

1. **Write unit tests first**: Fast feedback loop
2. **Run unit tests frequently**: `make test-unit`
3. **Run integration tests before commits**: `make test-integration`
4. **Run all tests before PR**: `make test-all`

## Test Structure

```
tests/
├── unit/
│   ├── test_server.py       # Game mechanics with mocks
│   └── test_manager.py      # Game manager tests
├── integration/
│   └── test_server.py       # Full stack tests with Docker
└── README.md
```

## Troubleshooting

**Integration tests fail to start**:
- Make sure Docker is running
- Check if ports 8000/5432/6379 are available
- Clean up: `make clean`

**Tests hang**:
- Testcontainers may not have stopped properly
- Run: `docker compose down -v`

**Permission errors**:
- Ensure Docker has proper permissions
- Try: `docker system prune -f`
