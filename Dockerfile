FROM python:3.13-slim
# FROM python:3.13
# FROM python:3.12-slim-bookworm

WORKDIR /app
COPY . /app/

RUN pip install .

ENV PYTHONUNBUFFERED='1'
EXPOSE 8888
ENTRYPOINT ["openroute-mcp", "--http"]
