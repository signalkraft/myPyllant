FROM python:3-slim

WORKDIR /build

RUN apt update \
    && apt install -y git \
    && rm -rf /var/lib/apt/lists/*

COPY . .

RUN pip install -r requirements-dev.txt \
    && pip install -e . \
    && pre-commit install

CMD pytest