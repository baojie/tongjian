# 拼音分片迁移全记录

> 执行时间：2026-05-14 至 2026-05-15
> 当前状态：全部完成，验证通过

---

## 目录

1. [背景与方案](#1-背景与方案)
2. [迁移执行](#2-迁移执行)
3. [脚本审计与修复](#3-脚本审计与修复)
4. [Skill 文档修复](#4-skill-文档修复)
5. [History 分桶](#5-history-分桶)
6. [前端 SPA 适配](#6-前端-spa-适配)
7. [规范文档更新](#7-规范文档更新)
8. [验证清单](#8-验证清单)
9. [附录](#9-附录)

---

## 1. 背景与方案

### 1.1 问题

`wiki/public/pages/` 单目录累积 19,258 个 `.md` 文件，导致：

- `ls` / `git status` 操作极慢（数秒至数十秒）
- 文件浏览器（VS Code / Finder）卡顿
- 人类编辑无法定位页面
- git diff 全量时输出巨大

### 1.2 选定方案

拼音首字前 2 字母分片（详见 [BUCKET_DESIGN.md](BUCKET_DESIGN.md)）。

算法核心逻辑（`wiki/scripts/page_bucket.py`）：

| 首字符类型 | 桶名规则 | 示例 |
|-----------|---------|------|
| CJK 汉字 | 首字拼音前 2 字母 | `刘备` → `li` |
| ASCII 字母/数字 | 前 2 字母数字 | `About` → `ab` |
| 前导标点 | 剥离后按剩余首字 | `《资治通鉴》` → `zi` |
| 单字/边界 | 补 `0` | `阿` → `a0` |

### 1.3 桶分布（迁移后）

- 总桶数：109
- 最大桶：`zh/`（1,520，7.9%）
- 最小桶：1（`e0/`、`ep/` 等稀有拼音）
- 平均：177/桶

---

## 2. 迁移执行

### 2.1 页面迁移脚本

**文件**：`wiki/scripts/migrate_buckets.py`

一次性脚本，扫描 `pages/` 下所有 `.md`，按 `page_bucket(slug)` 计算目标桶，`os.rename()` 移动（同文件系统零拷贝）。

```bash
python3 wiki/scripts/migrate_buckets.py          # dry-run
python3 wiki/scripts/migrate_buckets.py --apply   # 执行
```

**结果**：19,258 文件迁移，0 错误，109 桶创建。

### 2.2 执行后 pages/ 状态

```
pages/
├── di/     ← 第???卷.md（294 卷原文）
├── li/     ← 刘备、李广、李斯、礼、立…
├── zh/     ← 中国、诸葛亮、诸侯、中、之…
├── go/     ← 公、功、宫、共、供养…
├── qi/     ← 七国之乱、齐、前、秦、器…
├── ca/     ← 曹操、蔡、才、财、采…
├── ch/     ← 丞相、城、常、朝、陈…
├── wa/     ← 王莽、外、万、王、亡…
├── sh/     ← 商鞅、上下、尚书、师、史…
└── …（共 109 桶）
```

---

## 3. 脚本审计与修复

### 3.1 审计方法

对所有操作 `pages/` 目录的脚本进行五轮递进扫描：

| 轮次 | 范围 | 方法 |
|------|------|------|
| 1 | 脚本代码 | grep `pages/*.md` / `os.listdir` / `glob` 平铺模式 |
| 2 | 全部脚本 | 逐文件 review 所有 pages 路径引用 |
| 3 | Skill 文档 | 11 个 `.md` 文档中的示例命令 |
| 4 | 原子动作 | W2 定义与脚本实际行为对照 |
| 5 | 全量 grep | `pages/` 字符串全库扫描 + JS + config |

### 3.2 修复清单（11 个脚本）

#### (1) `build_fts_index.py` — CRITICAL

**问题**：`os.listdir(pages_dir)` 平铺读取，迁移后返回空（因 `.md` 在子目录）。

**修复**：
```python
# 旧
files = [f for f in os.listdir(pages_dir) if f.endswith('.md')]
# 新
files = list(pages_dir.rglob('*.md'))
```

#### (2) `pn_year_cache.py` — CRITICAL

**问题**：`glob("第???卷.md")` 不递归，卷页在 `di/` 桶后无法找到。

**修复**：
```python
# 旧
vol_files = glob(str(vol_dir / "第???卷.md"))
# 新
vol_files = list(vol_dir.rglob("第???卷.md"))
```

#### (3) `build_office_pages.py` — CRITICAL

**问题**：同上，`glob("第*.md")` 不递归。

**修复**：
```python
# 旧
for fpath in sorted(PAGES_DIR.glob("第*.md")):
# 新
for fpath in sorted(PAGES_DIR.rglob("第*.md")):
```

#### (4) `batch_fix_meta.py` — HIGH

**问题**：`os.listdir()` + 平铺路径拼接 `os.path.join(PAGES_DIR, fname)`。

**修复**：
```python
# 旧
for fname in os.listdir(PAGES_DIR):
    fpath = os.path.join(PAGES_DIR, fname)
# 新
for fpath in sorted(PAGES_DIR.rglob("*.md")):
    fname = fpath.name
```

#### (5) `batch_create_official.py` — HIGH

**问题**：`os.listdir()` 构造 EXISTING set，迁移后只返回桶目录名。

**修复**：
```python
# 旧
existing = {f.replace('.md', '') for f in os.listdir(EXISTING_DIR) if f.endswith('.md')}
# 新
existing = {f.stem for f in EXISTING_DIR.rglob("*.md")}
```

#### (6) `fix_suffix_format.py` — HIGH

**问题**：写入路径 `PAGES_DIR / f"{new_id}.md"` 无桶前缀。

**修复**：
```python
# 旧
out_path = PAGES_DIR / f"{new_id}.md"
# 新
bucket = page_bucket(new_id)
out_dir = PAGES_DIR / bucket
out_dir.mkdir(parents=True, exist_ok=True)
out_path = out_dir / f"{new_id}.md"
```

#### (7) `batch_create.py` — HIGH

**问题**：存在性检查 `ROOT / "pages" / f"{slug}.md"` 平铺路径。

**修复**：
```python
# 旧
target = ROOT / "pages" / f"{slug}.md"
# 新
target = resolve_page_file(PAGES_DIR, slug)
```

#### (8) `bulk_wikilink.py` — MEDIUM

**问题**：git diff 路径模式 `"docs/wiki/pages/*.md"` 不递归。

**修复**：
```bash
# 旧
subprocess.run(["git", "diff", "--name-only", since, "--", "docs/wiki/pages/*.md"])
# 新
subprocess.run(["git", "diff", "--name-only", since, "--", "docs/wiki/pages/"])
```

#### (9) `import_volumes.py` — CRITICAL

**问题**：写入 `pages_dir / f'第{nn}卷.md'` 平铺，卷页应在 `di/` 桶。

**修复**：
```python
# 旧
out_path = pages_dir / f'{slug}.md'
# 新
bucket = page_bucket(slug)
out_dir = pages_dir / bucket
out_dir.mkdir(parents=True, exist_ok=True)
out_path = out_dir / f'{slug}.md'
```

#### (10) `h21_audit_person_tables.py` — MEDIUM

**问题**：`resolve_page_file` 行后残留了死 fallback `or PAGES / f"{slug}.md"`。

**修复**：删除 fallback 分支。

#### (11) `renderer.js` — CRITICAL

**问题**：`renderSource()` 硬编码 `fetch(\`pages/\${pid}.md\`)` 忽略分桶；`_historyAll()` 读取 history 无桶前缀。

**修复**（两处）：
```javascript
// renderSource: 用 meta.path 替代平铺拼接
const pageFile = (meta && meta.path) || pid + '.md';
const r = await fetch(`pages/${pageFile}`);

// 新增 _historyBucket() 从 meta.path 提取桶名
function _historyBucket(page, registry) {
  if (registry && registry.pages) {
    const meta = registry.pages[page];
    if (meta && meta.path) {
      const parts = meta.path.split('/');
      if (parts.length >= 2) return parts[0];
    }
  }
  return '';
}
// _historyAll() 等函数传入 registry，fetch 时使用桶前缀
```

### 3.3 已确认桶兼容（无需修改的脚本）

以下脚本在审计时已正确使用 `rglob("*.md")` 或 `resolve_page_file()`：

- `add_page.py` — 使用 `page_bucket()` 写入正确桶
- `edit_page.py` — 使用 `resolve_page_file()` 定位
- `page_bucket.py` — 核心算法模块
- `build_registry.py` — `rglob("*.md")`
- `record_revision.py` — `page_bucket()` + `resolve_page_file()`
- `build_backlinks.py` — `rglob("*.md")`
- `compute_knowledge.py` — `rglob("*.md")`
- `compute_quality.py` — `rglob("*.md")`
- `fix_bad_pn.py` — `rglob("*.md")`
- `reclassify_concepts.py` — `rglob("*.md")`
- `batch_english_to_chinese_types.py` — `rglob("*.md")`
- `batch_merge_types.py` — `rglob("*.md")`
- `batch_split_concept_types.py` — `rglob("*.md")`
- `scan_missing_type.py` — `rglob("*.md")`
- `corpus_search.py` — `rglob("第???卷.md")`
- `corpus_discover.py` — 只读 pages.json
- `discover_wanted.py` — `rglob("*.md")`
- `wikify_chapters.py` — `resolve_page_file()` + `rglob()`
- `build_timeline.py` — `resolve_page_file()` + `rglob()`
- `check_citations.py` — `rglob("*.md")`
- `check_size_loss.py` — `page_bucket()` 算 history 路径
- `build_ruler_list_pages.py` — `resolve_page_file()` + `rglob()`
- `build_wanted_pages.py` — `page_bucket()` 写入
- `scan_office_duplicates.py` — `resolve_page_file()` + `rglob()`
- `add_surname.py` — `page_bucket()` + `rglob()`
- `batch_create_surname_pages.py` — `page_bucket()` + `rglob()`
- `disambiguate_single_char.py` — `page_bucket()` + `rglob()`
- `h22_fix_emdash.py` — `resolve_page_file()`
- `h23_merge_geo_official.py` — `resolve_page_file()` + `rglob()`
- `h24_merge_compound_wikilinks.py` — `rglob()`
- `record_action.py` — 无 pages 操作
- `rotate_history_migrate.py` — `page_bucket()` + `rglob()`

---

## 4. Skill 文档修复

Butler SKILL.md 及 `skills/SKILL_W*.md` 中的示例命令使用平铺路径。

### 4.1 `.claude/skills/butler/SKILL.md`（3 处）

| 行 | 旧 | 新 |
|----|---|----|
| 27 | `git add wiki/public/pages/<单个文件>` | `git add $(find wiki/public/pages/ -name "${SLUG}.md" -type f)` |
| 36 | `pages/第NNN卷.md` | `pages/di/第NNN卷.md`（位于 di/ 桶） |
| 110 | `git add wiki/public/pages/SLUG.md` | `git add $(find ... -name "${SLUG}.md")` |

### 4.2 `skills/SKILL_W*.md`（11 个文件，共 20+ 处）

| 文件 | 修复模式 |
|------|---------|
| W10e | `pages/*.md` → `pages/*/*.md`；`cat pages/人物名.md` → `resolve_page_file` |
| W10f | `pages/*.md` → `pages/*/*.md`；存在性检查改用 `resolve_page_file` |
| W8 | `pages/第NNN卷.md` → `pages/di/第NNN卷.md`；`ls pages/ \| xargs` → `grep -rl` |
| W4 | `pages/第080卷.md` → `pages/di/第080卷.md` |
| W6 标注规范 | 卷页路径改为 `pages/di/` |
| W6 离线质检 | `check_citations.py` 示例改用 `resolve_page_file` 定位 |
| W10c | `grep pages/目标页.md` → `resolve_page_file + read_text` |
| W10l | `grep pages/人物名.md` → `resolve_page_file + read_text` |
| W7 | `pages/*.md` → `pages/*/*.md` |

---

## 5. History 分桶

### 5.1 背景

`wiki/public/history/` 有 20,629 个 `.jsonl` 文件，同样平铺。

### 5.2 方案

与 pages/ 相同拼音分片算法（`page_bucket`），确保目录结构一致。

```
history/刘备.jsonl    →  history/li/刘备.jsonl
history/曹操.jsonl    →  history/ca/曹操.jsonl
```

### 5.3 迁移脚本

**文件**：`wiki/scripts/migrate_history_buckets.py`

```bash
python3 wiki/scripts/migrate_history_buckets.py          # dry-run
python3 wiki/scripts/migrate_history_buckets.py --apply   # 执行
```

**结果**：20,620 文件迁移，0 错误。

### 5.4 后端写入适配

`record_revision.py` 已使用 `page_bucket(slug)` 计算历史文件路径：

```python
bucket = page_bucket(page)
hist_dir = HIST / bucket
hist_dir.mkdir(parents=True, exist_ok=True)
page_jsonl = hist_dir / f"{page}.jsonl"
```

其他使用 history 路径的脚本（`check_size_loss.py`、`rotate_history_migrate.py`）同步适配。

### 5.5 前端读取适配

`renderer.js` 新增 `_historyBucket()` 函数，从 registry `meta.path` 提取桶名：

```javascript
function _historyBucket(page, registry) {
  const meta = registry.pages[page];
  if (meta && meta.path) return meta.path.split('/')[0];
  return '';
}
```

history fetch 路径变为 `history/{bucket}/{page}.jsonl`，无 bucket 时回退到 `history/{page}.jsonl`。

---

## 6. 前端 SPA 适配

### 6.1 页面加载流程

```
用户点击 #刘备
  → resolvePageId("刘备", registry)
  → meta = registry.pages["刘备"]  # { type: "人物", path: "li/刘备.md" }
  → fetch(`pages/${meta.path || pid + '.md'}`)
  → 渲染
```

### 6.2 注册表结构

`pages.json` / `pages.lite.json` 每条记录含 `path` 字段：

```json
{
  "刘备": { "type": "人物", "label": "刘备", "path": "li/刘备.md" },
  "曹操": { "type": "人物", "label": "曹操", "path": "ca/曹操.md" }
}
```

### 6.3 降级策略

若 registry 中某条无 `path` 字段，SPA fallback 到 `pages/{pid}.md`，保持向前兼容。

### 6.4 主要修改

| 文件 | 修改内容 |
|------|---------|
| `docs/wiki/js/renderer.js:546` | `fetch(\`pages/\${pid}.md\`)` → 使用 `meta.path` |
| `docs/wiki/js/renderer.js` | 新增 `_historyBucket()` 函数 |
| `docs/wiki/js/renderer.js` | `_historyAll()`、`renderHistory`、`renderRevision`、`renderDiff` 传入 registry 并使用桶前缀 |
| `docs/wiki/js/router.js` | 错误消息简化（不再暴露内部文件路径） |

---

## 7. 规范文档更新

| 文档 | 更新内容 |
|------|---------|
| `CLAUDE.md` | 新增拼音分片说明、桶分布数据、`page_bucket` 辅助函数、History 分桶规则 |
| `ref/BUCKET_DESIGN.md` | 完整方案设计（创建于项目 `ref/`） |
| `ref/BUCKET_MIGRATION_RECORD.md` | 本记录文件 |

---

## 8. 验证清单

### 8.1 验证脚本

**文件**：`wiki/scripts/verify_buckets.py`

```bash
python3 wiki/scripts/verify_buckets.py          # 全套
python3 wiki/scripts/verify_buckets.py --quick  # 仅文件系统层
python3 wiki/scripts/verify_buckets.py --layer resolution  # 仅解析层
```

### 8.2 测试项

| ID | 层 | 验证内容 | 状态 |
|----|-----|---------|------|
| T1 | 文件系统 | pages/ 顶层无 .md 文件 | ✓ |
| T2 | 文件系统 | 分桶数 ~109 | ✓ |
| T3 | 文件系统 | 总页面数 19,258 | ✓ |
| T4 | 文件系统 | 最大桶占比 ≤ 15% | ✓ (7.9%) |
| T5 | 文件系统 | history/ 顶层无 .jsonl | ✓ |
| T6 | 解析 | resolve_page_file 正确定位 15 个已知页面 | ✓ |
| T7 | 解析 | registry path 字段 100% 完整 | ✓ |
| T8a | 脚本 | build_registry.py 读取全量 | ✓ |
| T8b | 脚本 | add_page.py 写入正确桶 | ✓ |
| T8c | 脚本 | edit_page.py 定位已有页面 | ✓ |
| T8d | 脚本 | corpus_search 读取卷页 | ✓ |
| T8e | 脚本 | rglob 找到 294 卷 | ✓ |
| T9a | 数据完整性 | registry path 指向存在文件 | ✓ |
| T9b | 数据完整性 | history 与 pages 桶一致 | ✓ |
| T10a | 边界 | 294 卷全部在 di/ 桶 | ✓ |
| T10c | 边界 | SPA 模拟加载 100 页 100% | ✓ |
| T10d | 边界 | history 分桶逻辑正确 | ✓ |
| T11 | SPA | HTTP 渲染验证（需 wiki 服务） | ✓ |

---

## 9. 附录

### 9.1 涉及文件清单

#### 新建文件
- `wiki/scripts/migrate_buckets.py` — pages 迁移脚本
- `wiki/scripts/migrate_history_buckets.py` — history 迁移脚本
- `wiki/scripts/verify_buckets.py` — 验证脚本
- `ref/BUCKET_DESIGN.md` — 设计方案
- `ref/BUCKET_MIGRATION_RECORD.md` — 本记录

#### 修复文件（Python）
- `wiki/scripts/build_fts_index.py`
- `wiki/scripts/butler/pn_year_cache.py`
- `wiki/scripts/butler/build_office_pages.py`
- `wiki/scripts/batch_fix_meta.py`
- `wiki/scripts/batch_create_official.py`
- `wiki/scripts/butler/fix_suffix_format.py`
- `wiki/scripts/butler/batch_create.py`
- `wiki/scripts/butler/bulk_wikilink.py`
- `wiki/scripts/import_volumes.py`
- `wiki/scripts/butler/h21_audit_person_tables.py`

#### 修复文件（前端 JS）
- `docs/wiki/js/renderer.js`
- `docs/wiki/js/router.js`

#### 修复文件（Skill 文档）
- `.claude/skills/butler/SKILL.md`
- `skills/SKILL_W0_Butler总则.md`（无代码修复，目录描述已验证）
- `skills/SKILL_W2_Butler原子行动.md`（无代码修复，规则描述已验证）
- `skills/SKILL_W4_Butler评估与检验.md`
- `skills/SKILL_W6_Butler原文标注规范.md`
- `skills/SKILL_W6_Butler离线质检.md`
- `skills/SKILL_W7_引文真实性核验.md`
- `skills/SKILL_W8_精品页建设方法论.md`
- `skills/SKILL_W10c_词汇链接化.md`
- `skills/SKILL_W10e_原文溯源增补.md`
- `skills/SKILL_W10f_断链新建条目.md`
- `skills/SKILL_W10l_引文PN一致性.md`

#### 更新文档
- `CLAUDE.md` — 添加分桶规则
- `ref/BUCKET_DESIGN.md` — 补充审计报告和 history 分桶

### 9.2 迁移日志

pages 迁移日志：`wiki/logs/bucket_migration.jsonl`
history 迁移日志：`wiki/logs/history_bucket_migration.jsonl`
