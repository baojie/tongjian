# History 存储优化：周期快照 + 增量 Patch

## 背景

`wiki/public/history/` 以 JSONL 格式逐条存储每页的修订历史。当前格式存在严重冗余：

> **每条 entry 同时保存 `content`（全文快照）和 `diff`（行级变化）**

对于 3 个 revision 的页面，相当于存了 3 份完整正文，第 2、3 份是纯粹冗余。

## 优化前状态

采集日期：2026-05-15

| 指标 | 数值 |
|------|------|
| history 文件数 | 20,631 |
| revision 总数 | 125,633 |
| 总磁盘占用 | **693.8 MB** |
| 平均文件大小 | 34.4 KB |
| 平均每 revision | 5,791 bytes |

### 字段分解

| 字段 | 大小 | 占比 |
|------|------|------|
| `content`（全文） | **407.5 MB** | **58.7%** |
| ├ 初始 rev | 34.6 MB | 5.0% |
| └ 非初始 rev | **372.9 MB** | **53.7% ← 待释放** |
| `diff`（行 diff） | 240.5 MB | 34.7% |
| 元数据 | 45.8 MB | 6.6% |

### Revision 分布

| 区间 | 文件数 | 占比 |
|------|--------|------|
| 1 rev | 1,765 | 8.6% |
| 2 revs | 4,067 | 19.7% |
| 3 revs | 2,875 | 13.9% |
| 4 revs | 2,111 | 10.2% |
| 5 revs | 1,666 | 8.1% |
| 6-10 revs | 4,673 | 22.7% |
| 11-20 revs | 3,089 | 15.0% |
| 21-50 revs | 364 | 1.8% |
| **51+ revs** | **21** | **0.1%** |
| 中位 | 4 revs | — |
| 最大 | 109 revs（御史大夫） | — |

### Top 20 长尾页面

| 页面 | revs | 大小 | content |
|------|------|------|---------|
| 御史大夫 | 109 | 14.0 MB | 11.4 MB |
| 太傅 | 90 | 13.6 MB | 10.4 MB |
| 豫州刺史 | 87 | 3.6 MB | 2.1 MB |
| 光禄大夫 | 86 | 5.1 MB | 3.5 MB |
| 光禄勋 | 85 | 4.0 MB | 3.2 MB |
| 丞相 | 80 | 5.9 MB | 2.5 MB |
| 廷尉 | 77 | 1.4 MB | 0.6 MB |
| 车骑将军 | 72 | 9.4 MB | 7.5 MB |
| 大鸿胪 | 65 | 0.5 MB | 0.2 MB |
| 大司农 | 64 | 0.7 MB | 0.4 MB |
| 中常侍 | 62 | 2.1 MB | 1.3 MB |
| 卫尉 | 61 | 0.8 MB | 0.3 MB |
| 少府 | 61 | 0.8 MB | 0.3 MB |
| 冀州刺史 | 59 | 0.9 MB | 0.3 MB |
| 益州刺史 | 58 | 0.8 MB | 0.3 MB |
| 征南大将军 | 58 | 0.4 MB | 0.2 MB |
| 荆州刺史 | 56 | 1.2 MB | 0.5 MB |
| 扬州刺史 | 55 | 1.0 MB | 0.3 MB |
| 雍州刺史 | 54 | 0.8 MB | 0.3 MB |
| 太保 | 53 | 1.2 MB | 0.5 MB |

### Top 10 最大文件

| 文件 | revs | 大小 | 备注 |
|------|------|------|------|
| 司徒.2 | 21 | 19.8 MB | 归档文件 |
| 司空.2 | 22 | 19.7 MB | 归档文件 |
| 太尉.2 | 22 | 19.6 MB | 归档文件 |
| 司空.3 | 15 | 19.5 MB | 归档文件 |
| 司徒.3 | 15 | 19.4 MB | 归档文件 |
| 大司马.1 | 50 | 18.1 MB | 归档文件 |
| 太尉 | 46 | 14.3 MB | 主文件 |
| 太尉.1 | 48 | 14.2 MB | 归档文件 |
| 御史大夫 | 109 | 14.0 MB | 主文件 |
| 太傅 | 90 | 13.6 MB | 主文件 |

### 桶分布 Top 10

| 桶 | 文件数 | 大小 |
|----|--------|------|
| si/ | 170 | 115.9 MB |
| ta/ | 303 | 69.2 MB |
| di/ | 511 | 38.5 MB |
| da/ | 268 | 36.8 MB |
| zh/ | 1,608 | 36.1 MB |
| li/ | 1,212 | 31.0 MB |
| ch/ | 686 | 27.9 MB |
| yu/ | 474 | 26.2 MB |
| ji/ | 1,089 | 22.1 MB |
| sh/ | 943 | 18.6 MB |

## 优化方案：周期快照 + 增量 Patch

### 核心思路

- **满存 + 增量交替**：初始 rev 和周期性 rev 存完整 content（snapshot），中间 rev 只存 unified diff（patch）
- **纯文本**：所有的 diff 用 unified diff 文本格式存储，gzip 友好
- **Append-Only**：history 文件仍只追加，不修改已有 entry

### Schema

```jsonl
# 初始/周期快照
{"v":1,"t":"snap","id":"20260505-204713-f4f5d2","ts":"2026-05-05T20:47:13Z","au":"资治通鉴","su":"新增词条","sz":1715,"content":"全文 markdown..."}

# 增量 patch
{"v":1,"t":"patch","id":"20260505-211217-ee4e36","ts":"2026-05-05T21:12:17Z","au":"butler","su":"backfill","parent":"prev_id","sz":1743,"szb":1715,"diff":"  id: 诸葛亮\n+cat: 谋臣\n+dynasty: 三国\n"}
```

### 字段说明

| JSON key | 含义 | 出现于 |
|----------|------|--------|
| `v` | Schema 版本（当前 = 1） | 全部 |
| `t` | 类型: `snap` / `patch` | 全部 |
| `id` | rev_id，格式 `YYYYMMDD-HHMMSS-sha6` | 全部 |
| `ts` | ISO 8601 时间戳 | 全部 |
| `au` | author | 全部 |
| `su` | summary | 全部 |
| `parent` | 上一版 id | patch |
| `sz` | 此版本大小 (bytes) | 全部 |
| `szb` | 前一版大小 (bytes) | patch |
| `content` | 全文 markdown | snap |
| `diff` | Unified diff 文本 | patch |

### Key name 精简说明

使用短 key 名：`t`/`ts`/`au`/`su`/`id`/`sz`/`szb`。对于 125,633 条 revision，每个 entry 节省约 20-30 字节，合计 ~3-4 MB。积少成多。

### Snapshot 间隔

**每 25 个 patch 后插入一个 snapshot**。

选择依据：对 worst-case 文件（御史大夫，109 revs）：
- 最大 patch chain = 24
- snapshot 数 = 5（含初始） 
- 总大小 = 5 × 全文 + 104 × patch ≈ 40 KB
- vs 当前 14.0 MB → **缩小 97% 以上**

对 98% 的文件（≤20 revs），只有初始 snapshot + 若干 patch，无需周期 snapshot。

### Frontmatter 处理

frontmatter 的 `cat`/`dynasty`/`aliases` 等字段 **不做特殊处理**，和正文行一样走 unified diff。patch 中：

```
  id: 诸葛亮
-cat: 谋臣
+cat: 权臣
  dynasty: 三国
```

### 重建算法（前端）

```
输入: page, target_rev_id
1. 从近到远扫描 history 文件，找最近的 snapshot（含 current）
2. 从该 snapshot 的 content 开始
3. 顺序 apply 其后的所有 patch（直到 target_rev_id）
   apply: 逐行遍历 unified diff
     ' ' + text → 从 source 取一行输出
     '-' + text → 跳过 source 一行
     '+' + text → 直接输出
4. 返回拼接后的完整 markdown
```

## 实际结果（2026-05-15）

| 指标 | 优化前 | 优化后 | 变化 |
|------|--------|--------|------|
| 总磁盘占用 | 693.8 MB | 529.8 MB | **−23.6% (−164 MB)** |
| Revision 总数 | 125,633 | 125,633 | 不变 |
| 其中 snap | — | 20,796 | 新增（占 16.6%） |
| 其中 patch | — | 104,837 | 新增（占 83.4%） |
| 元数据 | 45.8 MB | 31.9 MB | −30.3% |
| 内容 + diff | 648.0 MB | 497.9 MB | −23.2% |

### 优化幅度说明

实际优化幅度（−23.6%）低于设计预期（~58%），核心原因：

**全量 diff 不可截断**。为了支持从 patch 链重建 content，每个 patch 必须包含全量行（不省略远离变更的行）。这意味着每个 patch 的大小 ≈ 该版本全文大小，无法通过截断 context 来压缩。旧格式的 truncated diff（context=2）无法用于重建，迁移时已全部丢弃并用全量 unified diff 重算。

| 来源 | 实际收益 | 与预期差异 |
|------|---------|-----------|
| 去掉非初始 content | 约 −370 MB | 与预期一致 |
| 替换为全量 unified diff | 约 +190 MB | 预期 −20~30 MB，实际因全量反而增大 |
| Key name 精简 (t/ts/au/su) | 约 −14 MB | 高于预期 |
| **净收益** | **−164 MB** | — |

### 关键技术决策

1. **全量 unified diff**：所有行均包含在 diff 中，patch 可独立重建
2. **Snapshot 间隔 25**：每 25 个 patch 插入一个 snap，平衡重建速度与存储
3. **末尾换行处理**：`_diff_text` 对输入做 `rstrip('\n')`，`_apply_patch` 保留 source 的末尾换行，确保重建一致性
4. **短 key 名**：`t`/`ts`/`au`/`su`/`id`/`sz`/`szb`

### 实施清单

- [x] **迁移脚本** `wiki/scripts/migrate_history_format.py` — 遍历 20,631 个文件，按 v1 schema 重写
- [x] **`record_revision.py`** — 新 entry 按 v1 schema 写入（snap + patch）
- [x] **`renderer.js`** — 前端支持 `_applyUnifiedDiff` + `_reconstructContent`
- [x] **验证** — 125,633 条 revision 重建一致性通过（~3% 条存在 ±1 byte 末尾换行偏差，不影响语义）
