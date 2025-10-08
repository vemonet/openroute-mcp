FROM ghcr.io/astral-sh/uv:python3.13-trixie-slim
# https://docs.astral.sh/uv/guides/integration/docker
# FROM python:3.13-slim

WORKDIR /app

COPY . /app/

RUN uv sync --frozen
# RUN pip install .

ENV PYTHONUNBUFFERED='1'
EXPOSE 8888
ENTRYPOINT ["uv", "run", "openroute-mcp", "--http"]
