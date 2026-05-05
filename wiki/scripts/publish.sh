#!/usr/bin/env bash
# publish.sh — 构建并发布资治通鉴 Wiki 到 docs/（GitHub Pages）
set -euo pipefail

WIKI_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PROJECT_ROOT="$(cd "$WIKI_ROOT/.." && pwd)"
PUBLIC_DIR="$WIKI_ROOT/public"
DOCS_DIR="$PROJECT_ROOT/docs"

echo "[publish] 构建 pages.json..."
python3 "$WIKI_ROOT/scripts/build_registry.py" "$PUBLIC_DIR/pages" \
    --out "$PUBLIC_DIR/pages.json" \
    --out-lite "$PUBLIC_DIR/pages.lite.json"

FTS_SCRIPT="$WIKI_ROOT/scripts/build_fts_index.py"
if [[ -f "$FTS_SCRIPT" ]]; then
    echo "[publish] 构建全文检索索引..."
    python3 "$FTS_SCRIPT" 2>/dev/null || true
fi

echo "[publish] 同步到 docs/..."
mkdir -p "$DOCS_DIR"
rsync -a --delete \
    --exclude='*.pyc' --exclude='__pycache__' \
    "$PUBLIC_DIR/" "$DOCS_DIR/"

echo "[publish] 完成 → $DOCS_DIR"
