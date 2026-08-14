# Multi-stage build: compile dependencies (incl. any that need a C
# toolchain, e.g. psycopg's binary extras) in a full image, then ship only
# the venv + app code in a slim runtime image.

FROM python:3.14-slim AS builder

WORKDIR /build
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir -r requirements.txt


FROM python:3.14-slim AS runtime

RUN groupadd --system app && useradd --system --gid app --create-home app

COPY --from=builder /opt/venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH" \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app
COPY --chown=app:app . .
RUN chmod +x docker-entrypoint.sh

# The fraud model artifact and Solidity contract ABIs live one level up
# (ondc_blockchain_ai/trained_models, ondc_blockchain_ai/artifacts) in a
# local checkout — see docker-compose.yml for how they're mounted into the
# container. Without them, app/ml/model.py trains a smaller model on the
# fly and the blockchain bridge no-ops (both by design, not a crash).

USER app
EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=15s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health', timeout=3)" || exit 1

ENTRYPOINT ["./docker-entrypoint.sh"]
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
