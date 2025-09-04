#! /bin/bash
echo "Activating virtual environment"
python -m venv venv
source ./venv/bin/activate
echo "Starting SnapApi with integrated SnapWatcher operator"
uvicorn app:app --host 0.0.0.0 --port 8000 --workers 1
