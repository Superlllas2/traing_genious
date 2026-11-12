#!/usr/bin/env bash
# One time setup on the DGX Spark (or any Linux machine with Ollama).
# Safe to run again: it skips what is already done.
set -u
cd "$(dirname "$0")" || exit 1

say() { printf '\n== %s\n' "$*"; }
confirm() { local answer; read -r -p "$1 [y/N] " answer; [[ "$answer" =~ ^([yY]|[yY]es)$ ]]; }

say "Python"
PY=$(command -v python3) || { echo "python3 not found. Install it: sudo apt install python3"; exit 1; }
"$PY" -c 'import sys; sys.exit(0 if sys.version_info >= (3, 9) else 1)' || { echo "Python 3.9 or newer is needed."; exit 1; }
echo "Found $("$PY" --version)."

say "PDF reading (pypdf)"
if [ ! -x .venv/bin/python ]; then
  "$PY" -m venv .venv 2>/dev/null || echo "Could not make a virtual environment. To fix: sudo apt install python3-venv, then run this again."
fi
if [ -x .venv/bin/python ]; then
  PY=.venv/bin/python
  if "$PY" -c 'import pypdf' 2>/dev/null; then
    echo "pypdf is installed."
  elif "$PY" -m pip install --quiet pypdf; then
    echo "pypdf installed."
  else
    echo "pypdf install failed. The researcher still works, but reads PDFs only from their abstracts."
  fi
fi
echo "$PY" > .python_path

say "Ollama and the model"
MODEL=$("$PY" -c 'import json; print(json.load(open("research.json"))["llm"]["model"])')
if ! command -v ollama >/dev/null 2>&1; then
  echo "Ollama is not installed. Install it with:"
  echo "  curl -fsSL https://ollama.com/install.sh | sh"
  echo "Then run this script again."
  exit 1
fi
if ! ollama list >/dev/null 2>&1; then
  echo "Ollama is installed but not running. Start it with:  sudo systemctl start ollama"
  echo "Then run this script again."
  exit 1
fi
if ollama list | awk 'NR > 1 {print $1}' | grep -qx "$MODEL"; then
  echo "$MODEL is ready."
elif confirm "Download $MODEL now? It is big (gpt-oss:120b is about 65 GB)."; then
  ollama pull "$MODEL" || exit 1
else
  echo "Skipped. Download it later with:  ollama pull $MODEL"
fi

say "Telegram and OpenAlex (both optional)"
"$PY" researcher.py setup

say "Check"
"$PY" researcher.py check

say "Start after a reboot"
LINE="@reboot cd $(pwd) && ./start_spark.sh"
if crontab -l 2>/dev/null | grep -qF "$LINE"; then
  echo "Already set: the research continues by itself after a reboot."
elif confirm "Continue the research by itself after the Spark restarts?"; then
  (crontab -l 2>/dev/null; echo "$LINE") | crontab - && echo "Done."
fi

chmod +x start_spark.sh stop_spark.sh 2>/dev/null
echo
echo "All set. Start the research with:  ./start_spark.sh"
