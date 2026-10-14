#!/bin/sh
# Hosted demo: Ollama serves Gemma next to Déjà on the same box.
ollama serve > /tmp/ollama.log 2>&1 &
exec python -m deja --public --port "${PORT:-7860}" --home /tmp/deja
