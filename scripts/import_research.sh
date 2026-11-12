#!/usr/bin/env bash
# Copies the text files of a frozen research library into research/<version>.
# Only text formats are copied. Databases, PDFs and archives are skipped.
#
# Usage: scripts/import_research.sh /path/to/library_final_2026-10-28 [version]
set -euo pipefail

SRC="${1:?Give the path to the frozen library folder}"
VERSION="${2:-v1}"
DEST="$(cd "$(dirname "$0")/.." && pwd)/research/$VERSION"

mkdir -p "$DEST"
rsync -a --prune-empty-dirs \
  --include='*/' \
  --include='*.md' --include='*.csv' --include='*.json' --include='*.txt' \
  --include='*.ris' --include='*.html' --include='*.sha256' \
  --exclude='*' \
  "$SRC"/ "$DEST"/

echo "Copied to $DEST"
du -sh "$DEST"
echo "Files above 50 MB (GitHub refuses files above 100 MB):"
find "$DEST" -type f -size +50M -print
