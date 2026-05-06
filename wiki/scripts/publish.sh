#!/usr/bin/env bash
# publish.sh — 重建注册表（wiki/public -> ../docs 符号链接，无需 rsync）
set -euo pipefail

WIKI_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PUBLIC_DIR="$WIKI_ROOT/public"

echo "[publish] 构建 pages.json..."
python3 "$WIKI_ROOT/scripts/build_registry.py" "$PUBLIC_DIR/pages" \
    --out "$PUBLIC_DIR/pages.json" \
    --out-lite "$PUBLIC_DIR/pages.lite.json"

FTS_SCRIPT="$WIKI_ROOT/scripts/build_fts_index.py"
if [[ -f "$FTS_SCRIPT" ]]; then
    echo "[publish] 构建全文检索索引..."
    python3 "$FTS_SCRIPT" 2>/dev/null || true
fi

echo "[publish] 完成（wiki/public 即 docs/，直接生效）"
