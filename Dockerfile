FROM ghcr.io/astral-sh/uv:python3.12-bookworm AS base
WORKDIR /app
COPY pyproject.toml uv.lock ./
ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev
COPY . .

FROM python:3.12-slim-bullseye AS final
EXPOSE 8181
ENV PYTHONUNBUFFERED=1
WORKDIR /app
COPY --from=base /app /app
ENV PATH="/app/.venv/bin:$PATH"
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8181"]
