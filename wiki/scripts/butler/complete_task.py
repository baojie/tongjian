#!/usr/bin/env python3
"""将 queue.md 中已领取的任务标记为完成（[~] → [x]）或放回（[~] → [ ]）。

用法：
    # 完成
    python3 wiki/scripts/butler/complete_task.py --page 希恩斯 --date 2026-04-27

    # 失败/放回（供其他实例重试）
    python3 wiki/scripts/butler/complete_task.py --page 希恩斯 --release
"""
from __future__ import annotations
import argparse, fcntl, re, sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from lock_manager import LockManager, LockError

QUEUE = Path(__file__).resolve().parents[3] / "wiki/logs/butler/queue.md"

RE_INPROG = re.compile(r"^(\s*- \[~\] )(P[123] \S+ \| )([^|]+)( \| )\[([^\]]+)\] (.*)$")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--page", required=True, help="页面 slug")
    ap.add_argument("--round", type=int, default=None, help="本轮轮号（用于锁检查）")
    ap.add_argument("--date", default="", help="完成日期（如 2026-04-27）")
    ap.add_argument("--release", action="store_true", help="放回队列而非标完成")
    ap.add_argument("--skip-lock-check", action="store_true",
                    help="跳过锁检查（仅限不持有轮次锁的内务清理操作）")
    args = ap.parse_args()

    # ── 锁检查：确认本轮持有有效轮次锁 ──────────────────────────────────────
    if not args.skip_lock_check and args.round is not None:
        try:
            LockManager().assert_owner(args.round)
        except LockError as e:
            print(f"[complete_task] 锁检查失败，拒绝修改队列：{e}", file=sys.stderr)
            return 1

    page = args.page.strip()
    found = False

    with open(QUEUE, "r+", encoding="utf-8") as f:
        fcntl.flock(f, fcntl.LOCK_EX)
        lines = f.readlines()

        for i, line in enumerate(lines):
            m = RE_INPROG.match(line)
            if not m:
                continue
            # m.group(3) is page name part
            if m.group(3).strip() != page:
                continue

            priority_type = m.group(2)  # e.g. "P1 create | "
            note = m.group(6)

            if args.release:
                lines[i] = f"- [ ] {priority_type}{page} | {note}\n"
                action = "released"
            else:
                date_tag = f"✓ {args.date}" if args.date else "✓"
                lines[i] = f"- [x] {priority_type}{page} | {date_tag} {note}\n"
                action = "completed"

            found = True
            break

        if found:
            f.seek(0)
            f.writelines(lines)
            f.truncate()

    if found:
        print(f"[queue] {page} → {action}")
    else:
        print(f"[queue] 未找到 [~] 状态的任务：{page}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
