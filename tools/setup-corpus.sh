#!/usr/bin/env bash
# Reproducible setup for the corpus pipeline (scripts/build_corpus.py).
# Creates tools/corpus-venv with pyosmium, then runs the build.
set -euo pipefail
cd "$(dirname "$0")/.."
python3 -m venv tools/corpus-venv
tools/corpus-venv/bin/pip install -q osmium
tools/corpus-venv/bin/python scripts/build_corpus.py --emit-mobile "$@"
