#!/usr/bin/env python3
"""分析：不分 976 桶，按次序分代，整文件 gzip。"""
from __future__ import annotations
import json, gzip
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LINE_INDEX = ROOT / "docs/wiki/line_index"
if not LINE_INDEX.is_dir():
    LINE_INDEX = ROOT / "wiki/public/line_index"

all_lines: list[tuple[str, str]] = []
for f in sorted(LINE_INDEX.glob("*.json")):
    data = json.loads(f.read_text(encoding="utf-8"))
    all_lines.extend(data.items())

TOTAL = len(all_lines)
print(f"总行数: {TOTAL:,}")

# 当前整包
full_dict = dict(all_lines)
full_json = json.dumps(full_dict, ensure_ascii=False, sort_keys=True)
full_bytes = len(full_json.encode("utf-8"))
full_gz = len(gzip.compress(full_json.encode("utf-8")))
full_gz_ratio = full_gz / full_bytes
print(f"\n整包 line_index (1 个文件):")
print(f"  text: {full_bytes/1024/1024:.2f} MB")
print(f"  gzip: {full_gz/1024/1024:.2f} MB ({full_gz_ratio*100:.0f}%)")

def simulate(epoch_size: int, label: str):
    epochs_text = []
    for i in range(0, TOTAL, epoch_size):
        chunk = dict(all_lines[i:i+epoch_size])
        j = json.dumps(chunk, ensure_ascii=False, sort_keys=True)
        epochs_text.append(len(j.encode("utf-8")))

    if not epochs_text:
        return

    current_size = epochs_text[-1]  # 最后一代 = current (text)
    old_text = sum(epochs_text[:-1])  # 前几代 (gzip)
    old_gz = int(old_text * full_gz_ratio)
    total = current_size + old_gz
    saving = (1 - total / full_bytes) * 100

    n_epochs = len(epochs_text)
    gz_files = n_epochs - 1

    # 每代文件尺寸信息
    print(f"\n  {label}")
    print(f"  {'─'*50}")
    print(f"  总代数:        {n_epochs} 代 ({gz_files} gzip + 1 text)")
    for i, s in enumerate(epochs_text):
        marker = "text ← current" if i == n_epochs - 1 else "gzip"
        print(f"    代 {i:>2}: {s/1024/1024:.2f} MB ({marker})")
    print(f"  旧代 gzip:     {old_gz/1024/1024:.2f} MB")
    print(f"  当前 text:     {current_size/1024/1024:.2f} MB")
    print(f"  合计:          {total/1024/1024:.2f} MB  (vs {full_bytes/1024/1024:.2f} MB)")
    print(f"  节省:          −{saving:.1f}%")


print(f"\n{'='*60}")
print("不分桶，按发现次序分代")
print(f"{'='*60}")
print(f"\ngzip 压缩率: {full_gz_ratio*100:.0f}% (整包)")

simulate(50000,    "代大小: 50,000 行")
simulate(100000,   "代大小: 100,000 行")
simulate(200000,   "代大小: 200,000 行")
