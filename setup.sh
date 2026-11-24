#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")"
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements-data.txt
.venv/bin/python scripts/download_sinan_ce.py
.venv/bin/python scripts/download_ibge_mesh.py
.venv/bin/python scripts/prepare_graph.py
.venv/bin/python scripts/prepare_confirmed_weekly.py
