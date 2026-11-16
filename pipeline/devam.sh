#!/bin/bash
# Embedding koşusunu kaldığı yerden devam ettirir (DB'dekiler atlanır)
cd "$(dirname "$0")" && uv run --no-sync python 03_parcala_embedle_yukle.py
