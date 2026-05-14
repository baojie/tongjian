#!/usr/bin/env python3
"""
check_citations.py — Butler W6 离线质检：验证 wiki 页面引文可溯源到原文。

验证目标: corpus/raw/资治通鉴.txt（294卷，约300万字）
不用章节页（含 PN 标注，字符串匹配会误判）。

用法:
  python3 wiki/scripts/butler/check_citations.py wiki/public/pages/曹操.md
  python3 wiki/scripts/butler/check_citations.py --all
  python3 wiki/scripts/butler/check_citations.py --featured
  python3 wiki/scripts/butler/check_citations.py --fix-critical wiki/public/pages/曹操.md
"""

import re
import sys
import json
import argparse
import subprocess
from pathlib import Path
from datetime import datetime

REPO_ROOT = Path(__file__).resolve().parents[3]
CORPUS_FILE = REPO_ROOT / "corpus" / "raw" / "资治通鉴.txt"
PAGES_DIR = REPO_ROOT / "wiki" / "public" / "pages"
ISSUES_LOG = REPO_ROOT / "wiki" / "logs" / "butler" / "citation_issues.jsonl"
RECORD_REV = REPO_ROOT / "wiki/scripts/record_revision.py"

MIN_FRAGMENT_LEN = 8  # 少于8字的片段不验证（太短易误匹配）


def load_corpus() -> str:
    """加载资治通鉴全文作为验证源。"""
    return CORPUS_FILE.read_text(encoding="utf-8")


def clean_fragment(text: str) -> list[str]:
    """清洗引文片段：去掉 markdown 符号、空格、省略号等。"""
    text = re.sub(r"\*+", "", text)                    # 去 markdown 加粗/斜体
    text = re.sub(r"\[\[([^\]|]+)(?:\|[^\]]+)?\]\]", r"\1", text)  # 去 wikilink
    text = text.replace("&nbsp;", " ")
    # 省略号两端截取
    if "……" in text or "..." in text:
        parts = re.split(r"……|\.\.\.", text)
        parts = [p.strip() for p in parts if len(p.strip()) >= MIN_FRAGMENT_LEN]
        return parts
    text = text.strip()
    return [text] if len(text) >= MIN_FRAGMENT_LEN else []


def extract_quotes(md_text: str) -> list[dict]:
    """
    从 markdown 页面提取引文，返回 [{text, line_no, quote_type}]。
    提取两种：
    1. 引用块 (> ...) 中的文字
    2. 行内全角引号 "…" 中的文字（≥8字）
    """
    quotes = []
    lines = md_text.split("\n")

    # 1. 引用块：连续 > 行合并
    blockquote_buf = []
    blockquote_start = 0

    def flush_blockquote(buf, start):
        if not buf:
            return
        merged = " ".join(buf)
        # 去掉 PN 引注行（如 （068-007））
        merged = re.sub(r"（\d{3}-\d{3}）", "", merged).strip()
        quotes.append({"raw": merged, "line_no": start, "quote_type": "blockquote"})

    for i, line in enumerate(lines):
        stripped = line.lstrip()
        if stripped.startswith(">"):
            content = stripped[1:].strip()
            content = re.sub(r"\*+", "", content).strip()
            if content:
                if not blockquote_buf:
                    blockquote_start = i + 1
                blockquote_buf.append(content)
        else:
            flush_blockquote(blockquote_buf, blockquote_start)
            blockquote_buf = []

    flush_blockquote(blockquote_buf, blockquote_start)

    # 过滤：blockquote 只验证含引号的直接引语
    quote_re = re.compile(r'[""「『]')
    quotes = [q for q in quotes
              if q["quote_type"] != "blockquote" or quote_re.search(q["raw"])]

    # 2. 行内全角引号 "…"
    inline_pattern = re.compile(r'["“]([^”"]{8,})["”]')
    for i, line in enumerate(lines):
        if line.startswith("---") or line.startswith("#"):
            continue
        for m in inline_pattern.finditer(line):
            quotes.append({
                "raw": m.group(1),
                "line_no": i + 1,
                "quote_type": "inline_quote"
            })

    return quotes


def normalize(text: str) -> str:
    """
    标准化文本，用于模糊匹配：
    - 去空格/换行
    - 去 PN 引用标记 (093-005)
    - 去所有标点，只保留汉字和字母数字
    """
    text = re.sub(r"\s+", "", text)
    text = re.sub(r"（\d{3}-\d{3,4}[^）]*）", "", text)
    text = re.sub(r"\(\d{3}-\d{3,4}[^)]*\)", "", text)
    text = re.sub(r"[^一-鿿\w]", "", text)
    return text


def verify_quote(fragment: str, corpus: str) -> bool:
    """
    在原文中查找片段。策略（依次）：
    1. 精确匹配
    2. 标准化后匹配
    3. 滑动窗口：8字子串，≥所需命中数即通过
    """
    if fragment in corpus:
        return True

    norm_frag = normalize(fragment)
    norm_corp = normalize(corpus)
    if len(norm_frag) >= MIN_FRAGMENT_LEN and norm_frag in norm_corp:
        return True

    # 滑动窗口：8字子串
    window = 8
    step = 4
    hits = 0
    needed = max(1, len(norm_frag) // 20)
    for i in range(0, len(norm_frag) - window + 1, step):
        sub = norm_frag[i:i + window]
        if sub in norm_corp:
            hits += 1
            if hits >= needed:
                return True
    return False


def check_page(page_path: Path, corpus: str, verbose: bool = True) -> list[dict]:
    """检查单个页面，返回 issues 列表。"""
    md_text = page_path.read_text(encoding="utf-8")
    page_id = page_path.stem
    quotes = extract_quotes(md_text)
    issues = []

    for q in quotes:
        fragments = clean_fragment(q["raw"])
        for frag in fragments:
            if len(frag) < MIN_FRAGMENT_LEN:
                continue
            found = verify_quote(frag, corpus)
            if not found:
                issue = {
                    "ts": datetime.now().isoformat(timespec="seconds"),
                    "page": page_id,
                    "issue_type": "FABRICATED_QUOTE",
                    "severity": "critical",
                    "content": frag,
                    "line_no": q["line_no"],
                    "quote_type": q["quote_type"],
                    "grep_result": "not_found",
                    "action": "delete_and_replace",
                    "status": "open",
                }
                issues.append(issue)
                if verbose:
                    print(f"  ❌ [{q['line_no']}] NOT FOUND: {frag[:50]}…")
            else:
                if verbose:
                    print(f"  ✅ [{q['line_no']}] ok: {frag[:40]}…")

    return issues


def fix_critical(page_path: Path, issues: list[dict]) -> int:
    """
    自动修复 critical 问题：
    - 删除无法溯源的引文行
    - 在删除位置插入占位符
    """
    if not issues:
        return 0

    md_text = page_path.read_text(encoding="utf-8")
    lines = md_text.split("\n")
    fixed_count = 0

    bad_line_nos = sorted({iss["line_no"] for iss in issues}, reverse=True)

    for line_no in bad_line_nos:
        idx = line_no - 1
        if 0 <= idx < len(lines):
            original_line = lines[idx]
            lines[idx] = f"<!-- [W6质检删除] 原文无法溯源，内容：{original_line.strip()[:60]} -->"
            fixed_count += 1

    result = "\n".join(lines)
    page_path.write_text(result, encoding="utf-8")
    print(f"  🔧 已修复 {fixed_count} 处")

    # 写入修订记录
    slug = page_path.stem
    summary = f"W6质检/fix-critical: 删除 {fixed_count} 处无法溯源引文"
    try:
        subprocess.run(
            [sys.executable, str(RECORD_REV), slug, "--summary", summary, "--author", "butler"],
            check=True, capture_output=True, text=True,
            cwd=REPO_ROOT,
        )
        print(f"  📝 修订记录已写入")
    except subprocess.CalledProcessError as e:
        print(f"  ⚠️  record_revision 失败: {e.stderr.strip()}")

    return fixed_count


def append_issues_log(issues: list[dict]):
    if not issues:
        return
    ISSUES_LOG.parent.mkdir(parents=True, exist_ok=True)
    with ISSUES_LOG.open("a", encoding="utf-8") as f:
        for iss in issues:
            f.write(json.dumps(iss, ensure_ascii=False) + "\n")


def get_featured_pages() -> list[Path]:
    result = []
    for md in sorted(PAGES_DIR.rglob("*.md")):
        text = md.read_text(encoding="utf-8")
        if re.search(r"^featured:\s*true", text, re.MULTILINE):
            result.append(md)
    return result


def main():
    parser = argparse.ArgumentParser(description="Butler W6 引文溯源质检")
    parser.add_argument("pages", nargs="*", help="页面路径")
    parser.add_argument("--all", action="store_true", help="检查所有页面")
    parser.add_argument("--featured", action="store_true", help="只检查精品页（featured:true）")
    parser.add_argument("--fix-critical", action="store_true", help="自动修复 critical 问题")
    parser.add_argument("--quiet", action="store_true", help="不打印每条验证结果")
    args = parser.parse_args()

    print("⏳ 加载资治通鉴原文…")
    corpus = load_corpus()
    print(f"✅ 原文已加载，共 {len(corpus):,} 字符\n")

    if args.featured:
        pages = get_featured_pages()
        print(f"📋 精品页：{len(pages)} 个\n")
    elif args.all:
        pages = [p for p in sorted(PAGES_DIR.rglob("*.md"))
                 if not p.stem.startswith("Special")]
        print(f"📋 全部页面：{len(pages)} 个\n")
    elif args.pages:
        pages = [Path(p) for p in args.pages]
    else:
        parser.print_help()
        sys.exit(0)

    total_issues = []
    for page_path in pages:
        if not page_path.exists():
            print(f"⚠️  文件不存在：{page_path}")
            continue
        print(f"🔍 检查 {page_path.stem}")
        issues = check_page(page_path, corpus, verbose=not args.quiet)
        if args.fix_critical and issues:
            fix_critical(page_path, issues)
        total_issues.extend(issues)
        if issues:
            print(f"  → {len(issues)} 个问题\n")
        else:
            print(f"  → ✅ 通过\n")

    append_issues_log(total_issues)

    critical = [i for i in total_issues if i["severity"] == "critical"]
    print("=" * 60)
    print(f"📊 检查完成：{len(pages)} 页，{len(total_issues)} 个问题（{len(critical)} critical）")
    if total_issues:
        print(f"📄 问题已写入 {ISSUES_LOG.relative_to(REPO_ROOT)}")
    if critical:
        print("\n⚠️  Critical 问题列表：")
        for iss in critical:
            print(f"  [{iss['page']}:{iss['line_no']}] {iss['content'][:60]}")
        print(f"\n提示：运行 --fix-critical 自动修复上述内容")


if __name__ == "__main__":
    main()
