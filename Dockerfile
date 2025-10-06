FROM python:3.12-slim-bookworm
# FROM python:3.13-slim
# FROM python:3.13

WORKDIR /app
COPY . /app/

RUN pip install .

ENV PYTHONUNBUFFERED='1'
EXPOSE 8888
ENTRYPOINT ["openroute-mcp"]
