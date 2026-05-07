#!/usr/bin/env python3
"""
bulk_wikilink.py — Add [[wikilink]] to all entity pages.

For each non-chapter page, scans body text for known entity labels/aliases
(from the registry) and wraps them in [[wikilinks]].

Rules:
  - Preserves frontmatter, blockquotes, headings, existing [[wikilinks]]
  - Longest-match-first to avoid partial overlaps
  - No self-links (links from a page to its own label)
  - No single-character terms (len<2)
  - Skips body after "## 参见" / "## 相关词条"
  - Writes directly, records revision, rebuilds registry once at end

Usage:
    python3 wiki/scripts/butler/bulk_wikilink.py [--dry-run] [--limit N]
    python3 wiki/scripts/butler/bulk_wikilink.py --since HEAD~5
    python3 wiki/scripts/butler/bulk_wikilink.py --since HEAD
"""

import json, re, subprocess, sys, time
from pathlib import Path

ROOT = Path("/home/baojie/work/knowledge/tongjian")
PAGES = ROOT / "wiki/public/pages"
REG_PATH = ROOT / "wiki/public/pages.json"
RECORD_REVISION = ROOT / "wiki/scripts/record_revision.py"
BUILD_REGISTRY = ROOT / "wiki/scripts/build_registry.py"


# ── 1. Load registry ──
data = json.loads(REG_PATH.read_text(encoding="utf-8"))
all_pages = data["pages"]

# ── 2. Build global term→slug map (exclude chapter pages, len<2) ──
term_to_slug = {}
for slug, meta in all_pages.items():
    if meta.get("type") == "chapter":
        continue
    label = meta.get("label", slug)
    if len(label) >= 2:
        term_to_slug[label] = slug
    for alias in meta.get("aliases", []):
        if len(alias) >= 2:
            term_to_slug[alias] = slug

terms = sorted(term_to_slug.keys(), key=len, reverse=True)

# ── 3. Compile regex patterns ──
LINK_PATTERN = re.compile("|".join(re.escape(t) for t in terms))
EXISTING_LINK = re.compile(r"\[\[([^\]]+)\]\]")
HEADING = re.compile(r"^#{1,6}(?:\s|$)")
SEE_ALSO = re.compile(r"^## (参见|相关词条)$")


def _link_text(text, page_slug):
    """Add [[wikilinks]] to a text segment with no existing wikilinks."""
    if not text.strip():
        return text

    parts = []
    last_end = 0

    for m in LINK_PATTERN.finditer(text):
        start, end = m.start(), m.end()
        if start > last_end:
            parts.append(text[last_end:start])

        matched = m.group(0)
        target = term_to_slug.get(matched)

        # Skip self-links (link from a page to itself)
        if target and target != page_slug:
            if target == matched:
                parts.append(f"[[{matched}]]")
            else:
                parts.append(f"[[{target}|{matched}]]")
        else:
            parts.append(matched)

        last_end = end

    if last_end < len(text):
        parts.append(text[last_end:])
    return "".join(parts)


def add_wikilinks(content, page_slug):
    """Add [[wikilinks]] to page body text, preserving structure.

    Returns (new_content, changed_bool).
    """
    fm_match = re.match(r"^(---.*?---)\n", content, re.DOTALL)
    if not fm_match:
        return content, False

    body_start = fm_match.end()  # right after frontmatter's trailing \n
    body = content[body_start:]

    lines = body.split("\n")
    new_lines = []
    changed = False
    in_see_also = False  # skip wikilinks after "## 参见" / "## 相关词条"
    in_semantic_block = False  # skip wikilinks inside ::: blocks (infobox/query/meta)

    for line in lines:
        stripped = line.strip()

        # Toggle ::: block mode — these blocks contain YAML, not body text
        if stripped.startswith(":::"):
            in_semantic_block = not in_semantic_block
            new_lines.append(line)
            continue

        if in_semantic_block:
            new_lines.append(line)
            continue

        # Detect end of wikilink zone
        if SEE_ALSO.match(stripped):
            in_see_also = True
            new_lines.append(line)
            continue

        if in_see_also:
            new_lines.append(line)
            continue

        # Blockquote → skip entirely (surface form preservation)
        if stripped.startswith(">"):
            new_lines.append(line)
            continue

        # Heading → skip (no wikilinks in headings)
        if HEADING.match(line):
            new_lines.append(line)
            continue

        # Regular text → protect existing wikilinks, link new terms
        new_line = _wikilink_line(line, page_slug)
        if new_line != line:
            changed = True
        new_lines.append(new_line)

    if not changed:
        return content, False

    # Preserve original byte-exact structure: replace body portion only
    new_body = "\n".join(new_lines)
    new_content = content[:body_start] + new_body
    return new_content, True


def _wikilink_line(line, page_slug):
    """Add wikilinks preserving existing [[wikilinks]]."""
    parts = []
    last_end = 0
    for m in EXISTING_LINK.finditer(line):
        before = line[last_end : m.start()]
        if before:
            parts.append(_link_text(before, page_slug))
        parts.append(m.group(0))
        last_end = m.end()

    after = line[last_end:]
    if after:
        parts.append(_link_text(after, page_slug))
    return "".join(parts)


def get_changed_since(commit):
    """Get list of entity page slugs modified since a commit."""
    # wiki/public → docs/wiki (canonical path for git)
    r = subprocess.run(
        ["git", "diff", "--name-only", commit, "--", "docs/wiki/pages/*.md"],
        capture_output=True, text=True, cwd=ROOT,
    )
    if r.returncode != 0:
        print(f"  ⚠ git diff failed: {r.stderr.strip()[:100]}", file=sys.stderr)
        return None

    changed = []
    for line in r.stdout.splitlines():
        p = Path(line)
        if p.suffix != ".md":
            continue
        slug = p.stem
        meta = all_pages.get(slug)
        if meta and meta.get("type") != "chapter":
            changed.append(slug)
    return changed


def main():
    dry_run = "--dry-run" in sys.argv
    limit = None
    since = None
    for i, arg in enumerate(sys.argv):
        if arg == "--limit" and i + 1 < len(sys.argv):
            limit = int(sys.argv[i + 1])
        if arg == "--since" and i + 1 < len(sys.argv):
            since = sys.argv[i + 1]

    # Determine slugs to process
    if since:
        slugs = get_changed_since(since)
        if slugs is None:
            sys.exit(1)
        if not slugs:
            print(f"[wikilink] No changed entity pages since {since}", file=sys.stderr)
            return
        print(f"[wikilink] {len(slugs)} entity pages changed since {since}", file=sys.stderr)
    else:
        slugs = [s for s, m in all_pages.items() if m.get("type") != "chapter"]
        if limit:
            slugs = slugs[:limit]

    print(f"[wikilink] Loaded {len(term_to_slug)} terms from {len(all_pages)} pages", file=sys.stderr)
    print(f"[wikilink] Processing {len(slugs)} entity pages"
          f"{' (DRY RUN)' if dry_run else ''}...", file=sys.stderr)

    modified = 0
    total_added = 0
    failed = 0
    t0 = time.time()

    for i, slug in enumerate(slugs):
        path = PAGES / f"{slug}.md"
        if not path.exists():
            continue

        original = path.read_text(encoding="utf-8")
        new_content, changed = add_wikilinks(original, slug)

        if not changed:
            continue

        old_count = len(EXISTING_LINK.findall(original))
        new_count = len(EXISTING_LINK.findall(new_content))
        added = new_count - old_count

        if added < 0:
            continue  # should not happen

        if not dry_run:
            # Write directly (edit_page.py --enrich is correct but 1991× rebuild is too slow)
            path.write_text(new_content, encoding="utf-8")

            # Verify: re-read and compare
            verify = path.read_text(encoding="utf-8")
            if verify != new_content:
                print(f"  ⚠ VERIFY {slug}: mismatch after write, retrying...", file=sys.stderr)
                path.write_text(new_content, encoding="utf-8")
                verify = path.read_text(encoding="utf-8")
                if verify != new_content:
                    print(f"  ✗ FAIL {slug}: content mismatch after retry", file=sys.stderr)
                    failed += 1
                    continue

            # Record revision
            r = subprocess.run(
                [sys.executable, str(RECORD_REVISION), slug,
                 "--summary", "添加 wikilinks: 自动匹配已知词条",
                 "--author", "butler"],
                capture_output=True, text=True, cwd=ROOT,
            )
            if r.returncode != 0:
                print(f"  ✗ FAIL {slug}: {r.stderr.strip()[:100]}", file=sys.stderr)
                failed += 1
                continue

        modified += 1
        total_added += added

        if (i + 1) % 100 == 0:
            elapsed = time.time() - t0
            rate = (i + 1) / elapsed if elapsed > 0 else 1
            eta = (len(slugs) - i - 1) / rate if rate > 0 else 0
            print(f"  [{i+1}/{len(slugs)}] {modified} modified, "
                  f"{total_added} links added, ~{eta:.0f}s left"
                  f"{' (dry-run)' if dry_run else ''}",
                  file=sys.stderr)

    elapsed = time.time() - t0

    # Rebuild registry once at the end (not in dry-run)
    if not dry_run and modified > 0:
        print(f"  Rebuilding registry...", file=sys.stderr)
        r = subprocess.run(
            [sys.executable, str(BUILD_REGISTRY), str(PAGES),
             "--out", str(ROOT / "wiki/public/pages.json"),
             "--out-lite", str(ROOT / "wiki/public/pages.lite.json")],
            capture_output=True, text=True, cwd=ROOT,
        )
        if r.returncode == 0:
            print(f"  ✓ pages.json + pages.lite.json updated", file=sys.stderr)
        else:
            print(f"  ⚠ pages.json update failed: {r.stderr.strip()[:200]}", file=sys.stderr)

    print(f"[wikilink] Done: {modified}/{len(slugs)} modified, "
          f"{total_added} links added, "
          f"{failed} failures, {elapsed:.1f}s",
          file=sys.stderr)

    if dry_run:
        print(f"DRY-RUN: {modified} pages would get {total_added} new wikilinks")
    else:
        print(f"COMPLETED: {modified} pages updated with {total_added} new wikilinks")


if __name__ == "__main__":
    main()
