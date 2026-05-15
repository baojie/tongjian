# RFC-tongjian-0001: Line-Hash History v2 存储 — 行级 hash 引入 memex 插件系统

- **Status**: proposed
- **Date**: 2026-05-16
- **Issue**: https://github.com/baojie/memex/issues/12
- **Source wiki**: tongjian
- **Target**: `memex/wiki/public/plugins/recent/`、`memex/wiki/public/plugins/diff/`、`memex/wiki/scripts/record_revision.py`

---

## Problem

Tongjian 在实验分支中实现了 line-hash history v2 存储（`45a7f20e2a`、`409197f63b`），将 history 总空间从 **693.8 MB 降至 129.5 MB（−81.3%）**。核心思路是用 base62 hash 标识每行内容，版本只存 hash 数组（snap/delta），行内容在全局 992 桶的 `line_index/` 中共享。

但该实现存在架构问题：

1. **v2 逻辑全部内联在 tongjian 的 renderer.js 中** — `_hashBucket()`、`_resolveLineHash()`、`_applyDelta()`、`_reconstructContentV2()`、`_historyAll()` 等约 80 行关键代码与 tongjian 的 DOM 渲染逻辑混杂，无法被其他 wiki 复用。

2. **memex 插件系统不支持 v2 格式** — `plugins/recent/` 和 `plugins/diff/` 只读取 v0 格式（`rev_id`/`timestamp`/`content`/`diff`/`parent_rev`），遇到 v2 的 snap/delta 格式会因缺少 `content` 字段而报错或显示空内容。

3. **后端与前端格式不同步** — tongjian 的 `record_revision.py` 已能写入 v2 格式，但同一 `record_revision.py` 也维护着 `recent.lite.jsonl` 和 `recent.diff.jsonl` 两个滚动日志。memex 的插件直接读取 history 文件而不是 recent 日志，因此即使 recent 日志能工作，history 文件的不兼容仍然阻塞复用。

4. **line_index 基础设施未标准化** — 992 桶的 hash 行索引（`build_line_index.py`、`hash_bucket()` 算法）是 v2 的核心依赖，但 memex 共享脚本中没有任何与之对接的模块。

### 触发场景

当其他 wiki（如 shiji-kb、ai-history）试图复用 tongjian 的 line-hash 压缩方案时，必须：
- 从 renderer.js 复制 80 行内联代码到各自的修版渲染路径
- 从 record_revision.py 复制 v2 写入逻辑
- 复制 page_bucket.py 的 `hash_bucket()` 实现
- 适配 plugins/recent/ 的读取路径以支持 v2 格式

这是一个"复制粘贴式复用"——任何 bug 修复或优化都需要在所有 wiki 中同步。

---

## Root cause

1. **实验优先级高于架构**：line-hash v2 在 tongjian 上做实验时（2026-05-15），memex 的插件系统尚未稳定。实验追求快速验证空间压缩效果，没有在 memex 层面做架构设计。

2. **v0 与 v2 格式差异巨大**：

| 维度 | v0 | v2 |
|------|----|----|
| entry 标识 | `rev_id` (date-hex6) | `id` (base62 6 位) |
| 内容存储 | `content` (全文) | `ln` (hash 数组) + line_index |
| 版本关系 | `parent_rev` + `diff` (行级 diff) | snap / delta (hash 级编辑操作) |
| 时间戳 | ISO 8601 字符串 (25 字符) | Unix int (10 字符) |
| 摘要 | `summary` 文本 | `su` hash 引用 |
| 前端重建 | 直接读 `content` | snap → 顺序 apply delta → hash 解析全文 |

两者在设计上完全不兼容，无法通过简单适配头实现共存。

3. **插件系统未设计 v2 扩展点**：`plugins/recent/index.js` 直接 fetch history 文件并全量读入内存，没有为不同版本（v0/v2）预留 dispatch 机制。

---

## Proposed change

### 1. 抽取共享的 line-hash 解析层（JS）

在 `memex/wiki/public/js/` 下新增 `line-resolver.js`，导出以下函数：

```js
// line-resolver.js — 全局行 hash 解析模块
//
// 依赖：line_index/<hash_bucket>.json（996 桶）

const LINE_ALPHABET = '0123456789abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ';
const lineIndexCache = {};

/**
 * Base62 hash → 2-char bucket name（与后端 hash_bucket() 一致）。
 */
export function hashBucket(hash) {
  return hash[0] + (LINE_ALPHABET.indexOf(hash[1]) % 16).toString(16);
}

/**
 * 解析单个 hash → 行文本。缓存复用。
 */
export async function resolveLineHash(hash) {
  if (!hash) return '';
  const bucket = hashBucket(hash);
  if (!lineIndexCache[bucket]) {
    const r = await fetch(`line_index/${bucket}.json`);
    if (!r.ok) return '';
    lineIndexCache[bucket] = await r.json();
  }
  return lineIndexCache[bucket][hash] || '';
}

/**
 * 对 hash 数组应用 delta 编辑操作。
 */
export function applyDelta(ln, dl) { ... }

/**
 * 从 v2 entries 重建指定版本的 hash 数组。
 */
export async function reconstructContentV2(entries, targetRevId) {
  // 从最近 snap 开始，apply 后续所有 delta 到 target
  // 返回解析后的全文 markdown
}
```

### 2. 插件支持 v0/v2 双格式

#### plugins/recent/index.js

新增 `_readHistoryV0()` / `_readHistoryV2()` 分支，在读取 history 文件时自动检测 entry 格式：

```js
// 自动检测：entry.v === 2 → v2，否则 v0
async function readHistoryEntries(page) {
  const text = await fetchHistoryFile(page);
  const entries = text.split('\n').filter(l => l.trim()).map(JSON.parse);
  if (entries[0]?.v === 2) {
    return { format: 'v2', entries };
  }
  return { format: 'v0', entries };
}
```

- `renderHistory()` — v2 格式调用 `reconstructContentV2()` 获取行数统计，v0 维持现有逻辑
- `renderRevision()` — v2 格式用 `reconstructContentV2()` 重建全文后 parse，v0 直接读 `rev.content`
- `renderRecent()` — 不受影响（读 `recent.lite.jsonl`，与格式无关）

#### plugins/diff/index.js

- `renderDiff()` — v2 格式通过 `reconstructContentV2()` 重建父版和当前版 markdown，然后重新计算 unified diff
- v0 维持现有逻辑（直接读 `rev.diff` 或相邻版 content 比较）

### 3. 统一后端写入接口

`record_revision.py` 的 v2 写入逻辑需要从 tongjian 私有改造成带"格式版本"参数的共享脚本：

```bash
# 向后兼容 — 默认仍写 v0
python3 "$MEMEX_ROOT/wiki/scripts/record_revision.py" PAGE \
  --summary "编辑" --author butler

# 可选 v2 模式
python3 "$MEMEX_ROOT/wiki/scripts/record_revision.py" PAGE \
  --format v2 --line-index-dir wiki/public/line_index
```

- 共享版本写入 v0 格式（向后兼容所有现有 wiki）
- `--format v2` 启用 line-hash 写入（需要 `--line-index-dir`）
- `build_line_index.py` 及其 `hash_bucket()` 算法从 `page_bucket.py` 迁入 memex 共享脚本

### 4. line_index 目录规范

在 memex 的 `CONSTITUTION.md` 或 `LAW.md` 中新增约定：

```
wiki/public/line_index/  # 可选目录（仅开启 v2 的 wiki 需要）
  10.json ... zf.json     # 992 个 hash 桶文件
```

- 由 `build_line_index.py --rebuild` 全量构建
- 由 `record_revision.py --format v2` 在写入时增量更新
- 前端通过 `resolveLineHash()` 懒加载

### 5. 迁移路径

分三个阶段：

| 阶段 | 内容 | 依赖 |
|------|------|------|
| **P1** | `line-resolver.js` 入 memex 共享 JS；`hash_bucket()` 入共享脚本 | 无 |
| **P2** | plugins/recent/、plugins/diff/ 支持 v2 读取（双格式） | P1 |
| **P3** | `record_revision.py` 支持 `--format v2` 写共享版 | P1 + P2 |

各 wiki 独立决定是否开启 v2（不开启则完全不受影响）。

---

## Alternatives considered

### A. 保持 v0-only，不引入 v2

- **理由**：v0 格式简单直接，开发维护成本低。
- **问题**：43 个文件 >20MB（司徒.2 达 19.8MB），500+ 条 revision 的页面在加载时全量下载 history JSONL，用户需要等待数秒才能看到历史版本。空间浪费 4×。
- **结论**：不可接受。已用实验数据验证 v2 的有效性。

### B. 用 IndexedDB / SQLite 替代 line_index JSON 文件

- **理由**：避免 992 个 JSON 文件进 git。
- **问题**：
  - SQLite 需要后端服务或 WASM，增加架构复杂度
  - IndexedDB 需要 Service Worker 安装脚本
  - 当前 992 文件共 ~90 MB，gzip 后 ~45 MB，进 git 可接受
- **结论**：长期可以探索，当前 line_index JSON 方案足够。

### C. 每个 wiki 独立内联 v2 代码（现状延续）

- **问题**：bug 修复需逐个 wiki 手动同步；格式升级（v3）无可控入口。
- **结论**：拒绝。这正是提交 RFC 的原因。

### D. gzip line_index 桶文件 + Epoch 分代

已在 `ref/spec/line-hash-compaction.md` TODO 中记录：按行被发现的次序分代，`current/` text + `epoch_NNN/` gzip。这与本 RFC 正交，可作为后续 RFC 提交。

---

## 受影响文件清单

### memex — 新建

| 文件 | 内容 |
|------|------|
| `wiki/public/js/line-resolver.js` | `hashBucket()`、`resolveLineHash()`、`applyDelta()`、`reconstructContentV2()` |
| `wiki/scripts/build_line_index.py` | 全站扫描 → 992 桶 hash 行索引（从 tongjian 移植） |

### memex — 修改

| 文件 | 内容 |
|------|------|
| `wiki/public/plugins/recent/index.js` | v0/v2 双格式 dispatch；v2 用 `reconstructContentV2()` 重建 |
| `wiki/public/plugins/diff/index.js` | v2 格式通过重建全文计算 diff |
| `wiki/scripts/record_revision.py` | 共享版本加 `--format v2` 参数（从 tongjian 移植 v2 写入逻辑） |
| `wiki/scripts/page_bucket.py` | 保留 `hash_bucket()`（已在共享脚本中） |

### tongjian — 清理

| 文件 | 内容 |
|------|------|
| `docs/wiki/js/renderer.js` | 删除 `_hashBucket()`、`_resolveLineHash()`、`_applyDelta()`、`_reconstructContentV2()`、`_historyAll()` — 改用从 memex 导入 |
| `wiki/scripts/record_revision.py` | v2 写入逻辑迁入 memex 共享版，tongjian 版本简化为配置调用共享脚本 |

---

## 后续工作（不在本 RFC 范围内）

1. **行索引 Epoch 分代**：`current/` text + `epoch_NNN/` gzip，解决 line_index 进 git 的体积问题（详见 `ref/spec/line-hash-compaction.md` TODO）
2. **history 数据库化**：将 per-page JSONL 迁移到 SQLite/KV，脱离 git 体系
3. **diff 插件优化**：v2 格式下直接基于 hash 数组算 diff，避免重建全文
