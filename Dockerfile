FROM python:3.12-slim

# ffmpeg: necessário para o yt-dlp juntar as faixas de vídeo e áudio
RUN apt-get update \
    && apt-get install -y --no-install-recommends ffmpeg \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY baixador.py app.py ./

ENV PYTHONUNBUFFERED=1

# Vídeos baixados ficam em /data (montado do seu computador)
WORKDIR /data

ENTRYPOINT ["python", "/app/baixador.py"]
