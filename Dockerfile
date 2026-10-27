FROM python:3.12-slim AS base
ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1 DATA_DIR=/data
WORKDIR /app
COPY requirements.txt ./
RUN pip install --no-cache-dir --require-hashes -r requirements.txt && useradd --uid 1000 --create-home app
COPY hisobdon ./hisobdon
ARG APP_VERSION=local
ENV APP_VERSION=${APP_VERSION}

FROM base AS test
COPY requirements-dev.txt pyproject.toml ./
RUN pip install --no-cache-dir --require-hashes -r requirements-dev.txt
COPY tests ./tests
CMD ["python", "-m", "pytest", "-q"]

FROM base AS runtime
USER 1000:1000
HEALTHCHECK --interval=30s --timeout=10s --start-period=90s --retries=3 CMD python -m hisobdon health
CMD ["python", "-m", "hisobdon"]
