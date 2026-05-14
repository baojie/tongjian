#!/usr/bin/env python3
"""record_revision.py — 为 wiki/public/pages/<page>.md 写入一条修订记录。

写入 v1 schema（周期快照 + 增量 patch）:
  {"v":1,"t":"snap", "id":"...","ts":"...","au":"...","su":"...","sz":N,"ch":"sha256:...","content":"全文..."}
  {"v":1,"t":"patch","id":"...","ts":"...","au":"...","su":"...","sz":N,"szb":N,"ch":"sha256:...","parent":"...","diff":"unified text"}

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

sys.path.insert(0, str(ROOT / "wiki/scripts"))
from page_bucket import page_bucket, resolve_page_file  # noqa: E402

WINDOW_SIZE    = 1000
ARCHIVE_BATCH  = 500
HIST_MAX_BYTES     = 20 * 1024 * 1024
HIST_ARCHIVE_BATCH = 50
SNAP_INTERVAL      = 25  # 每 25 个 patch 插入一个 snap


# ── diff / patch helpers ──────────────────────────────────────────────

def _diff_text(old: str, new: str) -> str:
    """全量 unified diff 文本，每行以 ' ', '+', '-' 开头。"""
    old = old.rstrip('\n') if old else old
    new = new.rstrip('\n') if new else new
    old_lines = old.splitlines(keepends=True) if old else []
    new_lines = new.splitlines(keepends=True) if new else []
    context = max(len(old_lines), len(new_lines)) + 1
    lines = []
    for line in difflib.unified_diff(old_lines, new_lines, n=context):
        if line.startswith(("--- ", "+++ ", "@@ ")):
            continue
        op = line[0] if line else " "
        text = line[1:].rstrip("\n") if line else ""
        lines.append(f"{op}{text}")
    return "\n".join(lines)


def _apply_patch(content: str, diff_text: str) -> str:
    """将 unified diff 文本应用到 content，返回新 content。"""
    if not diff_text:
        return content
    source = content.splitlines() if content else []
    result = []
    si = 0
    for line in diff_text.split("\n"):
        if not line:
            result.append(source[si] if si < len(source) else "")
            si += 1
            continue
        op, text = line[0], line[1:]
        if op == " ":
            result.append(source[si] if si < len(source) else text)
            si += 1
        elif op == "-":
            si += 1
        elif op == "+":
            result.append(text)
    while si < len(source):
        result.append(source[si])
        si += 1
    out = "\n".join(result)
    if content and content.endswith("\n") and not out.endswith("\n"):
        out += "\n"
    return out


def _reconstruct_content(entries: list[dict], target_idx: int | None = None
                         ) -> str:
    """从 entries 链中重建 target_idx 处的 content。

    从最近的 snap 开始，向前 apply patch 直到 target_idx。
    若 target_idx 为 None，重建到最后一条。
    """
    content = None
    for i, e in enumerate(entries):
        if e.get("t") == "snap":
            content = e.get("content", "")
        else:
            content = _apply_patch(content or "", e.get("diff", ""))
        if target_idx is not None and i >= target_idx:
            break
    return content or ""


def _patches_since_snap(entries: list[dict]) -> int:
    """从末尾往前数，距离最近 snap 的 patch 数。"""
    n = 0
    for e in reversed(entries):
        if e.get("t") == "snap":
            break
        n += 1
    return n


# ── helpers ───────────────────────────────────────────────────────────

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


def _rotate_history(page: str, bucket: str, entries: list[dict], file_size: int
                    ) -> tuple[list[dict], bool]:
    """Size-based rotation: archive oldest entries when file exceeds HIST_MAX_BYTES.

    旋转边界对齐到 snap，确保剩余 entries 以 snap 开头。
    """
    if not entries or file_size <= HIST_MAX_BYTES:
        return entries, False

    avg_bytes  = file_size / len(entries)
    batch_size = max(1, min(HIST_ARCHIVE_BATCH, int(HIST_MAX_BYTES / avg_bytes)))
    did_rotate = False
    hist_dir = HIST / bucket

    while entries and len(entries) * avg_bytes > HIST_MAX_BYTES:
        # 找到前 batch_size 个 entry 中最后的 snap，以它为切分边界
        end = min(batch_size, len(entries))
        snap_at = -1
        for i in range(end):
            if entries[i].get("t") == "snap":
                snap_at = i
        if snap_at >= 0:
            batch = entries[:snap_at + 1]  # 包含这个 snap
        else:
            batch = entries[:end]

        entries = entries[len(batch):]
        nums = [int(p.stem.rsplit(".", 1)[1])
                for p in hist_dir.glob(f"{page}.*.jsonl")
                if p.stem.rsplit(".", 1)[1].isdigit()]
        n = max(nums) + 1 if nums else 1
        (hist_dir / f"{page}.{n}.jsonl").write_text(
            "\n".join(json.dumps(e, ensure_ascii=False) for e in batch) + "\n",
            encoding="utf-8")
        print(f"  [hist-archive] {len(batch)} entries → history/{bucket}/{page}.{n}.jsonl")
        did_rotate = True

    return entries, did_rotate


def _rotate_all(lite_entries: list[dict], diff_entries: list[dict]
                ) -> tuple[list[dict], list[dict]]:
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


# ── main ──────────────────────────────────────────────────────────────

def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("page", help="slug（不含 .md）")
    ap.add_argument("--summary", default="")
    ap.add_argument("--author", default="butler")
    ap.add_argument("--action", default="edit", choices=["edit", "delete"])
    ap.add_argument("--timestamp", default=None, help="ISO 时间（默认现在）")
    args = ap.parse_args()

    page = args.page
    bucket = page_bucket(page)
    src  = resolve_page_file(PAGES, page)
    if not src:
        print(f"✗ pages/{bucket}/{page}.md 不存在", file=sys.stderr)
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

    # ── per-page history（flock 排他锁）───────────────────────────────
    hist_dir = HIST / bucket
    hist_dir.mkdir(parents=True, exist_ok=True)
    page_jsonl = hist_dir / f"{page}.jsonl"

    file_size = page_jsonl.stat().st_size if page_jsonl.exists() else 0
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

        # dedup: 比较 content hash
        if entries and entries[-1].get("ch") == f"sha256:{sha}":
            print(f"= {page} 内容与 latest 相同，跳过")
            return 0

        entries, did_rotate = _rotate_history(page, bucket, entries, file_size)

        # 获取上一版的 content（用于 diff 计算）
        last = entries[-1] if entries else None
        if last and last.get("t") == "snap":
            parent_content = last.get("content", "")
        elif last:
            parent_content = _reconstruct_content(entries, target_idx=len(entries) - 1)
        else:
            parent_content = ""

        size_before = last["sz"] if last else 0
        parent_rev  = last["id"] if last else None
        size_after  = len(content.encode("utf-8"))
        diff_text   = _diff_text(parent_content, content)

        # 判断是 snap 还是 patch
        patches_since = _patches_since_snap(entries)
        is_snap = (last is None) or (patches_since >= SNAP_INTERVAL)

        entry = {"v": 1}
        if is_snap:
            entry["t"] = "snap"
            entry["content"] = content
        else:
            entry["t"] = "patch"
            entry["szb"] = size_before
            entry["parent"] = parent_rev
            entry["diff"] = diff_text

        entry.update({
            "id": rev_id,
            "ts": ts_iso,
            "au": args.author,
            "su": args.summary or f"{args.author} {args.action}",
            "sz": size_after,
            "ch": f"sha256:{sha}",
        })
        if args.action == "delete":
            entry["action"] = "delete"

        if did_rotate:
            fh.seek(0)
            fh.truncate()
            for e in entries:
                fh.write(json.dumps(e, ensure_ascii=False) + "\n")
        else:
            fh.seek(0, 2)
        fh.write(json.dumps(entry, ensure_ascii=False) + "\n")

    # ── recent.lite.jsonl + recent.diff.jsonl ──────────────────────
    diff_lines = diff_text.split("\n") if diff_text else []
    diff_add   = sum(1 for l in diff_lines if l.startswith("+"))
    diff_del   = sum(1 for l in diff_lines if l.startswith("-"))

    recent_lite_entry = {
        "page": page,
        **{k: v for k, v in entry.items() if k not in ("content", "diff")},
        "diff_add": diff_add,
        "diff_del": diff_del,
    }
    recent_diff_entry = {"page": page, "rev_id": rev_id, "diff": diff_text}

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
