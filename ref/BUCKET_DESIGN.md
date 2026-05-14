# Wiki 页面拼音分片设计方案

## 背景

`wiki/public/pages/` 目录下累积了 **19,258 个 .md 文件**（294 卷原文 + 18,964 词条），全部平铺在单目录中，导致：

- `ls` / `git status` 等操作缓慢
- 人类编辑难以定位页面
- 文件浏览器卡顿
- git diff 在涉及全量操作时产生巨量输出

## 设计目标

1. **均衡分布** — 任何单桶不超过总文件数的 10%
2. **语义可理解** — 编辑者看到目录名能推断内容
3. **确定性** — 相同页面名永远映射到相同桶
4. **无运行时依赖** — 迁移一次性使用 pypinyin，运行时不依赖
5. **零重构** — 页面 ID、wikilink、URL hash 均不变

## 方案对比

| 方案 | 分布均匀度 | 语义性 | 实现复杂度 | 结论 |
|------|-----------|--------|-----------|------|
| 类型分片 | 极差（人物 31%） | 强 | 低 | 不均匀 |
| 拼音前 2 字母 | 中等（最大 8%） | 中 | 低 | **选用** |
| 拼音首字母缩写 | 中等 | 中 | 中 | 类似 |
| 按 Unicode 码位 hash | 最均匀 | 无 | 低 | 不保留语义 |
| 按朝代分片 | 不可行（93% 无数据） | 强 | 高 | — |

## 选定算法

### 规则

```
输入：页面名（不含 .md）
输出：2 字符桶名

1. 剥离前导标点符号（《》（）等）
2. 若首字符是 ASCII 字母或数字：
   → 取前 2 个字母数字（小写），不足补 "0"
3. 若首字符是 CJK 汉字：
   → 用 pypinyin 取第一字拼音的前 2 字母
   → 若拼音不足 2 字母（如 "阿" → "a"），取第二字首字母补足
   → 仍不足补 "0"
4. 若 pypinyin 不可用：
   → fallback：取 UTF-8 编码前 2 字节的 hex
```

### 实现

`wiki/scripts/page_bucket.py` 提供三个函数：

| 函数 | 用途 | 示例 |
|------|------|------|
| `page_bucket(slug)` | 返回桶名 | `"刘备"` → `"li"` |
| `page_path(slug)` | 返回相对路径 | `"刘备"` → `"li/刘备.md"` |
| `resolve_page_file(root, slug)` | 返回 Path 对象 | 查 `pages/li/刘备.md` |

### 依赖

- **迁移时**（一次性）：`pypinyin`（`pip install pypinyin`）
- **运行时**：无额外依赖。`page_bucket.py` 中 `pypinyin` 为可选导入，缺失时走 hex fallback

## 分布数据

统计时间：2026-05-14
总页面数：19,258

### 桶分布（前 10）

| 桶 | 文件数 | 占比 | 典型页面 |
|----|--------|------|---------|
| zh/ | 1,520 | 7.9% | 中国, 诸葛亮, 诸侯, 中, 之, 制, 主 |
| li/ | 1,165 | 6.0% | 刘备, 李广, 李斯, 礼, 立, 吏, 利 |
| go/ | 1,121 | 5.8% | 公, 功, 宫, 共, 供养, 贡 |
| qi/ | 1,014 | 5.3% | 七国之乱, 齐, 前, 秦, 器, 起 |
| ji/ | 989 | 5.1% | 九卿, 军, 家, 将, 计, 纪 |
| sh/ | 862 | 4.5% | 上下, 上书, 尚书, 师, 史, 事 |
| xi/ | 764 | 4.0% | 下, 下军, 西, 系, 县, 相 |
| ch/ | 633 | 3.3% | 丞相, 城, 常, 朝, 陈, 出 |
| di/ | 483 | 2.5% | 丁, 第001卷, 地, 弟, 帝, 典 |
| ya/ | 458 | 2.4% | 严, 言, 颜, 延, 牙, 雅 |
| 余 99 桶 | 1~447 | 其余 | — |

### 统计

- 桶数：109
- 最大桶：1,520（zh/）
- 最小桶：1（多个稀有拼音，如 ê/ 等）
- 平均桶大小：177
- 中位数：76

## 迁移过程

### 迁移脚本

`wiki/scripts/migrate_buckets.py`（一次性脚本，执行于 2026-05-14）

```
python3 wiki/scripts/migrate_buckets.py [--dry-run]
```

脚本行为：
1. 扫描 `pages/` 下所有 `*.md`
2. 对每个文件计算 `page_bucket(slug)`
3. 创建桶目录（`pages/li/`、`pages/ca/` 等）
4. 用 `os.rename()`（同文件系统，零拷贝）移动文件
5. 记录迁移日志到 `wiki/logs/bucket_migration.jsonl`

### 执行结果

- 19258 文件迁移，0 错误
- 109 桶目录创建
- 迁移后 pages/ 顶层无 `.md` 文件残留

### 受影响组件

| 组件 | 修改内容 |
|------|---------|
| `build_registry.py` | pid 用 `.stem`（支持子目录）；加 `path` 字段；lite 版也带 path |
| `router.js` | `fetch(pages/${pid}.md)` → 使用 `meta.path` |
| `add_page.py` | 写入 `pages/{bucket}/{slug}.md` |
| `edit_page.py` | 用 `resolve_page_file()` 查找文件 |
| `record_revision.py` | 同上 |
| `corpus_search.py` | `glob('第???卷.md')` → `rglob('第???卷.md')` |
| 约 30 个 Butler/工具脚本 | `glob('*.md')` → `rglob('*.md')`；或接入 `resolve_page_file()` |

### 审计清单（迁移后补充）

迁移后对 `wiki/scripts/` 下所有操作 pages 目录的脚本进行了详尽审计，发现并修复了 7 个遗漏的平铺路径：

| 严重度 | 脚本 | 问题 | 修复方式 |
|--------|------|------|---------|
| CRITICAL | `build_fts_index.py` | `os.listdir()` 平铺 → FTS 索引为空 | → `rglob("*.md")` |
| CRITICAL | `butler/pn_year_cache.py` | `glob("第???卷.md")` 平铺 → PN 缓存为空 | → `rglob()` |
| CRITICAL | `butler/build_office_pages.py` | `glob("第*.md")` 平铺 → 历任提取为空 | → `rglob()` |
| HIGH | `batch_fix_meta.py` | `os.listdir()` + 平铺路径拼接 | → `resolve_page_file()` |
| HIGH | `batch_create_official.py` | `os.listdir()` 存在性检查 | → `rglob()` |
| HIGH | `butler/fix_suffix_format.py` | 写入 `PAGES_DIR / f"{id}.md"` 无桶 | → `page_bucket()` |
| HIGH | `butler/batch_create.py` | 存在性检查 `ROOT / "pages" / f"{slug}.md"` | → `resolve_page_file()` |
| MEDIUM | `butler/bulk_wikilink.py` | git diff 路径模式 `pages/*.md` 不递归 | → `pages/`（目录级） |

所有修复后经 `python3 -m py_compile` 验证通过。

## History 分桶

### 背景

`wiki/public/history/` 目录下有 **20,629 个 .jsonl 文件**（20,620 主文件 + 9 归档文件），与 pages/ 平铺问题相同。

### 方案

采用与 pages/ 完全相同拼音分片算法（`page_bucket`），确保 history/ 和 pages/ 的目录结构一致。

```
history/刘备.jsonl    →  history/li/刘备.jsonl
history/曹操.jsonl    →  history/ca/曹操.jsonl
history/司徒.1.jsonl  →  history/si/司徒.1.jsonl
```

### 迁移

迁移脚本：`wiki/scripts/migrate_history_buckets.py`

```bash
python3 wiki/scripts/migrate_history_buckets.py          # dry-run
python3 wiki/scripts/migrate_history_buckets.py --apply   # 执行
```

执行于 2026-05-15：20,620 文件迁移，0 错误。

### 受影响组件

| 组件 | 修改内容 |
|------|---------|
| `record_revision.py` | `HIST / f"{page}.jsonl"` → `HIST / bucket / f"{page}.jsonl"` |
| `check_size_loss.py` | `HISTORY / f'{slug}.jsonl'` → `HISTORY / bucket / f'{slug}.jsonl'` |
| `rotate_history_migrate.py` | 同上 + `rglob("*.jsonl")` 递归扫描 |
| `renderer.js` | 新增 `_historyBucket()` 从 registry.path 提取桶；所有 fetch 路径加 bucket 前缀 |
| `router.js` | 错误消息简化（不再暴露内部路径） |

### SPA 兼容性

前端通过 registry 中的 `path` 字段（如 `"li/刘备.md"`）提取桶名：

```javascript
function _historyBucket(page, registry) {
  const meta = registry.pages[page];
  if (meta && meta.path) return meta.path.split('/')[0];
  return '';  // 无 path 时回退到根目录，向前兼容
}
```

history fetch 路径变为 `history/{bucket}/{page}.jsonl`，无 bucket 时回退到 `history/{page}.jsonl`。

## SPA 兼容性

### 页面加载流程

```
用户点击 #刘备
  → resolvePageId("刘备", registry)
  → meta = registry.pages["刘备"]  # { type: "人物", path: "li/刘备.md", ... }
  → fetch(`pages/${meta.path || pid + '.md'}`)
  → 渲染
```

### 注册表

`pages.lite.json` 中每条记录包含 `path`：

```json
{
  "刘备": { "type": "人物", "label": "刘备", "path": "li/刘备.md" },
  "曹操": { "type": "人物", "label": "曹操", "path": "ca/曹操.md" }
}
```

### 降级策略

若 registry 中某条无 `path` 字段（如旧版缓存），SPA fallback 到 `pages/{pid}.md`，保持向前兼容。

## 发布

`wiki/public` 是指向 `docs/wiki/` 的符号链接，因此：

```
wiki/public/pages/li/刘备.md  ≡  docs/wiki/pages/li/刘备.md
```

`publish.sh` 直接在 `wiki/public/` 上操作，对 `docs/` 实时生效。
