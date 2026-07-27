#!/usr/bin/env bash
set -e
cd "$(dirname "$0")"
if [ ! -d "venv" ]; then
  echo "Error: venv klasoru bulunamadi."
  echo "Once venv'i olustur ve paketleri yukle:"
  echo "  python3 -m venv venv"
  echo "  source venv/bin/activate"
  echo "  pip install -r requirements.txt"
  exit 1
fi
source venv/bin/activate
streamlit run app.py
