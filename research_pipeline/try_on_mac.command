#!/bin/bash
# A small trial on the Mac with the Gemma model the Telegram team uses:
# one theme, about 20 papers screened and a few read. Takes roughly 5 to 15 minutes.
# Quality is lower than on the Spark with the big model; this only shows that everything works.
cd "$(dirname "$0")" || exit 1
PY=""
[ -f ../persona_chat/.python_path ] && PY=$(cat ../persona_chat/.python_path)
[ -x "$PY" ] || PY=$(command -v python3)
MODEL="gemma4:12b-mlx"

if ! curl -s -m 3 http://localhost:11434/api/tags >/dev/null; then
  echo "Starting Ollama..."
  open -g -a Ollama
  sleep 8
fi

echo "Trial run with $MODEL. The log is saved in trial_log.txt."
echo
"$PY" -u researcher.py run --test --model "$MODEL" --no-think 2>&1 | tee trial_log.txt
echo
echo "Finished. Open the reports/test folder to see the result. You can close this window."
