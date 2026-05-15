#!/usr/bin/env python3
"""分析 line_index 按时间分 epoch + gzip 的效果。

遍历全部 history snap 条目，统计每行 hash 首次出现的时间分布。
"""
from __future__ import annotations
import json, gzip, sys, time
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
HIST = ROOT / "docs/wiki/history"
if not HIST.is_dir():
    HIST = ROOT / "wiki/public/history"
LINE_INDEX = ROOT / "docs/wiki/line_index"
if not LINE_INDEX.is_dir():
    LINE_INDEX = ROOT / "wiki/public/line_index"

def scan_all_snaps() -> dict[str, int]:
    """扫描全部 history 的 snap，返回 {line_hash: first_seen_timestamp_s}。"""
    first_seen: dict[str, int] = {}
    total_files = 0
    total_snaps = 0

    buckets = sorted(HIST.iterdir())
    for bi, bucket in enumerate(buckets):
        if not bucket.is_dir() or bucket.name.startswith("."):
            continue
        files = sorted(bucket.glob("*.jsonl"))
        for fpath in files:
            try:
                text = fpath.read_text(encoding="utf-8")
            except Exception:
                continue
            for line in text.splitlines():
                if not line.strip():
                    continue
                try:
                    entry = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if entry.get("t") == "snap" and entry.get("ln"):
                    ts = entry.get("ts", 0)
                    for h in entry["ln"].split():
                        if h not in first_seen:
                            first_seen[h] = ts
                elif entry.get("v") != 2 and entry.get("content"):
                    # v0: 模拟 ln — 不用 content 拆行了，跳过
                    pass
            total_snaps += 1  # 近似

        total_files += len(files)
        if (bi + 1) % 20 == 0:
            print(f"  已扫 {bi+1}/{len(buckets)} 桶, "
                  f"{len(first_seen):,} 唯一行", file=sys.stderr)

    return first_seen


def estimate_line_index_size(lines: set[str]) -> float:
    """估算 N 行在 line_index 中的大小 (MB)。"""
    return sum(len(l) + 11 for l in lines) / 1024 / 1024


def main():
    t0 = time.time()
    print("扫描全部 history snap 条目...", file=sys.stderr)

    # 加载 line_index 所有行内容
    print("加载 line_index...", file=sys.stderr)
    line_content: dict[str, str] = {}
    for f in sorted(LINE_INDEX.glob("*.json")):
        data = json.loads(f.read_text(encoding="utf-8"))
        line_content.update(data)

    print(f"  行索引: {len(line_content):,} 行", file=sys.stderr)

    first_seen = scan_all_snaps()
    el = time.time() - t0
    print(f"\n扫描完成: {len(first_seen):,} 行有首次出现时间, "
          f"耗时 {el:.0f}s", file=sys.stderr)

    # 按月份分组
    monthly: dict[str, list[str]] = defaultdict(list)
    for h, ts in first_seen.items():
        dt = datetime.fromtimestamp(ts, tz=timezone.utc)
        key = dt.strftime("%Y-%m")
        monthly[key].append(h)

    # 总行数 vs 有时间戳的行
    all_hashes = set(line_content.keys())
    has_time = set(first_seen.keys())
    no_time = all_hashes - has_time  # snap 中从未出现的行（纯来自 delta 新增行）

    print(f"\n{'='*60}")
    print("时间分桶分析")
    print(f"{'='*60}")

    print(f"\n  行索引总数:        {len(all_hashes):,}")
    print(f"  有首次时间戳:      {len(has_time):,} ({len(has_time)/len(all_hashes)*100:.1f}%)")
    print(f"  无时间戳 (delta):  {len(no_time):,} ({len(no_time)/len(all_hashes)*100:.1f}%)")

    # 估算无时间戳行的分布（按比例分到最后几个月）
    if no_time:
        print(f"  → 无时间戳行将按比例分到最近几个月")

    # 按月份排序
    sorted_months = sorted(monthly.keys())
    # 把无时间戳的行按比例分到最近 N 个月（假设最近更活跃）
    if no_time:
        recent_n = min(6, len(sorted_months))
        recent_months = sorted_months[-recent_n:] if recent_n > 0 else sorted_months
        weights = [len(monthly[m]) for m in recent_months]
        total_w = sum(weights)
        no_time_list = list(no_time)
        idx = 0
        for m, w in zip(recent_months, weights):
            n = int(len(no_time_list) * w / total_w) if total_w else 0
            monthly[m].extend(no_time_list[idx:idx+n])
            idx += n

    # 累计统计
    cumulative_lines: set[str] = set()
    cumulative_size = 0.0

    print(f"\n{'月份':<10} {'新行':>8} {'累计行':>10} {'累计 MB':>8} {'占比':>6}")
    print(f"{'─'*10} {'─'*8} {'─'*10} {'─'*8} {'─'*6}")

    month_totals: list[tuple[str, int]] = []
    for m in sorted_months:
        new_lines = monthly[m]
        new_set = set(new_lines)
        before = len(cumulative_lines)
        cumulative_lines |= new_set
        added = len(cumulative_lines) - before
        cum_size = estimate_line_index_size(cumulative_lines)
        pct = len(cumulative_lines) / len(all_hashes) * 100
        print(f"{m:<10} {added:>8,} {len(cumulative_lines):>10,} {cum_size:>7.1f} {pct:>5.1f}%")
        month_totals.append((m, added))

    # 完整 line_index 大小
    full_current_size = estimate_line_index_size(all_hashes)
    print(f"{'─'*10} {'─'*8} {'─'*10} {'─'*8} {'─'*6}")
    print(f"{'合计':<10} {len(has_time):>8,} {len(all_hashes):>10,} "
          f"{full_current_size:>7.1f} {'100%':>6}")

    # ── Epoch 方案估算 ──────────────────────────────
    print(f"\n{'='*60}")
    print("Epoch 方案存储估算")
    print(f"{'='*60}")

    # 假设按月分 epoch，旧 epoch 全量 gzip（压缩率 20%，即降至原大小的 20%）
    GZIP_RATIO = 0.20

    # 当前无 epoch：line_index 全部是 text json
    print(f"\n  基线: line_index 全部 text json")
    print(f"  → {full_current_size:.1f} MB (实际磁盘 {full_current_size*976*0.004:.0f} MB 含 fs 开销)")

    # 方案：每月一个 epoch，旧 epoch gzip，当月 text
    print(f"\n  按月分 epoch（旧 epoch gzip，当月 text json）:")
    total_text = 0.0
    total_gzip = 0.0
    epoch_count = 0
    for m, added in month_totals:
        if added == 0:
            continue
        month_lines = {h for h in monthly[m]}
        month_size = estimate_line_index_size(month_lines)
        if m == sorted_months[-1] or m == sorted_months[-1]:  # 当月
            total_text += month_size
            print(f"  {m}: {month_size:.2f} MB (text, 当月)")
        else:
            total_gzip += month_size * GZIP_RATIO
            if epoch_count < 3 or m in (sorted_months[-2],):
                print(f"  {m}: {month_size:.2f} MB × {GZIP_RATIO} = {month_size*GZIP_RATIO:.2f} MB (gzip)")
            epoch_count += 1

    # 无时间戳行（分到最近 N 个月的）
    # 已经被分摊进 monthly 了

    total_epoch = total_text + total_gzip
    saving = (1 - total_epoch / full_current_size) * 100
    print(f"\n  text 小计: {total_text:.1f} MB")
    print(f"  gzip 小计: {total_gzip:.1f} MB")
    print(f"  合计:      {total_epoch:.1f} MB")
    print(f"  vs 当前:   −{saving:.1f}%")

    # 简单方案：直接 gzip 超过 X 天未改的桶
    print(f"\n  简单方案: 直接 gzip 超过 60 天未修改的 line_index 桶")
    now = time.time()
    old_size = 0
    recent_size = 0
    old_count = 0
    recent_count = 0
    for f in sorted(LINE_INDEX.glob("*.json")):
        mtime = f.stat().st_mtime
        if now - mtime > 60 * 86400:
            old_size += f.stat().st_size
            old_count += 1
        else:
            recent_size += f.stat().st_size
            recent_count += 1
    total_disk = old_size + recent_size
    old_gzip = old_size * GZIP_RATIO
    simple_total = old_gzip + recent_size
    print(f"  >60 天未改: {old_count} 桶, {old_size/1024/1024:.1f} MB → gzip {old_gzip/1024/1024:.1f} MB")
    print(f"  ≤60 天有改: {recent_count} 桶, {recent_size/1024/1024:.1f} MB (保持 text)")
    print(f"  合计:       {simple_total/1024/1024:.1f} MB (vs 当前 {total_disk/1024/1024:.1f} MB)")
    print(f"  vs 当前:    −{(1-simple_total/total_disk)*100:.1f}%")


if __name__ == "__main__":
    main()
