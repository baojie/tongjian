# recent.lite.jsonl v2 字段名不匹配修复

> 日期：2026-05-16
> 关联 RFC: [rfc-tongjian-0001](../rfc/rfc-tongjian-0001-linehash-history-plugin.md)
> 关联 Issue: [baojie/memex#12](https://github.com/baojie/memex/issues/12)

## 问题

line-hash history v2 格式使用缩写字段名（`id`/`ts`/`au`/`su`）以节省存储空间。`record_revision.py` 在构建 `recent_lite_entry` 时直接将 history entry 的字段 spread 进去，导致 v2 缩写字段名涌入 `recent.lite.jsonl`。

前端 `renderer.js` 的 `renderRecent()` 函数读取旧字段名（`rev_id`/`timestamp`/`author`/`summary`），遇到 v2 条目时所有关键字段均为 `undefined`，页面显示异常（时间列为 `NaN-NaN-NaN NaN:NaN`，修订号和作者显示 "undefined"）。

## 范围

- 受影响的条目：全部 679 条
  - 47 条直接写入的 v2 格式记录（字段名不匹配）
  - 632 条 v0→v2 迁移后的旧记录（`rev_id` 已变，链接失效）
- 影响的范围：
  - `Special:Recent` 页面显示异常（NaN 时间、"undefined" 作者）
  - Revision/Diff 链接全部失效（旧 `rev_id` 在 v2 history 中不存在）
- 影响的文件：`wiki/public/recent.lite.jsonl`

## 修复

### 1. `wiki/scripts/record_revision.py`

在 `recent_lite_entry` 构建后添加 v2→旧格式字段名映射：

```python
if recent_lite_entry.get("v") == 2:
    recent_lite_entry["rev_id"] = recent_lite_entry.pop("id", None)
    recent_lite_entry["timestamp"] = recent_lite_entry.pop("ts", None)
    recent_lite_entry["author"] = recent_lite_entry.pop("au", None)
    recent_lite_entry["summary"] = recent_lite_entry.pop("su", None)
```

这样后续所有写入 `recent.lite.jsonl` 的条目都使用前端可解析的字段名。

### 2. `wiki/public/recent.lite.jsonl` — 双重 backfill

**第一轮（字段名）**：修复 47 条 v2 记录，将 `id`→`rev_id`、`ts`→`timestamp`、`au`→`author`、`su`→`summary`。

**第二轮（ID 对齐）**：修复 632 条 v0→v2 迁移后的旧记录。v0 的 `rev_id`（如 `20260514-164941-2fa81a`）在 v2 迁移中被替换为 `base62(content_hash)` 计算的短 hash（如 `BIeV9H`），但 `recent.lite.jsonl` 未随之更新。通过 `content_hash → base62_id()` 的确定性映射批量纠正所有旧记录的 `rev_id`，使 revision/diff 链接指向 v2 历史文件中的正确条目。

## 核验

`__verify_bucket_test__` 页面历史验证通过：
- 旧 `rev_id`: `20260514-164941-2fa81a` → 新 `rev_id`: `BIeV9H`
- `history/00/__verify_bucket_test__.jsonl` 中的 `id` 字段也是 `BIeV9H` — 一一对应 ✅

## 残留注意

v2 格式的 `su` 字段是 hash（如 `6fOWo2`），而非人类可读的 summary。`recent_lite_entry` 中的 `summary` 字段随之显示为 hash。这不会引起错误，但可读性差。需在 RFC P3 阶段统一处理 summary 的生成逻辑。

前端 `renderRevision`/`renderHistory`/`renderDiff` 已支持 v0/v2 双格式自动检测，无需额外修改。
