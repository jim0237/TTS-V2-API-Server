#!/bin/bash
set -e

echo "Activating virtual environment..."
source /app/venv/bin/activate

echo "Installing spacy model..."
python -m spacy download en_core_web_sm

echo "Starting application..."
exec python main-ui.py