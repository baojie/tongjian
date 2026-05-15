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

sys.path.insert(0, str(ROOT / "wiki/scripts"))
from page_bucket import page_bucket, resolve_page_file, hash_bucket  # noqa: E402

WINDOW_SIZE    = 1000   # 每条 recent 文件最多保留行数
ARCHIVE_BATCH  = 500    # 超出后一次归档最旧的条数

HIST_MAX_BYTES     = 20 * 1024 * 1024   # history 文件超过 20 MB 触发归档
HIST_ARCHIVE_BATCH = 50                  # 每次归档最旧的 50 条

LINE_INDEX_DIR = PUBLIC / "line_index"
MIN_HASH_LEN   = 6
SNAP_INTERVAL  = 26

BASE62 = '0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz'


def _base62_id(sha256_hex: str) -> str:
    n = int(sha256_hex, 16)
    chars = []
    while n:
        chars.append(BASE62[n % 62])
        n //= 62
    return ''.join(reversed(chars))[:6]


def _hex_to_base62(hex_str: str) -> str:
    n = int(hex_str, 16)
    chars = []
    while n:
        chars.append(BASE62[n % 62])
        n //= 62
    return ''.join(reversed(chars))


def _load_all_registries() -> dict[str, dict[str, str]]:
    registries: dict[str, dict[str, str]] = {}
    for f in sorted(LINE_INDEX_DIR.glob("*.json")):
        registries[f.stem] = json.loads(f.read_text(encoding="utf-8"))
    return registries


def _resolve_line(h: str, registries: dict[str, dict[str, str]]) -> str:
    return registries.get(hash_bucket(h), {}).get(h, "")


def _line_hash(line: str, registries: dict[str, dict[str, str]]) -> str:
    full = hashlib.sha256(line.encode("utf-8")).hexdigest()
    b62 = _hex_to_base62(full)
    bucket = hash_bucket(b62)
    registry = registries.setdefault(bucket, {})
    for length in range(MIN_HASH_LEN, 17):
        h = b62[:length]
        if h not in registry or registry[h] == line:
            registry[h] = line  # 注册新行
            return h
    raise RuntimeError(f"16位仍有碰撞: {line[:60]}")


def _compute_delta(parent_ln: list[str], current_ln: list[str]) -> list[list]:
    """LCS diff 生成逆序编辑操作。"""
    sm = difflib.SequenceMatcher(None, parent_ln, current_ln)
    dl = []
    for tag, i1, i2, j1, j2 in reversed(sm.get_opcodes()):
        if tag == "equal":
            continue
        elif tag in ("delete", "replace"):
            for k in reversed(range(i1, i2)):
                dl.append(["del", k])
        if tag in ("insert", "replace"):
            for k in reversed(range(j1, j2)):
                dl.append(["ins", i1, current_ln[k]])
    return dl


def _apply_delta(ln: list[str], dl: list[list]) -> list[str]:
    result = list(ln)
    for op in dl:
        if op[0] == "del":
            del result[op[1]]
        elif op[0] == "ins":
            result.insert(op[1], op[2])
    return result


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


def _rotate_history(page: str, bucket: str, entries: list[dict], file_size: int
                    ) -> tuple[list[dict], bool]:
    """Size-based rotation: archive oldest entries when file exceeds HIST_MAX_BYTES.
    Batch size is derived from avg entry size so each archive file stays under the limit."""
    if not entries or file_size <= HIST_MAX_BYTES:
        return entries, False

    avg_bytes  = file_size / len(entries)
    # How many entries fit in one archive file (min 1, max HIST_ARCHIVE_BATCH)
    batch_size = max(1, min(HIST_ARCHIVE_BATCH, int(HIST_MAX_BYTES / avg_bytes)))
    did_rotate = False
    hist_dir = HIST / bucket

    while entries and len(entries) * avg_bytes > HIST_MAX_BYTES:
        batch   = entries[:batch_size]
        entries = entries[batch_size:]
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

    rev_id = _base62_id(sha)
    ts_iso = _iso(now)

    # ── per-page history（flock 排他锁，防并发覆写）────────────────────────────
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

        # ── 内容去重（通过 base62 id 比较）─────────────────────────────────
        if entries and entries[-1].get("id") == rev_id:
            print(f"= {page} 内容与 latest 相同，跳过")
            return 0

        entries, did_rotate = _rotate_history(page, bucket, entries, file_size)

        is_v2 = entries and entries[0].get("v") == 2
        size_after = len(content.encode("utf-8"))
        content_lines = content.splitlines()

        if is_v2:
            # ── v2 写入 ────────────────────────────────────────────────────
            registries = _load_all_registries()

            current_ln_list = [_line_hash(l, registries) for l in content_lines]
            current_ln_str = ' '.join(current_ln_list)
            ts_int = int(now.timestamp())
            su_hash = _line_hash(
                args.summary or f"{args.author} {args.action}", registries)

            last = entries[-1] if entries else None
            since_snap = 0
            for e in reversed(entries):
                if e["t"] == "snap":
                    break
                since_snap += 1
            is_snap = (not entries) or (since_snap >= SNAP_INTERVAL)

            if is_snap:
                entry = {
                    "v": 2, "t": "snap", "id": rev_id, "ts": ts_int,
                    "au": args.author,
                    "su": su_hash,
                    "sz": size_after,
                    "lc": len(current_ln_list),
                    "ln": current_ln_str,
                }
                parent_content = ""
            else:
                # 从 snap 链重建 parent 的 ln 数组
                snap_idx = len(entries) - 1
                while snap_idx >= 0 and entries[snap_idx]["t"] != "snap":
                    snap_idx -= 1
                parent_ln = (entries[snap_idx]["ln"].split()
                             if snap_idx >= 0 else [])
                for j in range(snap_idx + 1, len(entries)):
                    parent_ln = _apply_delta(parent_ln, entries[j]["dl"])

                dl = _compute_delta(parent_ln, current_ln_list)
                la = sum(1 for op in dl if op[0] == "ins")
                lr = sum(1 for op in dl if op[0] == "del")
                lc = len(parent_ln) + la - lr
                entry = {
                    "v": 2, "t": "delta", "id": rev_id, "ts": ts_int,
                    "au": args.author,
                    "su": su_hash,
                    "sz": size_after,
                    "lc": lc,
                    "parent": last["id"] if last else None,
                    "szb": last.get("sz", 0) if last else 0,
                    "la": la, "lr": lr,
                    "dl": dl,
                }
                parent_lines = [_resolve_line(h, registries) for h in parent_ln]
                parent_content = "\n".join(parent_lines) + "\n" if parent_lines else ""

            if args.action == "delete":
                entry["action"] = "delete"

            # 保存更新后的行索引（仅写被修改的桶）
            for rbucket, reg in registries.items():
                path = LINE_INDEX_DIR / f"{rbucket}.json"
                if path.exists():
                    old_text = path.read_text(encoding="utf-8")
                    new_text = json.dumps(reg, ensure_ascii=False, sort_keys=True)
                    if old_text != new_text:
                        path.write_text(new_text, encoding="utf-8")
                else:
                    path.write_text(
                        json.dumps(reg, ensure_ascii=False, sort_keys=True),
                        encoding="utf-8")

            diff_chunks = _diff(parent_content, content)
        else:
            # ── v0 写入（未迁移的旧文件）─────────────────────────────────────
            last = entries[-1] if entries else None
            parent_content = last["content"] if last else ""
            size_before    = last["size"] if last else 0
            parent_rev     = last["rev_id"] if last else None

            diff_chunks = _diff(parent_content, content)
            entry = {
                "rev_id":       rev_id,
                "timestamp":    ts_iso,
                "author":       args.author,
                "summary":      args.summary or f"{args.author} {args.action}",
                "parent_rev":   parent_rev,
                "content_hash": f"sha256:{norm_sha}",
                "size_before":  size_before,
                "size":         size_after,
                "content":      content,
                "diff":         diff_chunks,
            }
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

    # ── recent.lite.jsonl + recent.diff.jsonl（滚动窗口，flock 保护）─────────
    diff_add  = sum(1 for d in diff_chunks if d[0] == "+")
    diff_del  = sum(1 for d in diff_chunks if d[0] == "-")

    recent_lite_entry = {
        "page": page,
        **{k: v for k, v in entry.items() if k not in ("content", "diff", "dl", "ln")},
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
