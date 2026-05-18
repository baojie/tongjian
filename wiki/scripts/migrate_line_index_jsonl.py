#!/usr/bin/env python3
"""migrate_line_index_jsonl.py — 将 line_index/*.json 转换为 *.jsonl 格式。

JSON → JSONL 格式转换：

旧格式（JSON 对象）:
  {"hash1":"content1","hash2":"content2"}

新格式（JSONL，每行一个 hash→content 映射）:
  {"hash1":"content1"}
  {"hash2":"content2"}

执行后删除旧 .json 文件，仅保留 .jsonl。
"""
from __future__ import annotations
import json, sys
from pathlib import Path

ROOT   = Path(__file__).resolve().parents[2]
PUBLIC = ROOT / "docs/wiki"
OUT    = PUBLIC / "line_index"

def main() -> int:
    if not OUT.exists():
        print(f"✗ {OUT} 不存在", file=sys.stderr)
        return 1

    converted = 0
    errors = 0
    for fpath in sorted(OUT.glob("*.json")):
        bucket = fpath.stem
        try:
            data = json.loads(fpath.read_text(encoding="utf-8"))
        except Exception as e:
            print(f"✗ {bucket}.json 解析失败: {e}")
            errors += 1
            continue

        jsonl_path = fpath.with_suffix(".jsonl")
        with jsonl_path.open("w", encoding="utf-8") as f:
            for h, content in data.items():
                f.write(json.dumps({h: content}, ensure_ascii=False) + "\n")
        old_size = fpath.stat().st_size
        new_size = jsonl_path.stat().st_size
        ratio = new_size / old_size * 100 if old_size else 0
        print(f"  {bucket}  {len(data):6d} 行  {old_size/1024:7.1f}→{new_size/1024:7.1f} KB  ({ratio:.0f}%)")
        fpath.unlink()  # 删除旧 JSON 文件
        converted += 1

    print(f"\n完成: {converted} 桶转换, {errors} 错误")
    return 0

if __name__ == "__main__":
    sys.exit(main())
