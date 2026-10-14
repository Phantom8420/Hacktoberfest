# Hosted demo of Déjà (sample screens, no recording). Built for a free Hugging Face Docker Space.
FROM python:3.12-slim

RUN apt-get update && apt-get install -y --no-install-recommends curl ca-certificates zstd \
    && curl -fsSL https://ollama.com/install.sh | sh \
    && rm -rf /var/lib/apt/lists/*

RUN useradd -m -u 1000 user
USER user
ENV HOME=/home/user OLLAMA_MODELS=/home/user/ollama HF_HOME=/home/user/hf DEJA_GEMMA=gemma3:1b \
    OLLAMA_KEEP_ALIVE=-1 PYTHONUNBUFFERED=1
WORKDIR /home/user/app

COPY --chown=user requirements-space.txt .
RUN pip install --no-cache-dir --user -r requirements-space.txt

# Bake both models into the image so the first visitor doesn't wait for downloads.
RUN ollama serve & sleep 5 && ollama pull gemma3:1b
RUN python -c "from faster_whisper import WhisperModel; WhisperModel('base.en', device='cpu', compute_type='int8')"

COPY --chown=user deja deja
COPY --chown=user start.sh .
EXPOSE 7860
CMD ["sh", "start.sh"]
