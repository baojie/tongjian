#!/usr/bin/env python3
"""按标点拆分行内容为 token，分析唯一 token 数和存储潜力。"""
from __future__ import annotations
import json, re
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LINE_INDEX = ROOT / "docs/wiki/line_index"
if not LINE_INDEX.is_dir():
    LINE_INDEX = ROOT / "wiki/public/line_index"

# 分隔符集合：中文/英文标点、空格、括号括号等
SEP_RE = re.compile(r'[，。；：！？、（）()\[\]【】「」『』""""''《》\n\r\t]')

def main():
    # 收集所有唯一行 + 全部行（含重复，算总词次）
    unique_lines: set[str] = set()
    all_lines: list[str] = []

    files = sorted(LINE_INDEX.glob("*.json"))
    for fi, f in enumerate(files):
        data = json.loads(f.read_text(encoding="utf-8"))
        vals = list(data.values())
        all_lines.extend(vals)
        unique_lines.update(vals)
        if (fi + 1) % 200 == 0:
            print(f"  已处理 {fi+1}/{len(files)} 文件, 累计唯一行 {len(unique_lines):,}", file=sys.stderr)

    total_unique = len(unique_lines)
    total_all = len(all_lines)  # 含重复的总行次
    total_chars = sum(len(l) for l in unique_lines)

    print(f"\n  唯一行: {total_unique:,}")
    print(f"  行次（含重复）: {total_all:,}")
    print(f"  总字符数: {total_chars:,}")
    print(f"  平均行长: {total_chars/max(1,total_unique):.1f} 字符")

    # 按分隔符拆分（保留空片段，但去重时不计空串）
    all_tokens: Counter = Counter()  # token → 出现次数
    unique_token_set: set[str] = set()
    token_count_per_line = []  # 每行产生的 token 数（用于估算）

    for line in unique_lines:
        parts = SEP_RE.split(line)
        tokens = [p for p in parts if p]  # 去空
        token_count_per_line.append(len(tokens))
        for t in tokens:
            all_tokens[t] += 1
            unique_token_set.add(t)

    unique_tokens = len(unique_token_set)
    total_token_occurrences = sum(all_tokens.values())

    # token 长度统计
    token_lengths = [len(t) for t in unique_token_set]
    avg_token_len = sum(token_lengths) / max(1, unique_tokens)
    max_token_len = max(token_lengths) if token_lengths else 0

    # 存储估算
    # 当前行索引大小 ~40.4 MB (JSON 结构)
    # 精确计算当前大小：每行 JSON entry 开销
    current_overhead_per_entry = 11  # "xxxxxx":"",\n 的结构
    current_size = sum(len(l) + current_overhead_per_entry for l in unique_lines)

    # token 方案：
    # 1. token 表：{"token": id, ...}
    #    {"xxxx":123,"yyyy":456,...}\n
    #    每个 entry: "token":id → 2(引号) + len(t) + 2(":) + id_digits + 1(,)
    #    = 5 + len(t) + id_digits
    id_digits = len(str(unique_tokens))
    token_index_entry_overhead = 5 + id_digits  # "":N,
    token_index_size = sum(len(t) + token_index_entry_overhead for t in unique_token_set)

    # 2. 行索引：{"hash":[id,id,...],...}
    #    每行的 token ID 数组
    #    结构：13 + token_ids + 3 ({"xxxxxx":[,],\n})
    avg_tokens_per_line = sum(token_count_per_line) / max(1, len(token_count_per_line))
    line_entry_overhead = 16  # {"xxxxxx":[  +  ]},\n
    token_line_size = 0
    total_token_ids = 0
    for line in unique_lines:
        parts = SEP_RE.split(line)
        tokens = [p for p in parts if p]
        total_token_ids += len(tokens)
        ids_str = ','.join(str(hash(t) % (10**id_digits)) for t in tokens)  # 模拟 ID
        entry_size = line_entry_overhead + len(ids_str)
        token_line_size += entry_size

    total_token_scheme = token_index_size + token_line_size

    # 更简单的估算：每行 = overhead + (avg_tokens_per_line × (id_digits + 1))
    simple_token_line_size = total_unique * (line_entry_overhead + avg_tokens_per_line * (id_digits + 0.9))
    simple_total = token_index_size + simple_token_line_size

    # 报告
    R = "=" * 60
    print(R)
    print("Token 化存储分析报告")
    print(R)

    print(f"\n【分词统计】")
    print(f"  唯一 token 数:        {unique_tokens:,}")
    print(f"  token 总出现次数:     {total_token_occurrences:,}")
    print(f"  平均 token 长度:      {avg_token_len:.1f} 字符")
    print(f"  最长 token:           {max_token_len} 字符")
    print(f"  每行平均 token 数:    {avg_tokens_per_line:.1f}")
    print(f"  每行 median token 数: {sorted(token_count_per_line)[len(token_count_per_line)//2]}")

    print(f"\n【token 长度分布】")
    buckets = Counter(min(lt, 50) for lt in token_lengths)
    for length in sorted(buckets):
        label = f"{length}" if length < 50 else "50+"
        bar = "█" * min(buckets[length] // 5000, 80)
        print(f"  {label:>4} 字符: {buckets[length]:>6}  {bar}")

    print(f"\n【最常见 token（前 20）】")
    for t, cnt in all_tokens.most_common(20):
        print(f"  {t!r} — {cnt:,} 次出现")

    print(f"\n【单例 token】")
    single = sum(1 for v in all_tokens.values() if v == 1)
    print(f"  仅出现 1 次的 token: {single:,} ({single/max(1,unique_tokens)*100:.1f}%)")

    print(f"\n【存储对比】")
    print(f"  方案                    | 索引大小   | 行内容大小 | 合计")
    print(f"  ─────────────────────────────────────────────────────────")
    print(f"  当前 (hash→全文)        | —         | {current_size/1024/1024:.1f} MB | {current_size/1024/1024:.1f} MB")
    print(f"  token (词表→[id])       | {token_index_size/1024/1024:.1f} MB | {token_line_size/1024/1024:.1f} MB | {total_token_scheme/1024/1024:.1f} MB")
    ratio = (1 - total_token_scheme / current_size) * 100 if current_size else 0
    print(f"  → token 方案: {total_token_scheme/1024/1024:.1f} MB, 相比当前 {'+' if ratio<0 else ''}{ratio:.1f}%")
    ratio_simple = (1 - simple_total / current_size) * 100 if current_size else 0
    print(f"  → token 方案(简化估): {simple_total/1024/1024:.1f} MB")

    print(f"\n【有 token 无分离场景分析】")
    # 多少行根本离不开？
    inseparable = 0
    for line in unique_lines:
        parts = SEP_RE.split(line)
        if len([p for p in parts if p]) <= 1:
            inseparable += 1
    print(f"  不可拆分（≤1 token）的行: {inseparable:,} ({inseparable/max(1,total_unique)*100:.1f}%)")

    print(f"\n【2-gram vs token 对比】")
    print(f"  2-gram 唯一: 716,367 | 唯一行: {total_unique:,}")
    print(f"  token 唯一:  {unique_tokens:,} | 唯一行: {total_unique:,}")
    print(f"  token 比 2-gram 少 {716367 - unique_tokens:,} 个单元 ({((716367 - unique_tokens)/716367)*100:.1f}%)")


if __name__ == "__main__":
    import sys
    main()
