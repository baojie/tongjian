#!/usr/bin/env python3
"""migrate_to_v2.py — 全量迁移 history 到 v2 line-hash 格式。

遍历所有桶的 history 文件（含归档），将 v0 entry 转为 v2：
  - Snap：存完整 ln（hash 数组），每 26 个 delta 后一个
  - Delta：存 dl（LCS 编辑操作），只记录变化

用法：
  python3 wiki/scripts/migrate_to_v2.py                     # 全量
  python3 wiki/scripts/migrate_to_v2.py --bucket zh         # 单桶
  python3 wiki/scripts/migrate_to_v2.py --page 诸葛亮        # 单页
"""
from __future__ import annotations
import difflib, hashlib, json, sys, time
from datetime import datetime
from pathlib import Path

ROOT       = Path(__file__).resolve().parents[2]
PUBLIC     = ROOT / "wiki/public"
PAGES      = PUBLIC / "pages"
HIST       = PUBLIC / "history"
LINE_INDEX = PUBLIC / "line_index"

sys.path.insert(0, str(ROOT / "wiki/scripts"))
from page_bucket import page_bucket, hash_bucket

MIN_HASH_LEN  = 6
SNAP_INTERVAL = 26

BASE62 = '0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz'


def base62_id(sha256_hex: str) -> str:
    """sha256 hex → 前6位 base62。"""
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


def load_all_registries() -> dict[str, dict[str, str]]:
    """加载全部 992 个行索引桶。"""
    registries: dict[str, dict[str, str]] = {}
    for f in sorted(LINE_INDEX.glob("*.json")):
        registries[f.stem] = json.loads(f.read_text(encoding="utf-8"))
    return registries


def resolve_line(h: str, registries: dict[str, dict[str, str]]) -> str:
    return registries.get(hash_bucket(h), {}).get(h, "")


def line_hash(line: str, registries: dict[str, dict[str, str]]) -> str:
    full = hashlib.sha256(line.encode("utf-8")).hexdigest()
    b62 = _hex_to_base62(full)
    bucket = hash_bucket(b62)
    registry = registries.get(bucket, {})
    for length in range(MIN_HASH_LEN, 17):
        h = b62[:length]
        if h not in registry or registry[h] == line:
            return h
    raise RuntimeError(f"16位仍有碰撞: {line[:60]}")


def compute_delta(parent_ln: list[str], current_ln: list[str]) -> list[list]:
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


def apply_delta(ln: list[str], dl: list[list]) -> list[str]:
    result = list(ln)
    for op in dl:
        if op[0] == "del":
            del result[op[1]]
        elif op[0] == "ins":
            result.insert(op[1], op[2])
    return result


def verify_reconstruction(v2_entries: list[dict], old_entries: list[dict],
                          registries: dict[str, dict[str, str]]) -> list[str]:
    """验证 v2 重建与 v0 content 一致。"""
    errors = []
    for i, (e, old) in enumerate(zip(v2_entries, old_entries)):
        if e["t"] == "snap":
            ln = e["ln"].split()
        else:
            snap_idx = i
            while snap_idx >= 0 and v2_entries[snap_idx]["t"] != "snap":
                snap_idx -= 1
            if snap_idx < 0:
                errors.append(f"[{i}] 无 snap 父节点")
                continue
            ln = v2_entries[snap_idx]["ln"].split()
            for j in range(snap_idx + 1, i + 1):
                ln = apply_delta(ln, v2_entries[j]["dl"])

        text = "\n".join(resolve_line(h, registries) for h in ln) + "\n"
        orig = old.get("content", "")
        if text.rstrip("\n") != orig.rstrip("\n"):
            errors.append(f"[{i}] 不匹配: len(orig)={len(orig)} len(rebuild)={len(text)}")
    return errors


def convert_page_entries(old_entries: list[dict],
                         registries: dict[str, dict[str, str]]) -> list[dict]:
    """将 v0 entries 转为 v2，返回 (v2_entries, stats)。"""
    v2 = []
    since_snap = 0

    for i, old in enumerate(old_entries):
        old_content = old.get("content", "")
        old_lines = old_content.splitlines()
        ln_str = ' '.join(line_hash(l, registries) for l in old_lines)
        sha = hashlib.sha256(old_content.encode('utf-8')).hexdigest()
        raw_ts = old.get("timestamp", old.get("ts", ""))
        ts_int = int(datetime.fromisoformat(raw_ts).timestamp()) if raw_ts else 0

        is_snap = (i == 0) or (since_snap >= SNAP_INTERVAL)

        entry: dict = {
            "v": 2,
            "id": base62_id(sha),
            "ts": ts_int,
            "au": old.get("author", old.get("au", "butler")),
            "su": line_hash(old.get("summary", old.get("su", "")), registries),
            "sz": old.get("size", old.get("sz", 0)),
        }

        if is_snap:
            entry["t"] = "snap"
            entry["ln"] = ln_str
            since_snap = 0
        else:
            prev = old_entries[i - 1]
            prev_content = prev.get("content", "")
            prev_lines = prev_content.splitlines()
            dl = compute_delta(
                [line_hash(l, registries) for l in prev_lines],
                [line_hash(l, registries) for l in old_lines])
            entry["t"] = "delta"
            entry["parent"] = v2[i - 1]["id"]
            entry["szb"] = prev.get("size", prev.get("sz", 0))
            entry["dl"] = dl
            since_snap += 1

        v2.append(entry)

    return v2


def migrate_file(path: Path, registries: dict[str, dict[str, str]]) -> dict:
    """迁移单个 history 文件，返回统计信息。"""
    rel = path.relative_to(HIST)
    text = path.read_text(encoding="utf-8")

    old_entries = []
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            old_entries.append(json.loads(line))
        except json.JSONDecodeError:
            pass

    if not old_entries:
        return {"path": str(rel), "status": "empty", "entries": 0}

    # 检测是否已迁移
    if old_entries[0].get("v") == 2:
        return {"path": str(rel), "status": "already_v2", "entries": len(old_entries)}

    v2_entries = convert_page_entries(old_entries, registries)

    # 验证
    errors = verify_reconstruction(v2_entries, old_entries, registries)
    if errors:
        return {"path": str(rel), "status": "verify_fail", "entries": len(v2_entries),
                "errors": errors}

    # 原子写入
    v2_text = "\n".join(json.dumps(e, ensure_ascii=False) for e in v2_entries) + "\n"
    tmp = path.with_suffix(".tmp")
    tmp.write_text(v2_text, encoding="utf-8")
    tmp.replace(path)

    snaps = sum(1 for e in v2_entries if e["t"] == "snap")
    deltas = sum(1 for e in v2_entries if e["t"] == "delta")

    return {"path": str(rel), "status": "ok", "entries": len(v2_entries),
            "snaps": snaps, "deltas": deltas}


def migrate_bucket(_bucket: str) -> dict:
    """迁移一个桶下所有 history 文件。"""
    stats = {"ok": 0, "skip": 0, "fail": 0, "total_entries": 0,
             "total_bytes_v0": 0, "total_bytes_v2": 0, "errors": []}

    registries = load_all_registries()
    if not registries:
        return {**stats, "error": "无行索引文件"}

    hist_dir = HIST / _bucket
    if not hist_dir.is_dir():
        return {**stats, "error": f"history 目录不存在: {_bucket}"}

    files = sorted(hist_dir.glob("*.jsonl"))
    if not files:
        return {**stats, "error": f"无 history 文件: {_bucket}"}

    for fpath in files:
        result = migrate_file(fpath, registries)
        if result["status"] == "ok":
            stats["ok"] += 1
            stats["total_entries"] += result["entries"]
        elif result["status"] == "already_v2":
            stats["skip"] += 1
        elif result["status"] == "verify_fail":
            stats["fail"] += 1
            stats["errors"].append(result)
        # skip empty, skipped

    return stats


def main() -> int:
    import argparse
    ap = argparse.ArgumentParser(description="全量迁移 history 到 v2")
    ap.add_argument("--bucket", help="只迁移指定桶")
    ap.add_argument("--page", help="只迁移指定页面")
    args = ap.parse_args()

    t0 = time.time()

    if args.page:
        bucket = page_bucket(args.page)
        page_file = HIST / bucket / f"{args.page}.jsonl"
        if not page_file.exists():
            print(f"✗ history 文件不存在: {page_file}")
            return 1
        registries = load_all_registries()
        if not registries:
            print("✗ 无行索引文件")
            return 1
        result = migrate_file(page_file, registries)
        if result["status"] == "ok":
            print(f"✓ {result['path']}  {result['entries']} entries  "
                  f"({result['snaps']} snaps + {result['deltas']} deltas)")
        elif result["status"] == "already_v2":
            print(f"  {result['path']}  已是 v2")
        else:
            print(f"✗ {result['path']}: {result.get('errors', [])}")
        elapsed = time.time() - t0
        print(f"\n耗时: {elapsed:.1f}s")
        return 0

    if args.bucket:
        buckets = [args.bucket]
    else:
        buckets = sorted([
            d.name for d in HIST.iterdir()
            if d.is_dir() and not d.name.startswith(".")
        ])

    grand = {"ok": 0, "skip": 0, "fail": 0, "total_entries": 0, "errors": []}

    for bucket in buckets:
        bt0 = time.time()
        stats = migrate_bucket(bucket)
        bt = time.time() - bt0

        if "error" in stats:
            print(f"  {bucket}/  — {stats['error']}")
            continue

        if stats["ok"] or stats["skip"] or stats["fail"]:
            parts = []
            if stats["ok"]:
                parts.append(f"{stats['ok']} files, {stats['total_entries']} entries")
            if stats["skip"]:
                parts.append(f"{stats['skip']} already v2")
            if stats["fail"]:
                parts.append(f"✗ {stats['fail']} failed")
            print(f"  {bucket}/  {', '.join(parts)}  ({bt:.1f}s)")

            grand["ok"] += stats["ok"]
            grand["skip"] += stats["skip"]
            grand["fail"] += stats["fail"]
            grand["total_entries"] += stats["total_entries"]
            grand["errors"].extend(stats["errors"])

    elapsed = time.time() - t0

    print(f"\n{'='*60}")
    print(f"完成: {grand['ok']} files migrated, {grand['skip']} already v2, "
          f"{grand['fail']} failed")
    print(f"总 entries: {grand['total_entries']}")
    if grand["errors"]:
        print(f"\n失败详情:")
        for e in grand["errors"]:
            print(f"  ✗ {e['path']}: {e['errors']}")
    print(f"耗时: {elapsed:.1f}s")

    return 1 if grand["fail"] else 0


if __name__ == "__main__":
    sys.exit(main())
