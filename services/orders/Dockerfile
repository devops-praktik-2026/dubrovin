# ---------- этап 1: собираем зависимости ----------
FROM python:3.12-slim AS builder
WORKDIR /build
COPY pyproject.toml ./
COPY orders ./orders
RUN pip install --no-cache-dir --prefix=/install .
# ---------- этап 2: собираем итоговый образ ----------
FROM python:3.12-slim
RUN useradd --create-home --uid 1000 app
COPY --from=builder /install /usr/local
WORKDIR /app
RUN chown app /app
COPY orders ./orders
USER app
EXPOSE 8000
CMD ["uvicorn", "orders.main:app", "--host", "0.0.0.0", "--port", "8000"]