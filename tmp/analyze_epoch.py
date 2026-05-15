#!/usr/bin/env python3
"""按次序分代（epoch）估算行索引压缩潜力。

当前 line_index：976 个 hash 桶，525K 行，40.4 MB 内容
方案：分代，每代固定行数，旧代 gzip，当前代 text。
"""
from __future__ import annotations
import json, gzip, io
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LINE_INDEX = ROOT / "docs/wiki/line_index"
if not LINE_INDEX.is_dir():
    LINE_INDEX = ROOT / "wiki/public/line_index"

# 加载全部行
all_lines: list[tuple[str, str]] = []  # (hash, content)
for f in sorted(LINE_INDEX.glob("*.json")):
    data = json.loads(f.read_text(encoding="utf-8"))
    all_lines.extend(data.items())

TOTAL_LINES = len(all_lines)
print(f"总行数: {TOTAL_LINES:,}")

# 当前当前大小（JSON entry overhead 评估）
current_total = sum(len(content) + 11 for _, content in all_lines)
current_per_line_avg = current_total / TOTAL_LINES
print(f"当前总大小 (评估): {current_total/1024/1024:.2f} MB")
print(f"每行平均: {current_per_line_avg:.1f} 字节")

# 对 976 桶分代，而非全局一整个文件
# 每个桶分代：每代 X 行 → 桶内 epoch_{N}/{bucket}.json(.gz)
# 桶内每代文件尺寸 ≈ X * per_line_bytes
# 前端按 current → epoch_N → epoch_N-1 → ... 顺序查找

# 用实际数据估算 gzip 压缩率
print("\n抽样测试 gzip 压缩率...")
sample = dict(all_lines[:5000])  # 5000 行
sample_text = json.dumps(sample, ensure_ascii=False, sort_keys=True)
sample_bytes = len(sample_text.encode("utf-8"))
sample_gz = len(gzip.compress(sample_text.encode("utf-8")))
gz_ratio = sample_gz / sample_bytes
print(f"  样本 {len(sample)} 行: text {sample_bytes/1024:.1f} KB → gzip {sample_gz/1024:.1f} KB ({gz_ratio*100:.0f}%)")

sample2 = dict(all_lines[:50000])
sample2_text = json.dumps(sample2, ensure_ascii=False, sort_keys=True)
sample2_bytes = len(sample2_text.encode("utf-8"))
sample2_gz = len(gzip.compress(sample2_text.encode("utf-8")))
gz_ratio2 = sample2_gz / sample2_bytes
print(f"  样本 {len(sample2)} 行: text {sample2_bytes/1024:.1f} KB → gzip {sample2_gz/1024:.1f} KB ({gz_ratio2*100:.0f}%)")

# 用 50K 样本的压缩率比较有代表性
GZIP_RATIO = gz_ratio2

# 按 976 桶分配行
buckets: dict[str, list[tuple[str, str]]] = {}
for h, c in all_lines:
    bk = h[0] + format('0123456789abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ'.index(h[1]) % 16, 'x')
    buckets.setdefault(bk, []).append((h, c))

BUCKET_COUNT = len(buckets)
print(f"\n实际桶数: {BUCKET_COUNT}")

# 模拟分代
def simulate_epoch(epoch_size: int, label: str):
    # 每桶内部分代
    total_text = 0.0   # 当前代（text）
    total_old = 0.0    # 旧代（gzip 前 text 大小）
    file_count_text = 0
    file_count_gz = 0

    for bk, entries in buckets.items():
        current_batch: list[tuple[str, str]] = []
        for h, c in entries:
            current_batch.append((h, c))
            if len(current_batch) >= epoch_size:
                # 冻结一批
                batch_text = json.dumps(dict(current_batch), ensure_ascii=False, sort_keys=True)
                total_old += len(batch_text.encode("utf-8"))
                file_count_gz += 1
                current_batch = []
        # 剩余 = 当前代
        if current_batch:
            batch_text = json.dumps(dict(current_batch), ensure_ascii=False, sort_keys=True)
            total_text += len(batch_text.encode("utf-8"))
            file_count_text += 1

    total_gzip = total_old * GZIP_RATIO
    total_all = total_text + total_gzip

    # 算一下每文件名太长，仅报告
    epochs_per_bucket = max(0, (len(buckets[list(buckets.keys())[0]]) - 1) // epoch_size) + 2
    avg_bucket_lines = TOTAL_LINES / BUCKET_COUNT
    epochs_avg = max(1, int(avg_bucket_lines / epoch_size) + 1)

    saving = (1 - total_all / current_total) * 100
    print(f"\n{label}")
    print(f"  {'─'*50}")
    print(f"  每代行数:        {epoch_size}")
    print(f"  总代均数/桶:     ~{epochs_avg} 代")
    print(f"  文件数:          text {file_count_text} + gzip {file_count_gz} = {file_count_text+file_count_gz}")
    print(f"  当前代 (text):   {total_text/1024/1024:.2f} MB")
    print(f"  旧代 (gzip):     {total_gzip/1024/1024:.2f} MB (源 {total_old/1024/1024:.2f} MB × {GZIP_RATIO:.2f})")
    print(f"  合计:            {total_all/1024/1024:.2f} MB  (vs 当前 {current_total/1024/1024:.2f} MB)")
    print(f"  节省:            −{saving:.1f}%")


# 各种代大小
simulate_epoch(100,    "代大小: 100 行")
simulate_epoch(500,    "代大小: 500 行")
simulate_epoch(2000,   "代大小: 2,000 行")
simulate_epoch(10000,  "代大小: 10,000 行")
simulate_epoch(50000,  "代大小: 50,000 行")

# 文件数分析
print(f"\n\n{'='*60}")
print(f"文件数与开销")
print(f"{'='*60}")
print(f"\n当前: {BUCKET_COUNT} 个 .json 文件")
print(f"实际磁盘: ~90 MB (ext4 块开销)")
for es in [100, 500, 2000, 10000, 50000]:
    files_gz = 0
    files_text = 0
    for bk, entries in buckets.items():
        n_batches = (len(entries) + es - 1) // es
        if n_batches <= 1:
            files_text += 1
        else:
            files_gz += n_batches - 1
            files_text += 1
    print(f"  代={es:>6}: {files_gz} gz + {files_text} text = {files_gz+files_text} files")
