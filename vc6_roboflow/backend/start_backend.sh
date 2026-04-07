#!/bin/bash
set -e
cd "$(dirname "$0")"
echo "=================================="
echo " VisionCount v6 + Roboflow Gender"
echo "=================================="
[ ! -d venv ] && python3 -m venv venv
source venv/bin/activate
pip install -q --upgrade pip
pip install -q "numpy==1.26.4"
pip install -q -r requirements.txt
echo ""
echo "Server starting on http://0.0.0.0:8000"
uvicorn main:app --host 0.0.0.0 --port 8000 --reload
