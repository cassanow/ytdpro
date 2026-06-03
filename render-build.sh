#!/usr/bin/env bash
# exit on error
set -o errexit

# Instala as dependências do Python
pip install -r requirements.txt

# Cria a pasta para o FFmpeg se não existir
mkdir -p ffmpeg_bin

# Baixa o FFmpeg estático para Linux
curl -L https://johnvansickle.com/ffmpeg/releases/ffmpeg-release-amd64-static.tar.xz | tar -xJ --strip-components=1 -C ffmpeg_bin