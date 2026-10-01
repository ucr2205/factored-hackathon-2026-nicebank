FROM python:3.12-slim
ENV POETRY_VERSION=2.1.3 \
    POETRY_VIRTUALENVS_CREATE=false \
    POETRY_NO_INTERACTION=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    HF_HOME=/models
RUN python -m pip install --no-cache-dir "poetry==${POETRY_VERSION}"
WORKDIR /app
COPY pyproject.toml poetry.lock ./
RUN poetry install --only main --no-root && rm -rf /root/.cache
# Bake the e5 weights at the exact revision the classifier was trained with; at runtime the hub is offline.
COPY model/ model/
RUN python -c "import json; from sentence_transformers import SentenceTransformer; \
e5 = json.load(open('model/classifier.json'))['e5']; SentenceTransformer(e5['model'], revision=e5['revision'], device='cpu')"
ENV HF_HUB_OFFLINE=1 \
    TRANSFORMERS_OFFLINE=1
COPY app.py .
EXPOSE 8000
# Two workers by default: under 100 concurrent users the single worker was the bottleneck (load test 2026-10-01:
# chat p50 2.2 s -> 0.34 s, throughput +57%) for ~0.5 GB more memory. Metrics are merged across workers.
ENV ML_WORKERS=2 \
    PROMETHEUS_MULTIPROC_DIR=/tmp/prometheus
CMD ["sh", "-c", "rm -rf \"$PROMETHEUS_MULTIPROC_DIR\" && mkdir -p \"$PROMETHEUS_MULTIPROC_DIR\" && exec uvicorn app:app --host 0.0.0.0 --port 8000 --workers \"$ML_WORKERS\""]
