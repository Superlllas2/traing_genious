#!/usr/bin/env bash
# Starts the research in the background. It keeps running after you close the terminal or SSH session.
cd "$(dirname "$0")" || exit 1
PY=$(cat .python_path 2>/dev/null || command -v python3)
mkdir -p logs
if [ -f logs/researcher.pid ] && kill -0 "$(cat logs/researcher.pid)" 2>/dev/null; then
  echo "Already running (process $(cat logs/researcher.pid))."
  exit 0
fi
nohup "$PY" -u researcher.py run "$@" >> logs/run.out 2>&1 &
echo $! > logs/researcher.pid
echo "Research started in the background (process $!)."
echo
echo "  Progress:  $PY researcher.py status"
echo "  Live log:  tail -f logs/run.out"
echo "  Stop:      ./stop_spark.sh   (starting again continues where it stopped)"
