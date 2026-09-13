# Build from the REPO ROOT so the image can COPY src/ and data/.
#   docker build -f firebase/scraper/Dockerfile .
FROM python:3.11-slim
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

WORKDIR /app
ENV UV_COMPILE_BYTECODE=1

COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project

COPY src/ ./src/
COPY scripts/ ./scripts/
COPY firebase/scripts/ ./firebase/scripts/

# Ensure the installed binary is on the path (uv installs to .venv)
ENV PATH="/app/.venv/bin:$PATH"

# The command executes the scraper, then the migration script
CMD ["bash", "-c", "python scripts/update_dataset.py && python firebase/scripts/migrate_to_firestore.py --project=mcmp-firebase"]
