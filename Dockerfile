FROM python:3.11-slim

WORKDIR /build

RUN apt update \
    && apt install -y git \
    && rm -rf /var/lib/apt/lists/*

COPY . .

RUN pip install -r dev-requirements.txt \
    && pip install -e . \
    && pre-commit install

CMD pytest