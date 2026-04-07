#!/bin/bash
set -e; cd "$(dirname "$0")"
command -v node >/dev/null || { echo "Node.js required"; exit 1; }
[ ! -d "node_modules" ] && npm install
echo "🚀 http://localhost:5173"
npm run dev
