# ---- Etapa base ----
FROM python:3.11-slim AS base

# Instalar ffmpeg (necesario para yt-dlp y faster-whisper)
RUN apt-get update && \
    apt-get install -y --no-install-recommends ffmpeg && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /app

# ---- Dependencias ----
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# ---- Código ----
COPY main.py .

# Pre-descargar el modelo Whisper durante el build para arranque más rápido
ARG WHISPER_MODEL=base
RUN python -c "from faster_whisper import WhisperModel; WhisperModel('${WHISPER_MODEL}', device='cpu', compute_type='int8')"

# ---- Runtime ----
ENV WHISPER_MODEL=${WHISPER_MODEL}
ENV DEVICE=cpu
ENV COMPUTE_TYPE=auto
ENV MAX_DURATION=3600

EXPOSE 8000

# Uvicorn con 1 worker (Whisper no es thread-safe, escalar con réplicas)
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1"]
