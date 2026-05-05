#!/usr/bin/env python3
"""record_revision.py — 为 wiki/public/pages/<page>.md 写入一条修订记录。

产出:
  1. wiki/public/history/<page>.jsonl     (per-page 索引，JSONL 格式，flock 保护)
  2. wiki/public/recent.lite.jsonl        (轻量全局修订日志，滚动窗口，不含 diff)
  3. wiki/public/recent.diff.jsonl        (仅 page + rev_id + diff，滚动窗口)
  4. wiki/logs/recent/recent.lite.{N}.jsonl / .diff.{N}.jsonl  (归档)

rev_id 格式: YYYYMMDD-HHMMSS-<sha256[:6]>  (UTC)
"""
from __future__ import annotations
import argparse, difflib, fcntl, hashlib, json, os, sys
from datetime import datetime, timezone
from pathlib import Path

ROOT    = Path(__file__).resolve().parents[2]
PUBLIC  = ROOT / "wiki/public"
PAGES   = PUBLIC / "pages"
HIST    = PUBLIC / "history"
RECENT_LITE = PUBLIC / "recent.lite.jsonl"
RECENT_DIFF = PUBLIC / "recent.diff.jsonl"
LOG_DIR = ROOT / "wiki/logs/recent"
LOCK    = LOG_DIR / "recent.lock"

WINDOW_SIZE    = 1000   # 每条 recent 文件最多保留行数
ARCHIVE_BATCH  = 500    # 超出后一次归档最旧的条数


def _diff(old: str, new: str, context: int = 2) -> list[list[str]]:
    """行级 unified diff，返回 [["+"/"-"/" ", line], ...] 去掉 @@/---/+++ 头。"""
    chunks = []
    for line in difflib.unified_diff(
        old.splitlines(keepends=True),
        new.splitlines(keepends=True),
        n=context,
    ):
        if line.startswith(("--- ", "+++ ", "@@ ")):
            continue
        op = line[0] if line else " "
        text = line[1:].rstrip("\n") if line else ""
        chunks.append([op, text])
    return chunks


def _iso(dt: datetime) -> str:
    s = dt.strftime("%Y-%m-%dT%H:%M:%S%z")
    return s[:-2] + ":" + s[-2:] if not s.endswith("Z") else s


def _read_jsonl(path: Path) -> list[dict]:
    if not path.exists():
        return []
    entries = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line:
            try:
                entries.append(json.loads(line))
            except json.JSONDecodeError:
                pass
    return entries


def _rotate_all(lite_entries: list[dict], diff_entries: list[dict]
                ) -> tuple[list[dict], list[dict]]:
    """超出窗口大小则归档最旧的一批，返回修剪后的列表。"""
    if len(lite_entries) <= WINDOW_SIZE:
        return lite_entries, diff_entries

    batch_lite = lite_entries[:ARCHIVE_BATCH]
    batch_diff = diff_entries[:ARCHIVE_BATCH]
    lite_entries = lite_entries[ARCHIVE_BATCH:]
    diff_entries = diff_entries[ARCHIVE_BATCH:]

    LOG_DIR.mkdir(parents=True, exist_ok=True)
    nums = [int(p.stem.rsplit(".", 1)[1])
            for p in LOG_DIR.glob("recent.*.jsonl")
            if p.stem.rsplit(".", 1)[1].isdigit()]
    n = max(nums) + 1 if nums else 1

    for filename, batch in [(f"recent.lite.{n}.jsonl", batch_lite),
                             (f"recent.diff.{n}.jsonl", batch_diff)]:
        (LOG_DIR / filename).write_text(
            "\n".join(json.dumps(e, ensure_ascii=False) for e in batch) + "\n",
            encoding="utf-8")
    print(f"  [archive] {len(batch_lite)} entries → logs/recent/recent.*.{n}.jsonl")
    return lite_entries, diff_entries


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("page", help="slug（不含 .md）")
    ap.add_argument("--summary", default="")
    ap.add_argument("--author", default="butler")
    ap.add_argument("--action", default="edit", choices=["edit", "delete"])
    ap.add_argument("--timestamp", default=None, help="ISO 时间（默认现在）")
    args = ap.parse_args()

    page = args.page
    src  = PAGES / f"{page}.md"
    if not src.exists():
        print(f"✗ {src} 不存在", file=sys.stderr)
        return 1

    content = src.read_text(encoding="utf-8")
    sha     = hashlib.sha256(content.encode("utf-8")).hexdigest()

    if args.timestamp:
        now = datetime.fromisoformat(args.timestamp)
        if now.tzinfo is None:
            now = now.replace(tzinfo=timezone.utc)
        now = now.astimezone(timezone.utc)
    else:
        now = datetime.now(timezone.utc)

    rev_id = f"{now.strftime('%Y%m%d-%H%M%S')}-{sha[:6]}"
    ts_iso = _iso(now)

    # ── per-page history（flock 排他锁，防并发覆写）────────────────────────────
    HIST.mkdir(exist_ok=True)
    page_jsonl = HIST / f"{page}.jsonl"

    with page_jsonl.open("a+", encoding="utf-8") as fh:
        fcntl.flock(fh, fcntl.LOCK_EX)
        fh.seek(0)
        lines = [l for l in fh.read().splitlines() if l.strip()]
        entries = []
        for l in lines:
            try:
                entries.append(json.loads(l))
            except json.JSONDecodeError:
                pass

        if entries and entries[-1].get("content_hash") == f"sha256:{sha}":
            print(f"= {page} 内容与 latest 相同，跳过")
            return 0

        last = entries[-1] if entries else None
        parent_content = last["content"] if last else ""
        size_before    = last["size"] if last else 0
        parent_rev     = last["rev_id"] if last else None

        size_after  = len(content.encode("utf-8"))
        diff_chunks = _diff(parent_content, content)
        entry = {
            "rev_id":       rev_id,
            "timestamp":    ts_iso,
            "author":       args.author,
            "summary":      args.summary or f"{args.author} {args.action}",
            "parent_rev":   parent_rev,
            "content_hash": f"sha256:{sha}",
            "size_before":  size_before,
            "size":         size_after,
            "content":      content,
            "diff":         diff_chunks,
        }
        if args.action == "delete":
            entry["action"] = "delete"

        fh.seek(0, 2)
        fh.write(json.dumps(entry, ensure_ascii=False) + "\n")

    # ── recent.lite.jsonl + recent.diff.jsonl（滚动窗口，flock 保护）─────────
    diff_add  = sum(1 for d in diff_chunks if d[0] == "+")
    diff_del  = sum(1 for d in diff_chunks if d[0] == "-")

    recent_lite_entry = {
        "page": page,
        **{k: v for k, v in entry.items() if k not in ("content", "diff")},
        "diff_add": diff_add,
        "diff_del": diff_del,
    }
    recent_diff_entry = {"page": page, "rev_id": rev_id, "diff": diff_chunks}

    LOG_DIR.mkdir(parents=True, exist_ok=True)
    with open(LOCK, "w") as lk:
        fcntl.flock(lk, fcntl.LOCK_EX)

        lite_entries = _read_jsonl(RECENT_LITE)
        diff_entries = _read_jsonl(RECENT_DIFF)
        lite_entries.append(recent_lite_entry)
        diff_entries.append(recent_diff_entry)

        lite_entries, diff_entries = _rotate_all(lite_entries, diff_entries)

        RECENT_LITE.write_text(
            "\n".join(json.dumps(e, ensure_ascii=False) for e in lite_entries) + "\n",
            encoding="utf-8")
        RECENT_DIFF.write_text(
            "\n".join(json.dumps(e, ensure_ascii=False) for e in diff_entries) + "\n",
            encoding="utf-8")

    delta = size_after - size_before
    print(f"✓ {page} rev={rev_id} size={size_before}→{size_after}({'+' if delta>=0 else ''}{delta}) author={args.author}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
