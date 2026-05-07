#!/usr/bin/env python3
"""
Batch page creator: Generate multiple wiki pages from a JSON entity list.
Each page gets: frontmatter, brief content from corpus search, PN citations.

Usage:
  python3 wiki/scripts/butler/batch_create.py entities.json [--dry-run]
  python3 wiki/scripts/butler/batch_create.py entities.json [--resume SLUG]

Input JSON format:
  [
    {
      "slug": "骨牌",
      "type": "game",
      "tags": ["游戏", "文化"],
      "description": "《资治通鉴》中记载的重要概念",
      "aliases": ["牙牌"],
      "corpus_terms": ["骨牌"]
    }
  ]
"""
import json, os, subprocess, sys, re, tempfile, time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
ADD_PAGE = ROOT / "wiki/scripts/add_page.py"
CORPUS_SEARCH = ROOT / "wiki/scripts/butler/corpus_search.py"

CORPUS_CACHE = {}

def search_corpus(term, max_results=5):
    """Search corpus and return list of (pn, snippet) tuples."""
    if term in CORPUS_CACHE:
        return CORPUS_CACHE[term]
    result = subprocess.run(
        [sys.executable, str(CORPUS_SEARCH), term, "--max", str(max_results)],
        capture_output=True, text=True, cwd=ROOT
    )
    snippets = result.stdout.strip().split('\n') if result.stdout.strip() else []
    parsed = []
    for s in snippets:
        if not s.strip():
            continue
        m = re.match(r'（(\d{3}-\d{3})）', s.strip())
        if m:
            text = s.strip()[len(m.group(0)):]
            text = re.sub(r'【[^】]+】', '', text)  # Remove search markers
            text = text.strip('… ')
            # Keep max 100 chars after PN
            text = text[:100]
            parsed.append((m.group(1), text))
    CORPUS_CACHE[term] = parsed
    return parsed

def generate_frontmatter(entity):
    """Generate YAML frontmatter string."""
    tags_str = ', '.join(f'[{t}]' for t in entity.get('tags', []))
    aliases = entity.get('aliases', [])
    aliases_str = ', '.join(f'[{a}]' for a in aliases)

    lines = ['---']
    lines.append(f'id: {entity["slug"]}')
    lines.append(f'type: {entity.get("type", "概念")}')
    lines.append(f'label: {entity["slug"]}')
    if aliases:
        lines.append(f'aliases: [{aliases_str}]')
    lines.append(f'tags: [{tags_str}]')
    lines.append(f'description: {entity.get("description", entity["slug"])}')
    lines.append('quality: basic')
    lines.append('---')
    return '\n'.join(lines)

def generate_content(entity):
    """Generate page body content with PN citations."""
    terms = entity.get('corpus_terms', [entity['slug']])
    all_hits = []
    for term in terms:
        all_hits.extend(search_corpus(term, max_results=5))

    # Deduplicate by PN
    seen_pn = set()
    unique_hits = []
    for pn, text in all_hits:
        if pn not in seen_pn:
            seen_pn.add(pn)
            unique_hits.append((pn, text))

    lines = [f'# {entity["slug"]}', '']

    desc = entity.get('description', '')
    if desc:
        lines.append(f'{desc}')
        lines.append('')

    if unique_hits:
        lines.append('## 原文引用')
        lines.append('')
        for pn, text in unique_hits[:5]:
            lines.append(f'> {text}')
            lines.append(f'> （{pn}）')
            lines.append('')

    lines.append('## 参见')
    lines.append('')

    raw = '\n'.join(lines)
    raw = _fix_empty_brackets(raw, entity, unique_hits)
    return raw

def create_page(entity, dry_run=False):
    """Create a single wiki page."""
    slug = entity['slug']
    page_path = ROOT / "wiki/public/pages" / f"{slug}.md"

    if page_path.exists():
        return f"EXISTS: {slug}"

    content = generate_frontmatter(entity) + '\n\n' + generate_content(entity)

    if dry_run:
        print(f"[DRY-RUN] Would create: {slug} ({entity.get('type', '概念')})")
        return f"DRY-RUN: {slug}"

    # Create via stdin
    result = subprocess.run(
        [sys.executable, str(ADD_PAGE), slug, "-",
         "--summary", f"新建«{slug}»词条",
         "--author", "butler"],
        input=content, capture_output=True, text=True, cwd=ROOT
    )

    if result.returncode == 0:
        return f"OK: {slug}"
    else:
        err = result.stderr.strip()
        if "already exists" in err:
            return f"EXISTS: {slug}"
        return f"FAIL: {slug} - {err}"

def _find_missing_in_corpus(corpus_raw, open_b, close_b, prefix):
    """在 corpus 原文中查找空括号内缺失的文字。

    尝试多种匹配策略以降噪（如 blockquote → 前缀、AI 额外删损）：
      1. 去除 `> ` 前缀后匹配
      2. 取前缀末 2 字
      3. 取前缀末 1 字
    """
    candidates = []
    raw = prefix.lstrip('> ').strip()
    if raw:
        candidates.append(raw)
    if len(prefix) >= 2:
        candidates.append(prefix[-2:].strip())
    if prefix:
        candidates.append(prefix[-1])

    for ctx in candidates:
        if not ctx or ctx not in corpus_raw:
            continue
        pos = corpus_raw.find(ctx)
        if pos < 0:
            continue
        after = corpus_raw[pos + len(ctx):]
        if after.startswith(open_b):
            inner_end = after.find(close_b, len(open_b))
            if inner_end > len(open_b):
                return after[len(open_b):inner_end]
    return None


def _fix_empty_brackets(content, entity, corpus_hits):
    """修补引文中 AI 剥离自身词条名后遗留的空括号/引号。

    但以尔 AI 在生成页面时，常因避自链之讳，将括号内与页面同名文字径行削去，
    徒留《》《「」「『』」「‘’」「“”」》之空壳。此函数借 corpus 原文比对，
    将所缺文字补归原位。

    Bracket pairs checked: 《》 「」 『』 ‘’ “”
    """
    label = entity.get('label', entity['slug'])
    bracket_pairs = [
        ('《', '》'),  # 《》
        ('「', '」'),  # 「」
        ('『', '』'),  # 『』
        ('‘', '’'),  # ‘’
        ('“', '”'),  # ""
    ]
    bracket_pairs.append(('"', '"'))  # ASCII quotes

    # Build a combined raw text from corpus hits for lookup
    corpus_raw = ' '.join(t for _, t in corpus_hits)
    corpus_raw = re.sub(r'【[^】]+】', '', corpus_raw)

    fixed = content
    for open_b, close_b in bracket_pairs:
        empty = f'{open_b}{close_b}'
        while True:
            idx = fixed.find(empty)
            if idx < 0:
                break
            ctx_start = max(0, idx - 30)
            prefix = fixed[ctx_start:idx]

            missing = _find_missing_in_corpus(corpus_raw, open_b, close_b, prefix)
            if missing:
                print(f"  ⚠ 修复空括号: 「{missing}」"
                      f"(来源: {entity['slug']})", file=sys.stderr)
            else:
                missing = (entity.get('corpus_terms') or [label])[0]
                print(f"  ⚠ 自动填充空括号(回退): 「{missing}」"
                      f"(来源: {entity['slug']})", file=sys.stderr)

            fixed = fixed[:idx] + open_b + missing + close_b + fixed[idx + 2:]

    return fixed


def main():
    import argparse
    ap = argparse.ArgumentParser(description="Batch create wiki pages")
    ap.add_argument("json_file", help="JSON file with entity list")
    ap.add_argument("--dry-run", action="store_true", help="Don't actually create")
    ap.add_argument("--resume", help="Resume from this slug (skip earlier)")
    args = ap.parse_args()

    with open(args.json_file, 'r') as f:
        entities = json.load(f)

    results = {"ok": 0, "exists": 0, "fail": [], "skip": 0}
    resumed = args.resume is None

    for entity in entities:
        slug = entity['slug']
        if not resumed:
            if slug == args.resume:
                resumed = True
            else:
                results["skip"] += 1
                continue

        status = create_page(entity, dry_run=args.dry_run)
        if status.startswith("OK:"):
            results["ok"] += 1
            print(f"  ✓ {slug}")
        elif status.startswith("EXISTS:"):
            results["exists"] += 1
            print(f"  - {slug} (exists)")
        else:
            results["fail"].append(slug)
            print(f"  ✗ {status}")

        # Small delay to avoid overwhelming the system
        if results["ok"] % 5 == 0 and not args.dry_run:
            time.sleep(0.5)

    print(f"\nResults: {results['ok']} created, {results['exists']} existed, "
          f"{len(results['fail'])} failed, {results['skip']} skipped")
    return 0 if not results['fail'] else 1

if __name__ == "__main__":
    sys.exit(main())
