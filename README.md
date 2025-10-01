# Your App Name

A brief description of what your application does.

## Features

- Feature 1
- Feature 2
- Feature 3

## Requirements

- Python 3.12+
- [uv](https://docs.astral.sh/uv/) for dependency management

## Installation

1. Clone the repository:
```bash
git clone https://github.com/yourusername/your-app-name.git
cd your-app-name
```

2. Install dependencies with uv:
```bash
uv sync --dev
```

## Usage

```bash
# Run the application
uv run your-app

# Or activate the virtual environment
source .venv/bin/activate
python -m your_app
```

## Development

### Setup

```bash
# Install development dependencies
uv sync --dev
```

### Code Quality

```bash
# Format code
uv run ruff format

# Lint code
uv run ruff check

# Type checking
uv run mypy src/

# Run tests
uv run pytest
```

### Running Tests

```bash
# Run all tests
uv run pytest

# Run with coverage
uv run pytest --cov=your_app
```

## Project Structure

```
your-app-name/
├── src/
│   └── your_app/
│       ├── __init__.py
│       └── main.py
├── tests/
├── pyproject.toml
├── README.md
└── LICENSE
