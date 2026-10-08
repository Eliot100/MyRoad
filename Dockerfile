# MyRoad platform image: one FastAPI process, SQLite on a mounted volume.
# Build:  docker build --build-arg CONTENT_REF=<MyRoad-content commit SHA, required> -t myroad .
# Run:    docker run -p 8080:8080 -v myroad-data:/data myroad

# --- content: path JSON from Eliot100/MyRoad-content at a fixed ref ---
FROM python:3.12-slim@sha256:05cda9777409a9c3ffddd94a4c476b79f0769a0b4857f0c7ed9226b6800b0d6f AS content
ARG CONTENT_REF
ADD https://github.com/Eliot100/MyRoad-content/archive/${CONTENT_REF}.tar.gz /tmp/content.tar.gz
RUN mkdir /content \
 && tar -xzf /tmp/content.tar.gz -C /content --strip-components=1 \
 && find /content -maxdepth 1 -name '*.md' -delete \
 && rm -rf /content/.github /content/scripts

# --- app ---
FROM python:3.12-slim@sha256:05cda9777409a9c3ffddd94a4c476b79f0769a0b4857f0c7ed9226b6800b0d6f
ARG CONTENT_REF
LABEL org.opencontainers.image.source="https://github.com/Eliot100/MyRoad" \
      org.myroad.content-ref="${CONTENT_REF}"
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    MYROAD_DB=/data/myroad.db \
    CONTENT_DIR=/app/packages/core/content \
    PORT=8080 \
    FORWARDED_ALLOW_IPS=127.0.0.1
# FORWARDED_ALLOW_IPS must be set at deploy time to the proxy's exact IP or network, never "*".
# Left at 127.0.0.1 behind a real proxy, the app sees the scheme as http and every client as the
# proxy's IP, which breaks per-IP login limits.

WORKDIR /app/packages/core

# Dependencies first, so code changes don't reinstall them.
COPY packages/core/pyproject.toml ./
RUN mkdir -p src/myroad_core && touch src/myroad_core/__init__.py \
 && pip install -e ".[api]"

# Code (editable install: the app reads locales/ and templates from this tree).
COPY freeze/v0/ /app/freeze/v0/
COPY packages/core/ ./
COPY --from=content /content ./content

RUN useradd --system --uid 10001 --home /app myroad \
 && mkdir -p /data \
 && chown -R myroad /data
USER myroad

EXPOSE 8080
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
  CMD python -c "import os,urllib.request; urllib.request.urlopen('http://127.0.0.1:%s/health' % os.environ.get('PORT','8080'), timeout=4)"

# One process only: login limits and the DB lock live in memory, and SQLite has one writer.
CMD ["sh", "-c", "exec uvicorn myroad_core.ui.app:app --host 0.0.0.0 --port \"$PORT\" --workers 1 --proxy-headers --forwarded-allow-ips \"$FORWARDED_ALLOW_IPS\""]
