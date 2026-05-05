#!/usr/bin/env python3
"""把 queue.md / housekeeping_queue.md 中的 [x] 已完成条目归档到 done.md。

Dream Round 时调用：
    python3 wiki/scripts/butler/cleanup_queue.py

策略
----
- 扫描 queue.md 和 housekeeping_queue.md 中所有以 `- [x]` 开头的行
- 追加到 wiki/logs/butler/queue_done.md（带时间戳标注归档时间）
- 原文件保留所有 [ ] / [~] 行（待处理）及结构性行（# 标题、空行、注释）
- 如果没有 [x] 条目，无操作

用法
----
    python3 wiki/scripts/butler/cleanup_queue.py [--dry-run]
    --dry-run  只显示会移动什么，不写文件
"""
from __future__ import annotations

import argparse
import datetime
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[3]
LOGS_DIR = REPO_ROOT / "wiki/logs/butler"

QUEUE_FILES = [
    (LOGS_DIR / "queue.md", LOGS_DIR / "queue_done.md"),
    (LOGS_DIR / "housekeeping_queue.md", LOGS_DIR / "housekeeping_done.md"),
]


def _is_done(line: str) -> bool:
    stripped = line.strip()
    return stripped.startswith("- [x]")


def _is_structural(line: str) -> bool:
    """保留：标题行、空行、注释行、非列表行。"""
    stripped = line.strip()
    return (
        not stripped.startswith("- [")   # 不是任务行 → 保留
        or stripped.startswith("- [ ]")  # 未完成 → 保留
        or stripped.startswith("- [~]")  # 进行中 → 保留
    )


def process(src: Path, done: Path, dry_run: bool) -> int:
    if not src.exists():
        return 0

    lines = src.read_text(encoding="utf-8").splitlines(keepends=True)
    completed = [l for l in lines if _is_done(l)]
    if not completed:
        return 0

    if dry_run:
        print(f"[dry-run] {src.name}: 发现 {len(completed)} 条 [x] 条目")
        for l in completed:
            print(f"  {l.rstrip()}")
        return len(completed)

    # 归档到 done.md
    stamp = datetime.date.today().isoformat()
    header = f"\n## 归档于 {stamp}（共 {len(completed)} 条）\n\n"
    with open(done, "a", encoding="utf-8") as f:
        f.write(header)
        f.writelines(completed)

    # 重写原文件：去掉 [x] 行，保留结构 + 未完成任务
    kept = [l for l in lines if _is_structural(l)]
    # 去掉连续多余空行（最多保留 1 个空行）
    cleaned: list[str] = []
    prev_blank = False
    for l in kept:
        blank = l.strip() == ""
        if blank and prev_blank:
            continue
        cleaned.append(l)
        prev_blank = blank

    src.write_text("".join(cleaned), encoding="utf-8")
    print(f"[cleanup] {src.name}: 归档 {len(completed)} 条 → {done.name}")
    return len(completed)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--dry-run", action="store_true", help="只显示，不写文件")
    args = ap.parse_args()

    total = 0
    for src, done in QUEUE_FILES:
        total += process(src, done, args.dry_run)

    if total == 0:
        print("[cleanup] 无已完成条目，无需归档")
    elif not args.dry_run:
        print(f"[cleanup] 合计归档 {total} 条")


if __name__ == "__main__":
    main()
