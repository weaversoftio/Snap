#! /bin/bash
echo "Starting..."
python -m venv venv
source ./venv/bin/activate
uvicorn app:app --host 0.0.0.0 --port 8000 --workers 1 --reload
