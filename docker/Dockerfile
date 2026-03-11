# multi-stage build for the fastapi api server
# usage: docker build -f docker/Dockerfile -t webhook-api .

# ---------------------------------------------------------------------------
# stage 1: builder - install python dependencies
# ---------------------------------------------------------------------------
FROM python:3.12-slim AS builder

WORKDIR /build

# copy requirements first for layer caching
COPY requirements.txt .

# install into /install prefix so runtime stage can copy wholesale
RUN pip install --no-cache-dir --prefix=/install -r requirements.txt

# ---------------------------------------------------------------------------
# stage 2: runtime - lean image with only what is needed to run
# ---------------------------------------------------------------------------
FROM python:3.12-slim AS runtime

# create non-root user
RUN addgroup --system app && adduser --system --ingroup app app

# copy installed packages from builder
COPY --from=builder /install /usr/local

WORKDIR /app

# copy application source, alembic migrations, and ini
COPY app/ app/
COPY alembic/ alembic/
COPY alembic.ini .

USER app

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
