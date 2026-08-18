FROM node:22-bookworm-slim

ARG CODEX_VERSION

RUN test -n "$CODEX_VERSION" \
    && apt-get update \
    && apt-get install -y --no-install-recommends ca-certificates git python3 \
    && rm -rf /var/lib/apt/lists/* \
    && npm install --global "@openai/codex@${CODEX_VERSION}" \
    && codex --version

WORKDIR /src
COPY --chown=node:node . /src

USER node

ENTRYPOINT ["python3", "scripts/tests/codex_real_e2e.py", "--source-dir", "/src"]
