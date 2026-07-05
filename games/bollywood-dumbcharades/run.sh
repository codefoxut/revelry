#!/bin/bash
# Run Bollywood Dumb Charades
# Uses the pipecat venv which has both fastapi and anthropic

VENV="/Users/ujjwal/bigjobs/pipecat/.venv"
PYTHON="$VENV/bin/python"
UVICORN="$VENV/bin/uvicorn"

cd "$(dirname "$0")"

if [ -z "$ANTHROPIC_API_KEY" ]; then
  echo "⚠️  ANTHROPIC_API_KEY not set."
  echo "    export ANTHROPIC_API_KEY=your-key-here"
  exit 1
fi

echo "🎬 Starting Bollywood Dumb Charades..."
echo "   Open: http://localhost:8080"
echo ""

"$UVICORN" main:app --host 0.0.0.0 --port 8080 --reload
