#!/usr/bin/env python3
"""释放轮次锁：删除 round_<N>.lock，表示本轮已完成。

所有锁操作通过 lock_manager.LockManager 完成，本脚本仅是 CLI 包装。

用法：
    python3 wiki/scripts/butler/release_round.py <round_number>
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from lock_manager import LockManager


def main() -> int:
    if len(sys.argv) < 2:
        print("Usage: release_round.py <round_number>", file=sys.stderr)
        return 1
    try:
        round_num = int(sys.argv[1])
    except ValueError:
        print(f"Error: round_number must be integer, got {sys.argv[1]!r}", file=sys.stderr)
        return 1

    LockManager().release(round_num)
    print(f"[released] round_{round_num}.lock")
    return 0


if __name__ == "__main__":
    sys.exit(main())
