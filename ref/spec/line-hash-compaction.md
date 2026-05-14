# Line-Hash History 存储实验

## 背景

History v1（snap + unified diff patch）将 693.8 MB 压缩至 529.8 MB（-23.6%），但全量 unified diff 包含所有行，patch 大小≈全文。核心矛盾：**重建要求 diff 不可截断，不截断则 patch ≈ full content**。

行级内容寻址方案绕过这个矛盾：每行用 hash 标识，版本只存 hash 数组。Snap 存完整数组，Delta 只记录变更的 [position, hash] 对。相同的行在不同版本间共享 hash，零冗余。

## 方案设计

### Hash 算法

```
sha256(line_content).hexdigest()[:N]
```

- 默认 N=6（16^6 = 16.7M 空间）
- 碰撞检测：注册时检查 hash 是否已被不同行占用；若是，N+=1 重试，最多 16 位
- 碰撞率（预研采样 ~30% 页面）：6 位约 0.9%，7 位接近 0%
- 确定性：同一行内容始终产出同一 hash

### 全局行索引

按拼音桶分片，每桶一个独立 JSON 文件 `line_index/<bucket>.json`：

```json
{
  "a1b2c3": "id: 刘备",
  "d4e5f6": "type: person",
  "g7h8i9": "label: 刘备",
  ...
}
```

索引构建来源：
1. `pages/<bucket>/*.md` — 当前页面内容
2. `history/<bucket>/*.jsonl` — 所有历史版本的 content 字段（确保已删除/已变更的行也可查询）

### v2 Entry 格式

**Snap（完整 hash 数组，每 26 个 delta 后插入一个）：**

```json
{"v":2,"t":"snap","id":"...","ts":"...","au":"...","su":"...","sz":1715,"ch":"sha256:...","ln":["a1b2c3","d4e5f6",...]}
```

- `ln` = line hashes array，顺序对应文件行
- 其余元数据与 v1 一致

**Delta（只记录变更行）：**

```json
{"v":2,"t":"delta","id":"...","parent":"...","ts":"...","au":"...","sz":1743,"szb":1715,"ch":"sha256:...","dl":[[2,"x7y8z9"],[5,"z0a1b2"]]}
```

- `dl` = delta lines: [[line_index, hash], ...]，line_index 是 parent 中的 0-based 行号
- 只保存 hash 发生变化的位置

**V1->V2 字段变更：**

| v1 | v2 | 说明 |
|----|----|------|
| `content` | `ln` | 全文 → hash 数组 |
| `diff` | `dl` | unified diff → 位置变更列表 |

### 重建算法

```
输入: page, target_rev_id

1. 获取该页面的所有 entry（主文件 + 归档文件）
2. 获取对应桶的行索引 line_index.json
3. 从 target_rev_id 向前找到最近的 snap
4. 从 snap 的 ln 数组开始：
   a. 如果 target 是 snap：ln.map(h => index[h]).join('\n')
   b. 如果 target 是 delta：顺序应用 dl 变更到 ln 数组，然后 lookup
5. 返回重建后的完整文本
```

### 存储估算

| 组件 | 估算大小 | 说明 |
|------|---------|------|
| Snap entries（~20K） | ~8 MB | 每个约 400 bytes（header + L×9 chars） |
| Delta entries（~105K） | ~21 MB | 每个约 200 bytes（header + 10×12 bytes） |
| 行索引（109 桶） | ~40 MB | 所有页面 + 历史版本的唯一行 |
| **总计** | **~69 MB** | vs v1 529.8 MB（-87%） |

## 实施与结果

### 实施步骤

1. `wiki/scripts/build_line_index.py` — 构建全局行索引
2. `wiki/scripts/conv_to_v2.py` — 单页 v2 转换 + 重建验证
3. `wiki/public/js/renderer.js` — 前端修改支持 v2 重建
4. 抽样 461 页全部通过重建验证

### 关键设计变更

**Delta 格式：基于 LCS 的编辑操作，而非位置比较。**

最初尝试按位置比较 hash 数组（逐位对比，记录不同的位置），但插入一行会导致后续所有行列移位，产生大量伪 diff。改用 `difflib.SequenceMatcher` 计算 hash 数组的 LCS，生成 `ins`/`del` 操作序列：

```json
"dl": [["ins", 5, "a1b2c3"], ["del", 3]]
```

应用时顺序执行 splice 操作，准确还原目标行阵列。

### 结果

| 指标 | v0（全文） | v2（行 hash） | 变化 |
|------|-----------|--------------|------|
| 单页 history 大小（诸葛亮，16 rev） | 70.0 KB | 7.1 KB | **−89.9%** |
| 单页 history 大小（丞相，80 rev） | 5,920.3 KB | 363.6 KB | **−93.9%** |
| 行索引（109 桶） | — | 92.9 MB | 新增 |
| 抽样 461 页重建 | — | 全部通过 | 0 误差 |
| 前端加载成本 | 直接读 content | 单次加载桶索引 (~370 KB avg) | 多 1 次 HTTP 请求 |

#### 行索引大小

| 桶 | 唯一行 | 索引大小 |
|----|-------|---------|
| zh/（最大） | 41,108 | 6,535 KB |
| li/ | 37,438 | 6,361 KB |
| di/（卷页面） | 46,080 | 14,562 KB |
| 其他桶 (avg) | ~3,500 | ~500 KB |

#### 抽样验证详情

从 109 桶随机抽样 500 个页面：

| 通过 | 失败 | v0 总大小 | v2 总大小（不含索引） | 缩减率 |
|-----|------|----------|-------------------|-------|
| 461 | 39¹ | 12.4 MB | 1.4 MB | **−88.8%** |

¹ 39 页因页面已被删除（history 留存但 .md 已不存在）无法转换，不影响 v2 方案有效性。

### 结论

**行 hash 方案可行，存储效率极高（−89~94%），但引入行索引作为额外的运行时依赖。**

对前端的影响：
- 浏览 history 页面时需加载桶索引 JSON（平均 500 KB，最大 14 MB）
- 索引在同一个会话内缓存复用
- 相较快照内容直接读取，多一次网络往返

对后端的权衡：
- 行索引 92.9 MB + v2 history ~40 MB = 总存储 ~133 MB
- 对比 v0 529.8 MB，**净节省 ~75%**
- 行索引需在内容变更时增量更新

### 实验分支

实验代码保存在 `linehash-experiment` 分支。报告已写入 `ref/spec/line-hash-compaction.md`。
