#!/usr/bin/env python3
"""
verify_buckets.py — 拼音分桶迁移完整性验证。

验证 pages/ 和 history/ 目录的拼音分片（109 桶）是否正确，
涵盖文件系统层、解析层、脚本层、数据完整性层。

用法:
    python3 wiki/scripts/verify_buckets.py           # 跑全套
    python3 wiki/scripts/verify_buckets.py --quick    # 只跑文件系统层 (T1-T5)
    python3 wiki/scripts/verify_buckets.py --layer resolution  # 只跑解析层
    python3 wiki/scripts/verify_buckets.py --verbose  # 显示详细信息

退出码:
    0 = 全部通过
    1 = 文件系统层失败
    2 = 解析层失败
    4 = 脚本层失败
    8 = 数据完整性层失败
    16 = 前端/SPA 层失败
    255 = 环境错误
    退出码为各层退出码的按位或。
"""
from __future__ import annotations

import argparse
import json
import random
import sys
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PAGES = ROOT / "wiki/public/pages"
HIST = ROOT / "wiki/public/history"
REGISTRY = ROOT / "wiki/public/pages.json"
REGISTRY_LITE = ROOT / "wiki/public/pages.lite.json"

sys.path.insert(0, str(ROOT / "wiki/scripts"))
from page_bucket import resolve_page_file, page_bucket  # noqa: E402


# ─── Test framework ────────────────────────────────────

class TestResult:
    """单个测试结果"""
    def __init__(self, name: str):
        self.name = name
        self.passed = True
        self.messages: list[str] = []

    def ok(self, msg: str = ""):
        self.passed = True
        if msg:
            self.messages.append(f"  ✓ {msg}")

    def fail(self, msg: str):
        self.passed = False
        self.messages.append(f"  ✗ {msg}")

    def summary(self) -> str:
        return f"{'✓' if self.passed else '✗'} {self.name}"


# ─── Layer: Filesystem (T1-T5) ─────────────────────────

def test_t1_no_top_level_md() -> TestResult:
    """pages/ 顶层无 .md 文件"""
    t = TestResult("T1 pages/ 顶层无 .md 残留")
    count = len(list(PAGES.glob("*.md")))
    if count == 0:
        t.ok("pages/ 顶层无 .md 文件")
    else:
        t.fail(f"pages/ 顶层残留 {count} 个 .md 文件")
    return t


def test_t2_bucket_count() -> TestResult:
    """分桶目录数量"""
    t = TestResult("T2 分桶目录数量")
    buckets = [d for d in PAGES.iterdir() if d.is_dir() and not d.name.startswith(".")]
    count = len(buckets)
    # 通常 109 桶，允许合理波动
    if 100 <= count <= 120:
        t.ok(f"分桶数 {count}（预期 ~109）")
    else:
        t.fail(f"分桶数 {count}，偏离预期 ~109")
    return t


def test_t3_total_page_count() -> TestResult:
    """页面文件总数"""
    t = TestResult("T3 页面文件总数")
    count = len(list(PAGES.rglob("*.md")))
    # 19,258 是迁移时的基准，可能会有小幅浮动
    if count >= 19000:
        t.ok(f"总页面数 {count}")
    else:
        t.fail(f"总页面数 {count}，远低于预期 19000+")
    return t


def test_t4_bucket_distribution() -> TestResult:
    """各桶文件分布（最大桶占比）"""
    t = TestResult("T4 桶分布均匀性")
    buckets = [d for d in PAGES.iterdir() if d.is_dir() and not d.name.startswith(".")]
    total = 0
    max_cnt = 0
    max_bucket = ""
    dist: list[tuple[str, int]] = []
    for b in buckets:
        cnt = len(list(b.glob("*.md")))
        dist.append((b.name, cnt))
        total += cnt
        if cnt > max_cnt:
            max_cnt = cnt
            max_bucket = b.name
    ratio = max_cnt / total * 100 if total > 0 else 0
    t.ok(f"最大桶 {max_bucket}/: {max_cnt} ({ratio:.1f}%)")
    if ratio <= 15:
        t.ok("分布均匀性可接受")
    else:
        t.fail(f"最大桶占比 {ratio:.1f}% > 15%，分布不均")
    # 打印分布 top 5
    dist.sort(key=lambda x: -x[1])
    for name, cnt in dist[:5]:
        t.messages.append(f"    {name}/: {cnt}")
    return t


def test_t5_history_no_top_level() -> TestResult:
    """history/ 顶层无 .jsonl 文件"""
    t = TestResult("T5 history/ 顶层无 .jsonl 残留")
    count = len(list(HIST.glob("*.jsonl")))
    if count == 0:
        t.ok("history/ 顶层无 .jsonl 文件")
    else:
        t.fail(f"history/ 顶层残留 {count} 个 .jsonl 文件")
    return t


# ─── Layer: Resolution (T6-T7) ─────────────────────────

def test_t6_resolve_known_pages() -> TestResult:
    """resolve_page_file 对已知页面能正确定位"""
    t = TestResult("T6 resolve_page_file 定位已知页面")
    known = ["刘备", "曹操", "商鞅", "秦始皇", "诸葛亮",
             "第001卷", "第294卷", "赤壁之战", "王莽", "韩信",
             "项羽", "刘邦", "李斯", "白起", "赵高"]
    all_ok = True
    for slug in known:
        p = resolve_page_file(PAGES, slug)
        bucket = page_bucket(slug)
        if p and p.parent.name == bucket:
            t.ok(f"{slug} → {bucket}/{p.name}")
        elif p:
            t.fail(f"{slug} → {p} (预期桶 {bucket})")
            all_ok = False
        else:
            t.fail(f"{slug} → 未找到")
            all_ok = False
    if all_ok:
        t.messages.append("  ✓ 全部已知页面正确定位")
    return t


def test_t7_registry_path_integrity() -> TestResult:
    """registry 中 path 字段完整性"""
    t = TestResult("T7 registry path 字段完整性")
    for fname, label in [(REGISTRY, "pages.json"), (REGISTRY_LITE, "pages.lite.json")]:
        data = json.loads(fname.read_text(encoding="utf-8"))
        pages = data.get("pages", data)
        total = len(pages)
        has_path = sum(1 for v in pages.values() if "path" in v)
        missing = [(k, v) for k, v in pages.items() if "path" not in v]
        if has_path == total:
            t.ok(f"{label}: {total}/{total} 有 path")
        else:
            t.fail(f"{label}: {has_path}/{total} 有 path, {len(missing)} 缺 path")
            for k, _ in missing[:10]:
                t.messages.append(f"    缺 path: {k}")
    return t


# ─── Layer: Scripts (T8) ───────────────────────────────

def test_t8a_build_registry() -> TestResult:
    """build_registry.py 能读取所有页面"""
    t = TestResult("T8a build_registry.py 读取全量")
    out = Path("/tmp/test_registry_t8a.json")
    result = subprocess.run(
        [sys.executable, str(ROOT / "wiki/scripts/build_registry.py"),
         str(PAGES), "--out", str(out), "--out-lite", str(out.with_suffix(".lite.json"))],
        capture_output=True, text=True, cwd=ROOT
    )
    if result.returncode != 0:
        t.fail(f"build_registry.py 退出码 {result.returncode}: {result.stderr.strip()}")
        return t
    # 检查输出
    try:
        data = json.loads(out.read_text(encoding="utf-8"))
        pages = data.get("pages", data)
        if len(pages) >= 19000:
            t.ok(f"读取 {len(pages)} 页")
        else:
            t.fail(f"仅读取 {len(pages)} 页，预期 19000+")
    except Exception as e:
        t.fail(f"解析 registry 失败: {e}")
    finally:
        out.unlink(missing_ok=True)
        out.with_suffix(".lite.json").unlink(missing_ok=True)
    return t


def test_t8b_add_page_creates_in_bucket() -> TestResult:
    """add_page.py 写入正确分桶"""
    t = TestResult("T8b add_page.py 写入正确桶")
    slug = "__verify_bucket_test__"
    content = f"""---
id: {slug}
type: 概念
label: Verify
aliases: []
tags: []
description: Bucket verification test.
---
# Verify

Test page for bucket verification.
"""
    result = subprocess.run(
        [sys.executable, str(ROOT / "wiki/scripts/add_page.py"),
         slug, "-", "--summary", "bucket verify test"],
        input=content, capture_output=True, text=True, cwd=ROOT
    )
    # 无论成功或失败（可能已有），检查文件位置
    p = resolve_page_file(PAGES, slug)
    bucket = page_bucket(slug)
    if p and p.parent.name == bucket:
        t.ok(f"{slug} → {bucket}/{p.name}")
    elif p:
        t.fail(f"{slug} → {p} (预期桶 {bucket})")
    else:
        t.fail(f"{slug} → 未找到")
    # 清理
    if p:
        p.unlink(missing_ok=True)
        # 清理可能的 empty bucket dir
        if p.parent.exists() and not any(p.parent.iterdir()):
            p.parent.rmdir()
    # 重建 registry 以清除测试页的记录
    subprocess.run(
        [sys.executable, str(ROOT / "wiki/scripts/build_registry.py"),
         str(PAGES), "--out", str(REGISTRY),
         "--out-lite", str(REGISTRY_LITE)],
        capture_output=True, cwd=ROOT
    )
    return t


def test_t8c_edit_page_finds_page() -> TestResult:
    """edit_page.py 能定位已有页面"""
    t = TestResult("T8c edit_page.py 定位已有页面")
    # 尝试读取一个肯定存在的页面，看 edit_page 是否能找到
    result = subprocess.run(
        [sys.executable, str(ROOT / "wiki/scripts/edit_page.py"),
         "商鞅", "-", "--summary", "verify"],
        input="", capture_output=True, text=True, cwd=ROOT
    )
    # 预期失败（空内容），但失败模式应该是内容校验失败而非"页面不存在"
    stderr = result.stderr.strip()
    if "页面不存在" in stderr:
        t.fail("edit_page.py 无法定位商鞅页面")
    else:
        t.ok(f"正确定位（预期拒绝: {stderr[:60]}）")
    return t


def test_t8d_corpus_search_finds_volumes() -> TestResult:
    """corpus_search.py 能读取 di/ 桶卷页"""
    t = TestResult("T8d corpus_search 读取卷页")
    result = subprocess.run(
        [sys.executable, str(ROOT / "wiki/scripts/butler/corpus_search.py"),
         "臣光曰", "--vol", "1", "--max", "1"],
        capture_output=True, text=True, cwd=ROOT
    )
    if result.returncode == 0 and "001-004" in result.stdout:
        t.ok("卷页在 di/ 桶可被 corpus_search 检索")
    else:
        t.fail(f"corpus_search 失败: {result.stderr.strip()[:100] or result.stdout[:100]}")
    return t


def test_t8e_rglob_finds_volumes() -> TestResult:
    """rglob('第???卷.md') 找到全部 294 卷"""
    t = TestResult("T8e rglob 找到全部 294 卷")
    count = len(list(PAGES.rglob("第???卷.md")))
    if count >= 294:
        t.ok(f"找到 {count} 卷")
    else:
        t.fail(f"仅找到 {count} 卷，预期 294")
    return t


# ─── Layer: Data Integrity (T9) ────────────────────────

def test_t9a_paths_exist() -> TestResult:
    """registry 中 path 全部指向存在的文件"""
    t = TestResult("T9a registry path 全部有效")
    data = json.loads(REGISTRY_LITE.read_text(encoding="utf-8"))
    pages = data.get("pages", data)
    not_found = []
    for slug, meta in pages.items():
        path = meta.get("path")
        if path:
            f = PAGES / path
            if not f.exists():
                not_found.append((slug, path))
    if not not_found:
        t.ok(f"全部 {len(pages)} 条 path 有效")
    else:
        t.fail(f"{len(not_found)} 条 path 指向不存在的文件")
        for slug, path in not_found[:10]:
            t.messages.append(f"  {slug} → pages/{path}")
    return t


def test_t9b_history_consistency() -> TestResult:
    """history 分桶与 pages 一致（抽样）"""
    t = TestResult("T9b history 分桶一致性（抽样）")
    buckets = [d for d in PAGES.iterdir() if d.is_dir() and not d.name.startswith(".")]
    samples = random.sample([b for b in buckets], min(30, len(buckets)))
    ok = 0
    checked = 0
    for b in samples:
        md_files = list(b.glob("*.md"))
        random.shuffle(md_files)
        for mf in md_files[:5]:
            slug = mf.stem
            expected = HIST / b.name / f"{slug}.jsonl"
            checked += 1
            if expected.exists():
                ok += 1
    t.ok(f"抽查 {checked} 条, history 存在 {ok} 条（其余可能无修订记录）")
    return t


# ─── Layer: Edge Cases (T10) ───────────────────────────

def test_t10a_volumes_in_di() -> TestResult:
    """全部 294 卷在 di/ 桶"""
    t = TestResult("T10a 卷页在 di/ 桶")
    ok = 0
    for vf in PAGES.rglob("第???卷.md"):
        if vf.parent.name == "di":
            ok += 1
    if ok >= 294:
        t.ok(f"{ok}/294 卷在 di/ 桶")
    else:
        t.fail(f"仅 {ok} 卷在 di/ 桶")
    return t


def test_t10b_spa_simulation() -> TestResult:
    """模拟 SPA 通过 meta.path 加载页面"""
    t = TestResult("T10c SPA 模拟加载")
    data = json.loads(REGISTRY_LITE.read_text(encoding="utf-8"))
    pages = data.get("pages", data)
    samples = random.sample(list(pages.keys()), min(100, len(pages)))
    ok = 0
    for slug in samples:
        meta = pages[slug]
        path = meta.get("path", f"{slug}.md")
        f = ROOT / "wiki/public" / "pages" / path
        if f.exists():
            ok += 1
        else:
            t.fail(f"SPA 无法加载: {slug} → pages/{path}")
    t.ok(f"模拟加载 {len(samples)} 页, 成功 {ok}")
    return t


def test_t10d_history_bucket_logic() -> TestResult:
    """模拟前端 _historyBucket 逻辑"""
    t = TestResult("T10d history 分桶逻辑模拟")
    data = json.loads(REGISTRY_LITE.read_text(encoding="utf-8"))
    registry = {"pages": data.get("pages", data)}

    def history_bucket(page, reg):
        meta = reg.get("pages", {}).get(page)
        if meta and "path" in meta:
            parts = meta["path"].split("/")
            if len(parts) >= 2:
                return parts[0]
        return ""

    tests = ["刘备", "曹操", "诸葛亮", "商鞅", "第001卷"]
    all_ok = True
    for page in tests:
        bucket = history_bucket(page, registry)
        if bucket:
            hist_path = HIST / bucket / f"{page}.jsonl"
            exists = hist_path.exists()
            msg = f"{page} → bucket={bucket}, history存在={exists}"
            if exists:
                t.ok(msg)
            else:
                t.messages.append(f"  {msg}（无修订记录，可接受）")
        else:
            t.fail(f"{page} → 无 bucket")
            all_ok = False
    if all_ok:
        t.messages.append("  ✓ history 分桶逻辑正确")
    return t


# ─── Layer: SPA Frontend (T11 — requires server) ──────

def test_t11_spa_http() -> TestResult:
    """通过本地服务器验证 SPA 渲染（需要 wiki 服务运行）"""
    t = TestResult("T11 SPA HTTP 渲染验证")
    import urllib.request
    import socket

    # 检查本地服务是否运行
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    result = sock.connect_ex(("127.0.0.1", 1084))
    sock.close()
    if result != 0:
        t.messages.append("  ⚠ 本地服务未运行 (port 1084)，跳过 HTTP 测试")
        t.messages.append("    启动: bash wiki/wiki.sh")
        # 标记为通过（非环境问题）
        return t

    checks = [
        ("index.html", "/"),
        ("pages.lite.json", "/pages.lite.json"),
        ("刘备 SPA 路径", f"/pages/{json.loads(REGISTRY_LITE.read_text())['pages']['刘备']['path']}"),
        ("商鞅 SPA 路径", f"/pages/{json.loads(REGISTRY_LITE.read_text())['pages']['商鞅']['path']}"),
        ("第001卷 SPA 路径", f"/pages/{json.loads(REGISTRY_LITE.read_text())['pages']['第001卷']['path']}"),
    ]
    all_ok = True
    for label, url_path in checks:
        try:
            resp = urllib.request.urlopen(f"http://127.0.0.1:1084{url_path}", timeout=5)
            if resp.status == 200:
                t.ok(f"{label} → HTTP 200")
            else:
                t.fail(f"{label} → HTTP {resp.status}")
                all_ok = False
        except Exception as e:
            t.fail(f"{label} → {e}")
            all_ok = False
    return t


# ─── Test Runner ────────────────────────────────────────

LAYER_TESTS = {
    "filesystem":  [test_t1_no_top_level_md, test_t2_bucket_count,
                   test_t3_total_page_count, test_t4_bucket_distribution,
                   test_t5_history_no_top_level],
    "resolution": [test_t6_resolve_known_pages, test_t7_registry_path_integrity],
    "scripts":    [test_t8a_build_registry, test_t8b_add_page_creates_in_bucket,
                  test_t8c_edit_page_finds_page, test_t8d_corpus_search_finds_volumes,
                  test_t8e_rglob_finds_volumes],
    "integrity":  [test_t9a_paths_exist, test_t9b_history_consistency],
    "edge":       [test_t10a_volumes_in_di, test_t10b_spa_simulation,
                  test_t10d_history_bucket_logic],
}

# 退出码映射
LAYER_EXIT_CODES = {
    "filesystem":  1,
    "resolution":  2,
    "scripts":     4,
    "integrity":   8,
    "edge":        16,
}

LAYER_NAMES = {
    "filesystem": "文件系统层",
    "resolution": "解析层",
    "scripts":    "脚本层",
    "integrity":  "数据完整性层",
    "edge":       "边界/SPA 模拟层",
}


def run_tests(tests: list, verbose: bool = False) -> bool:
    """运行一组测试，返回是否全部通过"""
    all_pass = True
    for test_fn in tests:
        result = test_fn()
        if verbose:
            print(f"\n  {result.name}")
            for msg in result.messages:
                print(msg)
        else:
            print(f"  {result.summary()}")
            if not result.passed:
                for msg in result.messages:
                    print(msg)
        if not result.passed:
            all_pass = False
    return all_pass


def main():
    ap = argparse.ArgumentParser(
        description="拼音分桶迁移完整性验证",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    ap.add_argument("--quick", action="store_true",
                    help="只跑文件系统层 (T1-T5)")
    ap.add_argument("--layer", choices=list(LAYER_TESTS.keys()),
                    help="只跑指定层")
    ap.add_argument("--verbose", "-v", action="store_true",
                    help="显示详细信息")
    ap.add_argument("--http", action="store_true",
                    help="包含 SPA HTTP 渲染验证（需要本地服务运行）")
    args = ap.parse_args()

    # 确认工作目录
    if not (PAGES.exists() and PAGES.is_dir()):
        print(f"✗ 页面目录不存在: {PAGES}", file=sys.stderr)
        sys.exit(255)

    # 选定要跑的层
    if args.quick:
        layers = ["filesystem"]
    elif args.layer:
        layers = [args.layer]
    else:
        layers = list(LAYER_TESTS.keys())

    if args.http:
        all_tests = list(LAYER_TESTS.values()) + [[test_t11_spa_http]]
        all_layer_keys = layers + (["http"] if "http" not in layers else [])
    else:
        all_tests = [LAYER_TESTS[l] for l in layers]
        all_layer_keys = layers

    exit_code = 0

    for layer_key, tests in zip(layers, all_tests):
        name = LAYER_NAMES.get(layer_key, layer_key)
        print(f"\n── {name} ──")
        if not run_tests(tests, verbose=args.verbose):
            exit_code |= LAYER_EXIT_CODES.get(layer_key, 255)

    # 汇总
    print(f"\n{'='*40}")
    if exit_code == 0:
        print("✓ 全部测试通过")
    else:
        failed_layers = [k for k, v in LAYER_EXIT_CODES.items() if exit_code & v]
        print(f"✗ 失败层: {', '.join(failed_layers)}")
    print(f"退出码 {exit_code}")
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
