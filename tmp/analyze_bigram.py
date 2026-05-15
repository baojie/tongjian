#!/usr/bin/env python3
"""分析行索引的 2-gram 压缩潜力。"""
from __future__ import annotations
import json, sys, os
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LINE_INDEX = ROOT / "docs/wiki/line_index"
if not LINE_INDEX.is_dir():
    LINE_INDEX = ROOT / "wiki/public/line_index"

def bigrams(s: str) -> list[str]:
    """字符级 2-gram。"""
    return [s[i:i+2] for i in range(len(s) - 1)]

def main():
    # 收集所有唯一行
    all_lines: set[str] = set()
    files = sorted(LINE_INDEX.glob("*.json"))
    line_per_file = []
    for f in files:
        data = json.loads(f.read_text(encoding="utf-8"))
        lines = list(data.values())
        line_per_file.append((f.stem, len(lines)))
        all_lines.update(lines)

    total_unique = len(all_lines)
    total_chars = sum(len(l) for l in all_lines)
    avg_line_len = total_chars / total_unique if total_unique else 0

    # 2-gram 分析
    all_bigrams: Counter = Counter()
    for line in all_lines:
        for bg in bigrams(line):
            all_bigrams[bg] += 1

    unique_bigrams = len(all_bigrams)
    total_bigram_occurrences = sum(all_bigrams.values())

    # 不同长度的行各自的 2-gram 分布
    len_buckets = Counter()
    for line in all_lines:
        len_buckets[len(line)] += 1

    # 行编码为 2-gram ID 后的存储估算
    # 每行 = N-1 个 2-gram ID
    total_bigram_ids = sum(max(0, len(l) - 1) for l in all_lines)
    max_line_bigrams = max(0, max(len(l) for l in all_lines) - 1)

    # 2-gram ID 编码位数
    id_bits = unique_bigrams.bit_length()
    id_bytes = (id_bits + 7) // 8  # 每个 ID 至少 2 字节

    # 行内容存储（json 键值对结构）
    # 当前：每个 entry = 引号 + hash(6) + 引号 + : + 引号 + content + 引号 + 逗号 + 换行
    #       ≈ 7 + 2 + content_len + 2 = 11 + content_len
    # hash key 平均 6 字符，base62，所以 key 平均 7 字符（含引号）
    # 所以当前 line_index 开销 ≈ sum(len(content) + 11 for each)
    current_key_value_overhead = 11  # "xxxxxx": "" + ,\n 的结构开销
    current_total_size = sum(len(l) + current_key_value_overhead for l in all_lines)

    # 2-gram 方案
    # line_index: {"hash": [id1, id2, ...]}  每个 ID 用 2 字节整数
    # {hash: [id,id,...]} 编码为 json
    # key: 7, value: [n ids], 分隔符, 缩进
    # 使用 compact json: {"hash":[1,2,3]}\n
    # overhead: 8 ({"":}) + len(hash)
    # bigram IDs: N * (数字长度 + 1 逗号)
    bigram_id_json_overhead = 8  # ({"":}...[)
    bigram_comma_overhead_per_id = 1  # 逗号
    # 但实际每行是：{"hash":[1,2,3]},\n
    # hash 6 chars + 7 for "hash":"" = 13 chars overhead
    # 然后 [ids]
    # 每个 id 平均位数 = ceil(log10(unique_bigrams))
    id_digits = len(str(unique_bigrams))  # 十进制位数
    # JSON 整数组: "[1,2,3]" 每个 id 平均 id_digits + 0.9（逗号分摊）
    bigram_line_storage = 0
    for line in all_lines:
        n_bg = max(0, len(line) - 1)
        ids_chars = n_bg * id_digits + max(0, n_bg - 1)  # digits + commas
        entry_size = 13 + ids_chars + 3  # 13: {"xxxxxx": , 3: ]}\n — fixed key
        bigram_line_storage += entry_size

    # 2-gram 索引（bigram → id 映射）
    # {"刘备": 1, "备以": 2, ...}
    # key 2 chars + value digits + overhead
    bigram_index_size = sum(2 + 2 + id_digits for _ in range(unique_bigrams))  # 粗略估算
    # 更精确：每个 entry: "ab":123,\n → 2 + 1 + 1 + id_digits + 1 + 1 = 6 + id_digits
    bigram_index_size_precise = unique_bigrams * (6 + id_digits)

    total_bigram_scheme = bigram_line_storage + bigram_index_size_precise

    # --- 报告 ---
    R = "=" * 60

    print(R)
    print("行索引 2-gram 分析报告")
    print(R)

    print(f"\n【基线】")
    print(f"  唯一行:               {total_unique:,}")
    print(f"  总字符数:             {total_chars:,}")
    print(f"  平均行长:             {avg_line_len:.1f} 字符")
    print(f"  当前 line_index 大小: {current_total_size/1024/1024:.1f} MB (估算)")
    print(f"  实际磁盘大小:         93 MB")

    print(f"\n【2-gram 统计】")
    print(f"  唯一 2-gram 数:       {unique_bigrams:,}")
    print(f"  总 2-gram 出现次数:   {total_bigram_occurrences:,}")
    print(f"  每个 2-gram 平均频率: {total_bigram_occurrences/unique_bigrams:.1f} 次")
    print(f"  ID 编码位数:          {id_bits} bits → {id_bytes} bytes (JSON: ~{id_digits} 位十进制)")

    print(f"\n【行长度分布（前 10）】")
    for length, count in sorted(len_buckets.items())[:10]:
        print(f"  {length} 字符: {count:>6} 行")

    print(f"\n【最常见 2-gram（前 20）】")
    for bg, count in all_bigrams.most_common(20):
        r = f"U+{ord(bg[0]):04X} U+{ord(bg[1]):04X}" if len(bg)==2 else ""
        print(f"  {bg!r} ({r}) — {count:,} 次出现")

    print(f"\n【最少见 2-gram（后 10）】")
    for bg, count in all_bigrams.most_common()[:-11:-1]:
        print(f"  {bg!r} — {count} 次出现")

    print(f"\n【存储对比估算】")
    print(f"  方案                | 索引大小     | 行索引大小 | 合计")
    print(f"  ──────────────────────────────────────────────────")
    print(f"  当前 (hash→全文)     | —           | {current_total_size/1024/1024:.1f} MB | {current_total_size/1024/1024:.1f} MB")
    print(f"  2-gram (hash→[id])   | {bigram_index_size_precise/1024/1024:.1f} MB | {bigram_line_storage/1024/1024:.1f} MB | {total_bigram_scheme/1024/1024:.1f} MB")
    ratio = (1 - total_bigram_scheme/current_total_size)*100 if current_total_size else 0
    print(f"  → 2-gram 方案节省: {ratio:.1f}%")

    print(f"\n【补充: 占行数最多的大行】")
    # 按行长度排序
    longest = sorted(all_lines, key=len, reverse=True)[:5]
    for i, l in enumerate(longest):
        print(f"  #{i+1}: {len(l)} 字符 — {l[:80]}...")

    print(f"\n【补充: 空行和短行统计】")
    empty = sum(1 for l in all_lines if len(l) == 0)
    short = sum(1 for l in all_lines if 1 <= len(l) <= 3)
    vshort = sum(1 for l in all_lines if 4 <= len(l) <= 10)
    print(f"  空行 (0):     {empty:>6}")
    print(f"  超短 (1-3):   {short:>6}")
    print(f"  短 (4-10):    {vshort:>6}")


if __name__ == "__main__":
    main()
