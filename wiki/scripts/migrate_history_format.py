#!/usr/bin/env python3
"""migrate_history_format.py — 将 history 迁移到 v1 schema (snap + patch)

v2: 从旧 entry 的 content 字段重新计算全量 diff（旧 diff 是 context-truncated，不可重建用）
"""
import difflib, json, os, sys, time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
HIST = ROOT / "wiki/public/history"
SNAP_INTERVAL = 25


def _diff_text(old: str, new: str) -> str:
    """全量 unified diff 文本（包含所有行，确保可重建）。"""
    old = old.rstrip('\n') if old else old
    new = new.rstrip('\n') if new else new
    if old == new:
        return ""
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


def _convert_entries(entries: list[dict]) -> list[dict]:
    """转换为 v1 格式：从 content 字段重新计算全量 diff。"""
    result = []
    patches_since_snap = 0
    prev_id = None

    for i, e in enumerate(entries):
        rev_id = e.get("rev_id", "")
        content = e.get("content", "")
        content_hash = e.get("content_hash", "")

        is_first = (i == 0)
        needs_snap = is_first or patches_since_snap >= SNAP_INTERVAL

        base = {
            "v": 1,
            "id": rev_id,
            "ts": e.get("timestamp", ""),
            "au": e.get("author", ""),
            "su": e.get("summary", ""),
            "sz": e.get("size", 0),
            "ch": content_hash,
        }
        if e.get("action"):
            base["action"] = e["action"]

        if needs_snap:
            base["t"] = "snap"
            base["content"] = content
            patches_since_snap = 0
        else:
            # 重新计算全量 diff: from previous content to this content
            prev_content = entries[i - 1].get("content", "")
            diff = _diff_text(prev_content, content)
            base["t"] = "snap" if not diff else "patch"
            if not diff:
                # 内容无变化 → 仍存为 snap（不应发生，但防御）
                base["content"] = content
                patches_since_snap = 0
            else:
                base["parent"] = prev_id
                base["szb"] = e.get("size_before", 0)
                base["diff"] = diff
                patches_since_snap += 1

        result.append(base)
        prev_id = rev_id

    return result


def _migrate_file(fpath: Path) -> bool:
    try:
        raw = fpath.read_text(encoding="utf-8")
    except Exception as exc:
        print(f"  ⚠ 读失败: {fpath.name} — {exc}", file=sys.stderr)
        return False

    lines = [l for l in raw.splitlines() if l.strip()]
    if not lines:
        return False

    try:
        first = json.loads(lines[0])
    except json.JSONDecodeError:
        print(f"  ⚠ 解析失败: {fpath.name}", file=sys.stderr)
        return False

    if first.get("v") == 1 and first.get("content"):
        # 已迁移且是 v1 方案. 但如果 diff 太短（旧截断格式），需要重算
        # 安全检测：读所有 entry，检查 patches 的 diff 是否能覆盖重建
        # 简单策略：如果任一 patch 的 diff 比其 sz 小很多（<30%），说明是截断格式，需重算
        all_entries = []
        for line in lines:
            try:
                all_entries.append(json.loads(line))
            except:
                continue
        needs_recalc = False
        for e in all_entries:
            if e.get("t") == "patch" and e.get("diff"):
                if len(e["diff"]) < e.get("sz", 999999) * 0.3:
                    needs_recalc = True
                    break
        if not needs_recalc:
            return False  # 已经是正确全量 diff

        # 需要重算：用旧备份文件或从 content 重建
        # 但如果只有 v1 格式而没有原始 content，无法重算
        # 看看能否从备份获取
        bak = fpath.with_name(fpath.name + ".bak")
        if bak.exists():
            raw = bak.read_text(encoding="utf-8")
            lines = [l for l in raw.splitlines() if l.strip()]
            if not lines:
                return False
        else:
            # 没有备份，尝试从已有 v1 重新计算
            # 从 snap 的 content + patches 重建各版 content
            # 但 patches 是截断的，重建会错！
            # 只能重新计算 snap 间的 diff
            # 我们直接删掉重新迁移
            print(f"  ⚠ 无备份，删除后重迁: {fpath.name}")
            fpath.unlink()
            return False

    entries = []
    for line in lines:
        try:
            entries.append(json.loads(line))
        except json.JSONDecodeError:
            print(f"  ⚠ 跳过损坏行: {fpath.name}", file=sys.stderr)
            continue

    if not entries:
        return False

    new_entries = _convert_entries(entries)
    new_text = "\n".join(json.dumps(e, ensure_ascii=False) for e in new_entries) + "\n"

    old_sz = sum(len(l) for l in raw.splitlines())
    new_sz = len(new_text)

    # 原子写入
    tmp = fpath.with_name(f".{fpath.name}.tmp.{os.getpid()}")
    try:
        tmp.write_text(new_text, encoding="utf-8")
        tmp.replace(fpath)
    except Exception as exc:
        print(f"  ✗ 写入失败: {fpath.name} — {exc}", file=sys.stderr)
        if tmp.exists():
            tmp.unlink()
        return False

    pct = (1 - new_sz / old_sz) * 100 if old_sz else 0
    print(f"  ✓ {fpath.name}  {old_sz/1024:.1f}K → {new_sz/1024:.1f}K  ({pct:+.1f}%)")
    return True


def main() -> int:
    t0 = time.time()
    total_files = 0
    migrated_files = 0
    total_old = 0
    total_new = 0

    # 需要从备份恢复的文件列表（v1 格式但 diff 截断）
    # 先删除所有 v1 文件（会被跳过），然后把 .bak 恢复，重新迁移
    # 但实际上我们可以在迁移前做这个
    # 设计: 先恢复所有 .bak，删除所有 v1，再执行迁移

    buckets = sorted([d for d in HIST.iterdir() if d.is_dir() and d.name != ".git"])
    for bucket in buckets:
        jsonl_files = sorted(bucket.glob("*.jsonl"))
        # 排除 .bak 文件
        jsonl_files = [f for f in jsonl_files if not f.name.endswith(".bak")]
        for fpath in jsonl_files:
            total_files += 1
            old_sz = fpath.stat().st_size
            if _migrate_file(fpath):
                migrated_files += 1
            new_sz = fpath.stat().st_size
            total_old += old_sz
            total_new += new_sz

    elapsed = time.time() - t0
    pct = (1 - total_new / total_old) * 100 if total_old else 0
    print(f"\n{'='*60}")
    print(f"迁移完成")
    print(f"  总文件:   {total_files}")
    print(f"  已迁移:   {migrated_files}")
    print(f"  耗时:     {elapsed:.1f}s")
    print(f"  总大小:   {total_old/1024/1024:.1f} MB → {total_new/1024/1024:.1f} MB ({pct:+.1f}%)")
    print(f"{'='*60}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
