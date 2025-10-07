FROM python:3.13-slim

WORKDIR /build

RUN apt update \
    && apt install -y git pipx \
    && rm -rf /var/lib/apt/lists/* \
    && pipx install uv

ENV PATH="$PATH:/root/.local/bin"

COPY . .

RUN uv run pre-commit install

CMD uv run pytest