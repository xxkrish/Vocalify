FROM python:3.12-slim

# System deps (ffmpeg + basics)
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install python deps
COPY requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# Copy app
COPY . /app

# Render sets PORT. Default 10000.
ENV PORT=10000

# Start
CMD ["bash", "-lc", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT}"]
