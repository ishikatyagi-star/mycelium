# Mycelium API (FastAPI). FalkorDB runs separately (FalkorDB Cloud, or the falkordb/falkordb image).
FROM python:3.12-slim
ENV PYTHONUNBUFFERED=1 PYTHONPATH=/app UV_SYSTEM_PYTHON=1 HF_HOME=/app/.cache FASTEMBED_CACHE_PATH=/app/.cache/fastembed
RUN pip install --no-cache-dir uv
WORKDIR /app
COPY pyproject.toml uv.lock ./
RUN uv export --frozen --no-dev --no-hashes -o requirements.txt && uv pip install --system -r requirements.txt
COPY core ./core
COPY api ./api
COPY seed ./seed
COPY mcp_server ./mcp_server
COPY fleet ./fleet
COPY eval ./eval
# bake the embedding model into the image (no download on cold start)
RUN python -c "from core.embed import embed; embed('warmup')"
EXPOSE 8000
CMD ["sh", "-c", "uvicorn api.main:app --host 0.0.0.0 --port ${PORT:-8000} --workers ${WEB_CONCURRENCY:-2}"]
