#!/usr/bin/env python3
"""edit_page.py — 编辑 wiki 页面并自动记录修订历史。

用法:
    python3 wiki/scripts/edit_page.py <slug> <content_file> \
        [--summary "更新: ..."] [--author butler]

    # 从 stdin 读取:
    cat new.md | python3 wiki/scripts/edit_page.py <slug> - --summary "..."

    # 允许修改原文引用节（去重/纠错专用）:
    python3 wiki/scripts/edit_page.py <slug> <file> --allow-citation-edit

铁律（不可绕过，除非显式传标志）:
    - 旧版有 ## 原文引用 节，新版必须保留 → 拒绝（退出码 2）
    - 旧版有 frontmatter（--- 开头），新版没有 → 拒绝（退出码 3）
    - 新版 size < 旧版 size × 0.6 → 拒绝（退出码 4）
    - 退出码 2 可加 --allow-citation-edit 跳过（仅限去重/纠错）
    - 退出码 3/4 可加 --allow-shrink 跳过（仅限 redirect/merge）
"""
from __future__ import annotations
import argparse, re, subprocess, sys
from pathlib import Path

ROOT   = Path(__file__).resolve().parents[2]
PAGES  = ROOT / "wiki/public/pages"
REC    = ROOT / "wiki/scripts/record_revision.py"
REG    = ROOT / "wiki/scripts/build_registry.py"

sys.path.insert(0, str(ROOT / "wiki/scripts"))
from page_bucket import resolve_page_file  # noqa: E402

CITATION_SECTION = "## 原文引用"


def _has_citation(text: str) -> bool:
    return any(line.strip() == CITATION_SECTION for line in text.splitlines())


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
    ap.add_argument("--allow-citation-edit", action="store_true",
                    help="允许修改/删除原文引用节（去重/纠错专用）")
    ap.add_argument("--allow-shrink", action="store_true",
                    help="允许 frontmatter 丢失或内容大幅缩减（redirect/merge 专用）")
    ap.add_argument("--enrich", action="store_true",
                    help="追加模式：检查旧版 ## 节全部保留，禁止替换已有节")
    args = ap.parse_args()

    target = resolve_page_file(PAGES, args.slug)
    if not target:
        print(f"✗ 页面不存在: {args.slug}（请用 add_page.py）", file=sys.stderr)
        sys.exit(1)

    old_content = target.read_text(encoding="utf-8")

    if args.content_file == "-":
        new_content = sys.stdin.read()
    else:
        src = Path(args.content_file)
        if not src.exists():
            print(f"✗ 内容文件不存在: {src}", file=sys.stderr)
            sys.exit(1)
        new_content = src.read_text(encoding="utf-8")

    # 铁律0：原文引用节不得被非授权操作删除
    if not args.allow_citation_edit and _has_citation(old_content) and not _has_citation(new_content):
        print(
            f'⛔ 禁止写入：{args.slug} 旧版含 "{CITATION_SECTION}" 节，新版缺失。\n'
            f"   若确为去重/纠错操作，请加 --allow-citation-edit 标志。",
            file=sys.stderr,
        )
        sys.exit(2)

    # 铁律1：frontmatter 不得被非授权操作删除
    if not args.allow_shrink and old_content.lstrip().startswith("---") and not new_content.lstrip().startswith("---"):
        print(
            f"⛔ 禁止写入：{args.slug} 旧版含 frontmatter，新版缺失。\n"
            f"   若确为 redirect/merge 操作，请加 --allow-shrink 标志。",
            file=sys.stderr,
        )
        sys.exit(3)

    # 铁律2（追加模式）：旧版 ## 节必须全部保留（禁止替换）
    if args.enrich:
        old_sections = set(re.findall(r'^## (.+)$', old_content, re.MULTILINE))
        new_sections = set(re.findall(r'^## (.+)$', new_content, re.MULTILINE))
        lost = old_sections - new_sections - {'参见', '相关词条', '简介'}
        if lost:
            print(
                f"⛔ 禁止写入（--enrich 模式）：{args.slug} 以下旧节丢失：{lost}\n"
                f"   Append-Only 原则：只能追加新节，不能删除或替换已有节。",
                file=sys.stderr,
            )
            sys.exit(5)

    # 铁律3：禁止内容大幅缩减（新版 < 旧版 60%）
    old_size = len(old_content.encode("utf-8"))
    new_size  = len(new_content.encode("utf-8"))
    if not args.allow_shrink and old_size > 400 and new_size < old_size * 0.6:
        print(
            f"⛔ 禁止写入：{args.slug} 新版 {new_size}B 不足旧版 {old_size}B 的 60%。\n"
            f"   若确为 redirect/merge 操作，请加 --allow-shrink 标志。",
            file=sys.stderr,
        )
        sys.exit(4)

    target.write_text(new_content, encoding="utf-8")
    print(f"✓ 更新 {target}")

    r = subprocess.run(
        [sys.executable, str(REC), args.slug,
         "--summary", args.summary or f"编辑: {args.slug}",
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
