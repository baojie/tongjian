#!/usr/bin/env python3
"""add_page.py — 新建 wiki 页面并自动记录修订历史。

用法:
    python3 wiki/scripts/add_page.py <slug> <content_file> \
        [--summary "新增词条: ..."] [--author butler]

    # 从 stdin 读取内容:
    echo "---\nid: foo\n---\n# foo" | python3 wiki/scripts/add_page.py foo - \
        --summary "新增词条: foo"

规则:
    - 若页面已存在则退出（用 edit_page.py）
    - 写入 wiki/public/pages/<bucket>/<slug>.md（拼音前缀桶，如 pages/li/刘备.md）
    - 自动调用 record_revision.py 记录初版修订
"""
from __future__ import annotations
import argparse, subprocess, sys
from pathlib import Path

ROOT   = Path(__file__).resolve().parents[2]
PAGES  = ROOT / "wiki/public/pages"
REC    = ROOT / "wiki/scripts/record_revision.py"
REG    = ROOT / "wiki/scripts/build_registry.py"

sys.path.insert(0, str(ROOT / "wiki/scripts"))
from page_bucket import page_bucket  # noqa: E402


def _rebuild_registry() -> None:
    r = subprocess.run(
        [sys.executable, str(REG), str(PAGES),
         "--out", str(ROOT / "wiki/public/pages.json"),
         "--out-lite", str(ROOT / "wiki/public/pages.lite.json")],
        capture_output=True, text=True, cwd=ROOT
    )
    if r.returncode == 0:
        print("✓ pages.json + pages.lite.json 已更新")
    else:
        print(f"⚠ pages.json 更新失败: {r.stderr.strip()}", file=sys.stderr)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("slug", help="页面 slug（不含 .md）")
    ap.add_argument("content_file", help="内容文件路径，或 - 表示 stdin")
    ap.add_argument("--summary", default="")
    ap.add_argument("--author", default="butler")
    args = ap.parse_args()

    bucket = page_bucket(args.slug)
    target = PAGES / bucket / f"{args.slug}.md"
    if target.exists():
        print(f"✗ 页面已存在: {target}（请用 edit_page.py）", file=sys.stderr)
        sys.exit(1)
    target.parent.mkdir(parents=True, exist_ok=True)

    if args.content_file == "-":
        content = sys.stdin.read()
    else:
        src = Path(args.content_file)
        if not src.exists():
            print(f"✗ 内容文件不存在: {src}", file=sys.stderr)
            sys.exit(1)
        content = src.read_text(encoding="utf-8")

    target.write_text(content, encoding="utf-8")
    print(f"✓ 写入 {target}")

    r = subprocess.run(
        [sys.executable, str(REC), args.slug,
         "--summary", args.summary or f"新增: {args.slug}",
         "--author", args.author],
        capture_output=True, text=True, cwd=ROOT
    )
    print(r.stdout, end="")
    if r.returncode != 0:
        print(r.stderr, file=sys.stderr)
        sys.exit(r.returncode)

    _rebuild_registry()


if __name__ == "__main__":
    main()
