"""Build full-text search index from chapter pages for client-side FTS."""
import os
import re
import json
from pathlib import Path

_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
_REPO_ROOT = os.path.dirname(os.path.dirname(_SCRIPT_DIR))
pages_dir = Path(_REPO_ROOT) / "wiki" / "public" / "pages"
out_dir = Path(_REPO_ROOT) / "wiki" / "public" / "data"
out_path = out_dir / "fts-index.json"


def strip_wikilinks(text):
    """Strip [[target]] -> target, [[target|display]] -> display."""
    return re.sub(r'\[\[([^\]|]+)(?:\|[^\]|]+)?\]\]', r'\1', text)


def parse_frontmatter(content):
    """Parse YAML frontmatter from markdown content."""
    fm = {}
    m = re.match(r'^---\s*\n(.*?)\n---', content, re.DOTALL)
    if m:
        for line in m.group(1).split('\n'):
            if ':' in line:
                key, _, val = line.partition(':')
                fm[key.strip()] = val.strip()
    return fm


def parse_paragraphs(content):
    """Extract PN paragraphs from chapter content.

    Returns list of (pn_id, text) tuples.
    """
    # Skip frontmatter
    rest = content
    m = re.match(r'^---\s*\n.*?\n---', rest, re.DOTALL)
    if m:
        rest = rest[m.end():]

    paragraphs = []
    # Pattern: [NNN-PPP] text
    # Skip heading lines (# ...)
    lines = rest.split('\n')
    current_pn = None
    current_text = []

    for line in lines:
        # Skip headings
        if line.startswith('#'):
            continue
        # Check for PN marker at start of line
        pn_match = re.match(r'^\[(\d{3}-\d{3})\]\s*(.*)', line)
        if pn_match:
            # Save previous paragraph if any
            if current_pn is not None and current_text:
                text = ''.join(current_text).strip()
                if text:
                    paragraphs.append((current_pn, text))
            current_pn = pn_match.group(1)
            current_text = [pn_match.group(2)]
        elif current_pn is not None and line.strip():
            current_text.append(line.strip())

    # Save last paragraph
    if current_pn is not None and current_text:
        text = ''.join(current_text).strip()
        if text:
            paragraphs.append((current_pn, text))

    return paragraphs


def process_chapter(content):
    """Process a chapter page and return (chapter_info, entries)."""
    fm = parse_frontmatter(content)
    chapter_num = int(fm.get('vol_num', fm.get('chapter_num', 0)))
    chapter_title = fm.get('vol_title', fm.get('chapter_title', ''))
    chapter_id = fm.get('id', '')

    paragraphs = parse_paragraphs(content)

    entries = []
    for pn, raw_text in paragraphs:
        clean = strip_wikilinks(raw_text).strip()
        if clean:
            entries.append({
                "c": chapter_num - 1,  # 0-indexed
                "p": pn,
                "x": clean
            })

    chapter_info = {
        "n": chapter_num,
        "f": chapter_id,
        "t": chapter_title
    }

    return chapter_info, entries


def main():
    chapters = []
    all_entries = []
    chapter_set = set()

    for fpath in sorted(pages_dir.rglob("*.md")):
        if fpath.is_dir():
            continue
        content = fpath.read_text(encoding="utf-8")

        fm = parse_frontmatter(content)
        if fm.get('type') != '章节':
            continue

        try:
            chap_info, entries = process_chapter(content)
            if chap_info["n"] in chapter_set:
                continue  # dedup
            chapter_set.add(chap_info["n"])
            chapters.append(chap_info)
            all_entries.extend(entries)
        except Exception as e:
            print(f"  Error processing {fname}: {e}")

    # Sort chapters by number
    chapters.sort(key=lambda c: c["n"])

    index = {
        "chapters": chapters,
        "entries": all_entries
    }

    out_dir.mkdir(parents=True, exist_ok=True)
    out_path.write_text(
        json.dumps(index, ensure_ascii=False, separators=(',', ':')),
        encoding="utf-8",
    )

    print(f"Chapters: {len(chapters)}")
    print(f"Entries: {len(all_entries)}")
    print(f"Output: {out_path}")
    size = os.path.getsize(out_path)
    size = out_path.stat().st_size
    print(f"Size: {size:,} bytes ({size/1024:.0f} KB)")


if __name__ == '__main__':
    main()
