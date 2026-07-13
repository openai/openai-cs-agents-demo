FROM python:3.11-slim-bookworm

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_INDEX_URL=https://mirrors.cloud.tencent.com/pypi/simple \
    PIP_TRUSTED_HOST=mirrors.cloud.tencent.com

RUN sed -i 's|http://deb.debian.org/debian|http://mirrors.tencent.com/debian|g; s|http://deb.debian.org/debian-security|http://mirrors.tencent.com/debian-security|g' /etc/apt/sources.list.d/debian.sources \
    && apt-get update \
    && apt-get install -y --no-install-recommends clamav curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY python-backend/requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

COPY python-backend/ ./

RUN useradd --create-home --uid 10001 appuser \
    && mkdir -p /app/data \
    && chown -R appuser:appuser /app

USER appuser
EXPOSE 8000

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000", "--proxy-headers"]
