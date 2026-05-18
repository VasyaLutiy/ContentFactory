FROM python:3.12-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

RUN groupadd --system contentfactory \
    && useradd --system --gid contentfactory --home-dir /app contentfactory

COPY pyproject.toml ./
COPY app ./app
COPY docker/api-entrypoint.sh /usr/local/bin/content-factory-api-entrypoint
COPY docker/worker-entrypoint.sh /usr/local/bin/content-factory-worker-entrypoint

RUN pip install --upgrade pip \
    && pip install . \
    && chmod +x /usr/local/bin/content-factory-api-entrypoint /usr/local/bin/content-factory-worker-entrypoint \
    && mkdir -p /var/lib/content-factory/artifacts \
    && chown -R contentfactory:contentfactory /app /var/lib/content-factory

USER contentfactory

EXPOSE 8000

ENTRYPOINT ["/usr/local/bin/content-factory-api-entrypoint"]
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
