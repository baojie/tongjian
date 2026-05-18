# RFC-tongjian-0002: 页面拼音分片标准化 — 引入 memex 共享规范

- **Status**: accepted
- **Date**: 2026-05-17
- **Issue**: https://github.com/baojie/memex/issues/46
- **Source wiki**: tongjian
- **Target**: `CONSTITUTION.md`、`wiki/scripts/page_bucket.py`、`wiki/scripts/build_registry.py`、`wiki/public/js/renderer.js`、`wiki/public/js/router.js`

---

## Problem

Tongjian 在 2026-05-14 实现了页面拼音分片（`3b5c2c2533`），将 19,258 个 `.md` 文件从单目录分散到 109 个拼音前缀桶中。迁移解决了单目录性能问题，但暴露了架构层面的缺失：

1. **分片算法无共享标准** — `page_bucket.py` 中定义了拼音前缀算法和 `resolve_page_file()` / `page_path()` 辅助函数，但其他 wiki（shiji-kb 已有 20,833 页、honglou、ai-history）如要分片，需各自复制 tongjian 的实现，无法保证算法一致。

2. **Registry `path` 字段未纳入 memex 规范** — `pages.json` 的 `path` 字段（如 `"li/刘备.md"`）是前端正确加载分桶页面的关键依赖。但 `build_registry.py` 并未在所有 wiki 上统一输出 `path` 字段，缺少 `path` 的旧注册表会导致 SPA 404。

3. **前端硬编码平铺路径** — `renderer.js` 中 `fetch(\`pages/\${pid}.md\`)` 模式在所有 wiki 中默认使用，不兼容分桶结构。每个 wiki 需要手动添加 `meta.path` fallback。

4. **History 文件路径无规范** — history/ 目录与 pages/ 共享同一分片算法，但该关联仅在 tongjian 的 `record_revision.py` 中隐式使用，未在 memex 层声明"history 路径由 `page_bucket()` 决定"的约定。

### 触发场景

- shiji-kb（20,833 页）已超过 tongjian 分片前的规模，`git status` / `ls` 卡顿正在复现
- 新建 wiki 达到数千页后需要分片，但不知从何下手
- 跨 wiki 迁移脚本（如 `corpus_search.py`、`build_backlinks.py`）中处理 `glob("*.md")` vs `rglob("*.md")` 的方式不统一

---

## Root cause

1. **分片是事后迁移而非先验设计** — 拼音分片方案（`ref/BUCKET_DESIGN.md`）是在 tongjian 已累积 19,258 页后的应急设计，没有先作为 memex 架构规范发布。

2. **Registry `path` 字段是分片的产物而非规范** — `path` 字段是在分片迁移时加入 `build_registry.py` 的，作为"让前端能找到分桶文件"的适配手段，未被定义为 memex 注册表的必需字段。

3. **缺省行为假设平铺** — 所有 memex 共享脚本（`add_page.py`、`edit_page.py`、`build_registry.py`）的设计隐含假设页面文件在 `pages/` 平铺。分片后每个脚本需要手动修复路径模式。

---

## Proposed change

### 1. 将 `page_bucket.py` 确立为 memex 共享模块

确认 `page_bucket.py` 已位于 `$MEMEX_ROOT/wiki/scripts/` 下，在 `CONSTITUTION.md` 中声明其为所有 wiki 共享的页面路由模块。

核心接口：

```python
def page_bucket(name: str) -> str:        # 页面名 → 桶名（如 "刘备" → "li"）
def page_path(slug: str) -> str:          # 页面名 → pages/ 下相对路径（如 "li/刘备.md"）
def resolve_page_file(root: Path, slug: str) -> Path | None:  # 按 slug 查找文件
```

### 2. Registry `path` 字段标准化

在 `CONSTITUTION.md` 中定义 `path` 字段为 pages.json 的必需字段：

```json
{
  "刘备": {
    "type": "人物",
    "path": "li/刘备.md"
  }
}
```

- `build_registry.py` 对所有页面输出 `path` 字段（无论是否已分桶，未分桶时等价于 `"{slug}.md"`）
- SPA 前端通过 `meta.path` 加载页面，缺省时 fallback 到 `"{pid}.md"`

### 3. 前端路径统一使用 `meta.path`

修改 `renderer.js` 和 `router.js` 中的页面 fetch 模式：

```javascript
// 统一路径解析（无论分桶与否均工作）
function _pageFile(pid, meta) {
  return (meta && meta.path) || pid + '.md';
}
```

此函数并入 `util.js` 作为共享工具函数，所有 wiki 的 `renderer.js` 使用此接口。

### 4. History 文件路径规范

在 `CONSTITUTION.md` 中声明：

```
history/<page>.jsonl 的实际路径由 page_bucket(page) 决定。
写入：history/{bucket}/{page}.jsonl
读取：从 registry.path 提取 bucket，拼入路径
```

前端新增 `_historyBucket()` 工具函数（从 `meta.path` 提取桶名），写入 `util.js`。

### 5. 分片迁移模式标准化

在 `CONSTITUTION.md` 或 `ref/spec/bucket-migration.md` 中定义标准迁移流程：

| 步骤 | 内容 |
|------|------|
| 触发条件 | pages/ 文件数 > 5,000 |
| 算法选择 | 拼音前缀（中文 wiki）/ 字母前缀（英文 wiki） |
| 迁移脚本 | `migrate_buckets.py` + `--dry-run` 先行 |
| 审计模式 | 5 轮递进扫描（代码 → 全部脚本 → Skill 文档 → 原子动作 → 全库 grep） |
| 验证 | 5 层 17 项测试（详见 tongjian `verify_buckets.py`） |
| 降级 | registry 无 `path` 字段时 fallback 平铺 |

---

## 受影响文件清单

### memex — 规范文档

| 文件 | 内容 |
|------|------|
| `CONSTITUTION.md` | 新增 `page_bucket` 共享模块声明、registry `path` 字段规范、history 路径约定 |
| `ref/spec/bucket-migration.md` | 标准迁移流程（新建，从 tongjian 经验泛化） |

### memex — 共享脚本

| 文件 | 内容 |
|------|------|
| `wiki/scripts/page_bucket.py` | 确认已在 memex 共享脚本目录（已有 `hash_bucket()` 补充） |
| `wiki/scripts/build_registry.py` | 确保所有 entry 输出 `path` 字段 |

### memex — 前端 JS

| 文件 | 内容 |
|------|------|
| `wiki/public/js/util.js` | 新增 `_pageFile(pid, meta)` 和 `_historyBucket(page, registry)` |
| `wiki/public/js/renderer.js` | 页面 fetch 使用 `meta.path`；history fetch 使用桶前缀 |
| `wiki/public/js/router.js` | 路径降级处理 |

---

## Alternatives considered

### A. 只入规范不动代码

仅在 CONSTITUTION.md 中写约定，各 wiki 自行实现。

- **问题**：shiji-kb 分片时仍需重复 tongjian 的 5 轮审计 + 11 个脚本修复模式，memex 共享脚本中的 `glob("*.md")` 模式依然需要逐个修复。
- **结论**：否决。经验和修复模式必须编码到共享脚本中。

### B. 统一用 hash 分片替代拼音分片

- **理由**：hash 分片比拼音更均匀（拼音分桶最大桶 7.9%，hash 可做到 <1%）。
- **问题**：拼音分片保留了语义可读性（`li/` 下是李/刘/礼等），hash 对人类编辑无意义。
- **结论**：拼音分片更适合 pages/（编辑友好），hash 分片保留给 line_index/。两者不冲突。

### C. 永远不分片（保持平铺）

- **问题**：19,000+ 文件的单目录已经不可用。`git status` 耗时 >10s。
- **结论**：不可接受。

---

## 参考

- tongjian `ref/BUCKET_DESIGN.md` — 方案设计文档
- tongjian `ref/BUCKET_MIGRATION_RECORD.md` — 迁移全记录（5 轮审计、11 脚本修复、SPA 适配、17 项验证）
- tongjian `wiki/scripts/verify_buckets.py` — 验证脚本
- tongjian `wiki/scripts/page_bucket.py` — 算法实现
