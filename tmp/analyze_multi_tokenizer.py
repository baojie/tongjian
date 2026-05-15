#!/usr/bin/env python3
"""多种 tokenizer 对照分析行索引压缩潜力。"""
from __future__ import annotations
import json, re, sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LINE_INDEX = ROOT / "docs/wiki/line_index"
if not LINE_INDEX.is_dir():
    LINE_INDEX = ROOT / "wiki/public/line_index"

# ── 各种 tokenizer ──────────────────────────────────

def char_tokens(s: str):       return list(s)
def whitespace_tokens(s: str): return s.split()
def cjk_punct_tokens(s: str):  return [t for t in re.split(r'[，。；：！？、]', s) if t]
def all_punct_tokens(s: str):  return [t for t in re.split(r'[，。；：！？、（）()\[\]【】「」『』""""''《》\n\r\t]', s) if t]

def ngram_tokens(n: int):
    def tok(s: str):
        return [s[i:i+n] for i in range(max(0, len(s)-n+1))]
    return tok

# 识别 wikilink 模式的 tokenizer
# `[[xxx]]` 保持整体，其余按 CJK 标点切
WIKILINK_RE = re.compile(r'(\[\[.+?\]\])')
def wikilink_aware_tokens(s: str):
    parts = WIKILINK_RE.split(s)
    result = []
    for part in parts:
        if part.startswith('[[') and part.endswith(']]'):
            result.append(part)
        else:
            result.extend(cjk_punct_tokens(part))
    return [t for t in result if t]

# 尝试按 wiki 语法特征切
# `- ` 列表项, `> ` 引用, `### ` 标题, `[NNN-MMM]` PN编号,
# `[[xxx]]` wikilink, `**xxx**` 加粗
WIKI_FEATURE_RE = re.compile(
    r'(- |> |### |## |# |\*\*|\*\*\*|\[\[|\]\]|\]\||`[^`]+`)'
    r'|(\[?\d{3}-\d{3}\]?)'
)
def wiki_feature_tokens(s: str):
    parts = WIKI_FEATURE_RE.split(s)
    return [t for t in parts if t and t.strip()]

# ── 主分析 ──────────────────────────────────────────

def analyze(name: str, tokenizer, unique_lines: list[str]) -> dict:
    all_tokens: Counter = Counter()
    tokens_per_line = []
    for line in unique_lines:
        ts = tokenizer(line)
        tokens_per_line.append(len(ts))
        for t in ts:
            all_tokens[t] += 1

    unique_tokens = len(all_tokens)
    total_occurrences = sum(all_tokens.values())
    singles = sum(1 for v in all_tokens.values() if v == 1)

    # token 长度统计
    token_lens = [len(t) for t in all_tokens]
    avg_token_len = sum(token_lens) / max(1, unique_tokens)

    # 每行 token 数
    avg_tokens = sum(tokens_per_line) / max(1, len(tokens_per_line))
    med_tokens = sorted(tokens_per_line)[len(tokens_per_line)//2]

    # 存储估算
    id_digits = len(str(unique_tokens))
    token_index_overhead = 5 + id_digits  # "":N, 的开销
    token_index_size = sum(len(t) + token_index_overhead for t in all_tokens)

    line_overhead = 16  # {"xxxxxx":[  ]},\n
    total_line_size = 0
    for line, nt in zip(unique_lines, tokens_per_line):
        ids_str = ','.join(str(i) for i in range(nt))  # 模拟 ID
        total_line_size += line_overhead + len(ids_str)

    total_size = token_index_size + total_line_size

    return {
        "name": name,
        "unique_tokens": unique_tokens,
        "total_occurrences": total_occurrences,
        "avg_token_len": round(avg_token_len, 1),
        "singles": singles,
        "singles_pct": round(singles / max(1, unique_tokens) * 100, 1),
        "avg_tokens_per_line": round(avg_tokens, 1),
        "med_tokens_per_line": med_tokens,
        "token_index_size_mb": round(token_index_size / 1024 / 1024, 2),
        "line_size_mb": round(total_line_size / 1024 / 1024, 2),
        "total_mb": round(total_size / 1024 / 1024, 2),
        "vs_current_pct": round((1 - total_size / CURRENT_SIZE) * 100, 1),
    }

def header(name: str):
    print(f"\n{'─'*60}")
    print(f"  {name}")
    print(f"{'─'*60}")

def print_row(r: dict):
    vs = r["vs_current_pct"]
    vs_str = f"−{abs(vs):.1f}%" if vs >= 0 else f"+{abs(vs):.1f}%"
    print(f"  唯一 token: {r['unique_tokens']:>8,}  "
          f"(行数的 {r['unique_tokens']/UNIQUE_LINES*100:.1f}%)")
    print(f"  单例率:     {r['singles_pct']}%")
    print(f"  token/行:   {r['avg_tokens_per_line']} (中位数 {r['med_tokens_per_line']})")
    print(f"  平均 token 长度: {r['avg_token_len']} 字符")
    print(f"  词表大小:   {r['token_index_size_mb']} MB  "
          f"| 行大小: {r['line_size_mb']} MB  "
          f"| 合计: {r['total_mb']} MB")
    print(f"  → 相比当前 (40.4 MB): {vs_str}")


# ── jieba 分词（如可用）──────────────────────────────

try:
    import jieba
    HAVE_JIEBA = True
    # jieba 初始化
    for line in ["测试", "刘备以左将军领豫州牧"]:
        list(jieba.cut(line))
except ImportError:
    HAVE_JIEBA = False

def jieba_tokens(s: str):
    return list(jieba.cut(s))


if __name__ == "__main__":
    # 加载所有唯一行
    print("加载行索引...", file=sys.stderr)
    unique_lines: set[str] = set()
    files = sorted(LINE_INDEX.glob("*.json"))
    for fi, f in enumerate(files):
        data = json.loads(f.read_text(encoding="utf-8"))
        unique_lines.update(data.values())
        if (fi + 1) % 200 == 0:
            print(f"  {fi+1}/{len(files)}", file=sys.stderr)

    LINES = list(unique_lines)
    UNIQUE_LINES = len(LINES)
    TOTAL_CHARS = sum(len(l) for l in LINES)
    CURRENT_SIZE = sum(len(l) + 11 for l in LINES)  # 11 = JSON entry overhead
    print(f"唯一行: {UNIQUE_LINES:,}, 总字符: {TOTAL_CHARS:,}, "
          f"当前大小: {CURRENT_SIZE/1024/1024:.1f} MB", file=sys.stderr)

    # ── token 对照表 ─────────────────────────────────
    tokenizers = [
        ("逐字 (char)", char_tokens),
        ("按空格切分", whitespace_tokens),
        ("按 CJK 标点切", cjk_punct_tokens),
        ("按全标点切", all_punct_tokens),
        ("wikilink 感知切", wikilink_aware_tokens),
        ("3-gram", ngram_tokens(3)),
        ("4-gram", ngram_tokens(4)),
        ("5-gram", ngram_tokens(5)),
    ]

    if HAVE_JIEBA:
        tokenizers.append(("jieba 分词", jieba_tokens))

    print("\n" + "=" * 60)
    print("多种 Tokenizer 对照分析")
    print(f"唯一行: {UNIQUE_LINES:,}  |  当前 line_index: {CURRENT_SIZE/1024/1024:.1f} MB")
    print("=" * 60)

    results = []
    for name, tok in tokenizers:
        header(name)
        r = analyze(name, tok, LINES)
        print_row(r)
        results.append(r)

    # ── 对照表 ─────────────────────────────────────
    print(f"\n\n{'='*60}")
    print("对照总表")
    print(f"{'='*60}")
    print(f"{'Tokenizer':<20} {'唯一 token':>9} {'行比':>6} {'单例率':>7} "
          f"{'token/行':>8} {'合计 MB':>8} {'vs 当前':>8}")
    print(f"{'─'*20} {'─'*9} {'─'*6} {'─'*7} {'─'*8} {'─'*8} {'─'*8}")
    print(f"{'current (行级)':<20} {UNIQUE_LINES:>9,} {'100%':>6} {'—':>7} "
          f"{'1.0':>8} {CURRENT_SIZE/1024/1024:>8.1f} {'—':>8}")
    for r in results:
        vs = r["vs_current_pct"]
        vs_s = f"−{abs(vs):.1f}%" if vs >= 0 else f"+{abs(vs):.1f}%"
        ratio = r["unique_tokens"] / UNIQUE_LINES * 100
        print(f"{r['name']:<20} {r['unique_tokens']:>9,} "
              f"{ratio:>5.1f}%  {r['singles_pct']:>5}% "
              f"{r['avg_tokens_per_line']:>8} {r['total_mb']:>8.1f} {vs_s:>8}")
