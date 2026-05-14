#!/usr/bin/env python3
"""conv_to_v2.py — 将单页 history 转为 v2 line-hash 格式（实验/验证用）。"""
from __future__ import annotations
import hashlib, json, sys, time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PUBLIC = ROOT / "wiki/public"
PAGES = PUBLIC / "pages"
HIST = PUBLIC / "history"
LINE_INDEX = PUBLIC / "line_index"

sys.path.insert(0, str(ROOT / "wiki/scripts"))
from page_bucket import page_bucket, resolve_page_file

MIN_HASH_LEN = 6
SNAP_INTERVAL = 26


def line_hash(line: str, registry: dict[str, str]) -> str:
    full = hashlib.sha256(line.encode("utf-8")).hexdigest()
    for length in range(MIN_HASH_LEN, 17):
        h = full[:length]
        if h not in registry or registry[h] == line:
            return h
    raise RuntimeError(f"16位仍有碰撞: {line[:60]}")


def compute_delta(parent_ln: list[str], current_ln: list[str]
                  ) -> list[list]:
    """用 LCS diff 计算从 parent_ln 到 current_ln 的编辑操作。

    dl 元素: ["ins", pos, hash] / ["del", pos]
    ops 按从尾到头的顺序生成，apply_delta 按此顺序执行。
    """
    import difflib
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
    return dl  # 逆序 ops，apply 时逆序执行


def apply_delta(ln: list[str], dl: list[list]) -> list[str]:
    """按顺序应用 dl 操作，返回新的 hash 数组。"""
    result = list(ln)
    for op in dl:
        if op[0] == "del":
            del result[op[1]]
        elif op[0] == "ins":
            result.insert(op[1], op[2])
        elif op[0] == "mod":
            result[op[1]] = op[2]
    return result


def convert_page(page: str) -> dict:
    bucket = page_bucket(page)
    src = resolve_page_file(PAGES, page)
    if not src:
        return {"error": f"页面不存在: {page}"}

    # 加载行索引
    index_path = LINE_INDEX / f"{bucket}.json"
    if not index_path.exists():
        return {"error": f"行索引不存在: {bucket}"}
    with open(index_path, encoding="utf-8") as f:
        registry: dict[str, str] = json.load(f)

    # 读取当前页面内容
    current_text = src.read_text(encoding="utf-8")
    current_lines = current_text.rstrip("\n").split("\n")
    current_sha = hashlib.sha256(current_text.encode("utf-8")).hexdigest()

    # 读取现有 history (v0 格式，每条有 content)
    hist_dir = HIST / bucket
    page_jsonl = hist_dir / f"{page}.jsonl"
    if not page_jsonl.exists():
        return {"error": f"history 不存在: {page}"}

    old_entries = []
    for line in page_jsonl.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line:
            try:
                old_entries.append(json.loads(line))
            except json.JSONDecodeError:
                pass

    # 转换为 v2
    v2_entries = []
    stats = {"snaps": 0, "deltas": 0}
    since_snap = 0  # 距上一个 snap 的 delta 数

    for i, old in enumerate(old_entries):
        old_content = old.get("content", "")
        old_lines = old_content.rstrip("\n").split("\n")

        # 计算每行 hash
        ln = [line_hash(l, registry) for l in old_lines]

        is_snap = (i == 0) or (since_snap >= SNAP_INTERVAL)

        entry = {
            "v": 2,
            "id": old.get("rev_id", old.get("id", "")),
            "ts": old.get("timestamp", old.get("ts", "")),
            "au": old.get("author", old.get("au", "butler")),
            "su": old.get("summary", old.get("su", "")),
            "sz": old.get("size", old.get("sz", 0)),
            "ch": old.get("content_hash", old.get("ch", "")),
        }

        if is_snap:
            entry["t"] = "snap"
            entry["ln"] = ln
            stats["snaps"] += 1
            since_snap = 0
        else:
            prev = old_entries[i - 1]
            prev_content = prev.get("content", "")
            prev_lines = prev_content.rstrip("\n").split("\n")
            parent_ln = [line_hash(l, registry) for l in prev_lines]
            dl = compute_delta(parent_ln, ln)
            entry["t"] = "delta"
            entry["parent"] = prev.get("rev_id", prev.get("id", ""))
            entry["szb"] = prev.get("size", prev.get("sz", 0))
            entry["dl"] = dl
            stats["deltas"] += 1
            since_snap += 1

        v2_entries.append(entry)

    v2_text = "\n".join(json.dumps(e, ensure_ascii=False) for e in v2_entries) + "\n"
    stat = page_jsonl.stat()
    v0_bytes = stat.st_size

    return {
        "page": page,
        "bucket": bucket,
        "v0_entries": len(old_entries),
        "v2_entries": len(v2_entries),
        "snaps": stats["snaps"],
        "deltas": stats["deltas"],
        "v0_bytes": v0_bytes,
        "v2_bytes": len(v2_text.encode("utf-8")),
        "index_bytes": index_path.stat().st_size,
        "v2": v2_entries,
        "_old": old_entries,
    }


def verify_reconstruction(v2_entries: list[dict], old_entries: list[dict],
                           registry: dict[str, str]) -> list[str]:
    """验证 v2 重建内容与 v0 原始 content 一致。"""
    errors = []
    for i, (e, old) in enumerate(zip(v2_entries, old_entries)):
        if e["t"] == "snap":
            ln = list(e["ln"])
        else:
            snap_idx = i
            while snap_idx >= 0 and v2_entries[snap_idx]["t"] != "snap":
                snap_idx -= 1
            snap = v2_entries[snap_idx]
            ln = list(snap["ln"])
            for j in range(snap_idx + 1, i + 1):
                ln = apply_delta(ln, v2_entries[j]["dl"])

        lines = [registry.get(h, "") for h in ln]
        text = "\n".join(lines) + "\n"
        orig = old.get("content", "")
        if text.rstrip("\n") != orig.rstrip("\n"):
            errors.append(f"[{i}] 内容不匹配: "
                          f"len(orig)={len(orig)} len(rebuilt)={len(text)}")
    return errors


def main():
    pages = sys.argv[1:] if len(sys.argv) > 1 else ["诸葛亮", "刘备", "丞相"]
    for page in pages:
        t0 = time.time()
        result = convert_page(page)
        el = time.time() - t0
        if "error" in result:
            print(f"✗ {page}: {result['error']}")
            continue

        # 验证重建
        bucket = result["bucket"]
        with open(LINE_INDEX / f"{bucket}.json", encoding="utf-8") as f:
            registry = json.load(f)
        errors = verify_reconstruction(
            result["v2"], result["_old"], registry)

        ratio = (1 - result["v2_bytes"] / result["v0_bytes"]) * 100
        status = "✓" if not errors else "✗"
        print(f"\n{'='*60}")
        print(f"{status} {page} ({bucket})")
        print(f"  v0: {result['v0_entries']} entries  {result['v0_bytes']/1024:.1f} KB")
        print(f"  v2: {result['snaps']} snaps + {result['deltas']} deltas  "
              f"{result['v2_bytes']/1024:.1f} KB  ({ratio:+.1f}%)")
        print(f"  行索引: {result['index_bytes']/1024:.1f} KB")
        if errors:
            for e in errors:
                print(f"  ⚠ {e}")
        else:
            print(f"  重建: 全部 {result['v0_entries']} 条通过")
        print(f"  耗时: {el*1000:.0f}ms")


if __name__ == "__main__":
    main()
