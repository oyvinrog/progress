#!/bin/bash

# Activate the virtual environment and run Progress List

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

if [ ! -d ".venv" ]; then
    echo "Error: Virtual environment not found at .venv"
    echo "Please create it first with: python -m venv .venv && .venv/bin/pip install -r requirements.txt"
    exit 1
fi

source .venv/bin/activate
python -m progress_list "$@"
