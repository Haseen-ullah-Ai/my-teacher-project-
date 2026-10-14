FROM python:3.11-slim AS dependencies

ENV PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_NO_CACHE_DIR=1 \
    PYTHONDONTWRITEBYTECODE=1
WORKDIR /build
COPY backend/requirements-lock.txt .
RUN python -m pip install --prefix=/install -r requirements-lock.txt

FROM python:3.11-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH="/usr/local/bin:${PATH}" \
    DATA_DIR=/app/data \
    REPORTS_DIR=/app/reports
WORKDIR /app/backend

RUN python -m pip uninstall --yes packaging \
    && groupadd --system --gid 10001 researchpilot \
    && useradd --system --uid 10001 --gid researchpilot --home-dir /app researchpilot \
    && mkdir -p /app/data /app/reports \
    && chown -R researchpilot:researchpilot /app

COPY --from=dependencies /install /usr/local
COPY --chown=researchpilot:researchpilot backend/app ./app
COPY --chown=researchpilot:researchpilot backend/alembic ./alembic
COPY --chown=researchpilot:researchpilot backend/alembic.ini ./alembic.ini
COPY --chown=researchpilot:researchpilot backend/entrypoint.sh /usr/local/bin/researchpilot-entrypoint
COPY --chown=researchpilot:researchpilot scripts /app/scripts
COPY --chown=researchpilot:researchpilot data /app/data

USER researchpilot
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --start-period=60s --retries=3 \
    CMD ["python", "-c", "import json, urllib.request; health=json.load(urllib.request.urlopen('http://127.0.0.1:8000/health', timeout=3)); raise SystemExit(0 if health.get('db') == 'ok' else 1)"]
ENTRYPOINT ["/bin/sh", "/usr/local/bin/researchpilot-entrypoint"]
CMD ["python", "-m", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
