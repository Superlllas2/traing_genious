#!/usr/bin/env bash
cd "$(dirname "$0")" || exit 1
if [ -f logs/researcher.pid ] && kill "$(cat logs/researcher.pid)" 2>/dev/null; then
  rm -f logs/researcher.pid
  echo "Stopped. Start again any time with ./start_spark.sh: it continues where it stopped."
else
  rm -f logs/researcher.pid
  echo "It was not running."
fi
