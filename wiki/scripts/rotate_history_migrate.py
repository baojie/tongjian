#!/usr/bin/env python3
"""rotate_history_migrate.py — 一次性将超过阈值的 history 文件做 size-based rotation.

用法:
  python3 wiki/scripts/rotate_history_migrate.py          # dry-run（只报告，不修改）
  python3 wiki/scripts/rotate_history_migrate.py --apply  # 实际执行
"""
from __future__ import annotations
import argparse, json, re, sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
from page_bucket import page_bucket  # noqa: E402

ROOT               = Path(__file__).resolve().parents[2]
PUBLIC             = ROOT / "wiki/public"
HIST               = PUBLIC / "history"
HIST_MAX_BYTES     = 20 * 1024 * 1024
HIST_ARCHIVE_BATCH = 50

_ARCHIVE_RE = re.compile(r'\.\d+$')


def is_main_file(p: Path) -> bool:
    return not _ARCHIVE_RE.search(p.stem)


def rotate_file(page: str, path: Path, bucket: str, apply: bool) -> None:
    raw = path.read_text(encoding="utf-8")
    entries: list[dict] = []
    for line in raw.splitlines():
        line = line.strip()
        if line:
            try:
                entries.append(json.loads(line))
            except json.JSONDecodeError:
                pass

    # Compute actual per-entry serialized sizes
    serialized = [json.dumps(e, ensure_ascii=False).encode() for e in entries]
    total_size  = sum(len(s) + 1 for s in serialized)
    file_size   = path.stat().st_size

    avg_bytes = file_size / max(len(entries), 1)
    batch_size = max(1, min(HIST_ARCHIVE_BATCH, int(HIST_MAX_BYTES / avg_bytes)))

    print(f"\n{page} [{bucket}/]:")
    print(f"  当前: {file_size/1024/1024:.1f} MB, {len(entries)} 条"
          f", 均 {avg_bytes/1024:.0f} KB/条, batch_size={batch_size}")

    archived_total = 0
    hist_dir = HIST / bucket
    archive_n = max(
        [int(p.stem.rsplit(".", 1)[1]) for p in hist_dir.glob(f"{page}.*.jsonl")
         if p.stem.rsplit(".", 1)[1].isdigit()],
        default=0
    )

    remaining_size = total_size
    while serialized and remaining_size > HIST_MAX_BYTES:
        # Build batch by actual size
        batch_ser: list[bytes] = []
        batch_bytes = 0
        while serialized and len(batch_ser) < batch_size:
            s = serialized[0]
            if batch_ser and batch_bytes + len(s) + 1 > HIST_MAX_BYTES:
                break
            batch_ser.append(serialized.pop(0))
            batch_bytes += len(s) + 1

        if not batch_ser:
            # single entry exceeds limit — archive anyway
            batch_ser.append(serialized.pop(0))
            batch_bytes = len(batch_ser[0]) + 1

        remaining_size -= batch_bytes
        archive_n += 1
        archive = hist_dir / f"{page}.{archive_n}.jsonl"

        if apply:
            archive.write_bytes(b"\n".join(batch_ser) + b"\n")
            print(f"  [归档 {archive_n}] {len(batch_ser)} 条 → {bucket}/{archive.name}"
                  f" ({archive.stat().st_size/1024/1024:.1f} MB)")
        else:
            print(f"  [dry {archive_n}] {len(batch_ser)} 条 → {bucket}/{archive.name}"
                  f" (~{batch_bytes/1024/1024:.1f} MB)")
        archived_total += len(batch_ser)

    if apply and archived_total > 0:
        remaining_entries = [json.loads(s) for s in serialized]
        path.write_text(
            "\n".join(json.dumps(e, ensure_ascii=False) for e in remaining_entries) + "\n",
            encoding="utf-8")
        new_size = path.stat().st_size
        print(f"  [主文件] → {new_size/1024/1024:.1f} MB, {len(remaining_entries)} 条")
    elif archived_total > 0:
        remaining_size_est = sum(len(s) + 1 for s in serialized)
        print(f"  [dry 主文件] → ~{remaining_size_est/1024/1024:.1f} MB, {len(serialized)} 条")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true", help="实际执行（默认 dry-run）")
    args = ap.parse_args()

    oversized = sorted(
        [(p, p.stat().st_size) for p in HIST.rglob("*.jsonl")
         if is_main_file(p) and p.stat().st_size > HIST_MAX_BYTES],
        key=lambda x: -x[1]
    )

    if not oversized:
        print("没有超过阈值的 history 文件。")
        return 0

    print(f"{'[DRY-RUN] ' if not args.apply else ''}找到 {len(oversized)} 个超过 20 MB 的主文件：")
    for p, sz in oversized:
        print(f"  {p.name}: {sz/1024/1024:.1f} MB")

    for p, _ in oversized:
        bucket = page_bucket(p.stem)
        rotate_file(p.stem, p, bucket, apply=args.apply)

    if not args.apply:
        print("\n（以上为 dry-run，加 --apply 参数实际执行）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
