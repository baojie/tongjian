#!/usr/bin/env bash
# 快捷启动资治通鉴 Wiki 本地服务
set -euo pipefail
WIKI_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
"$WIKI_DIR/wiki-daemon.sh" start "${1:-1084}"
