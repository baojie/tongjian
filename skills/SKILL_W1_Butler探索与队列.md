---
name: skill-butler-w1
description: 资治通鉴 Wiki Butler 的三队列选取算法——优先级规则、候选准备、corpus_search验证、候选不足扩展规则。
---

# SKILL W1: 探索与队列

## 三队列选取算法

每轮按以下优先顺序选取任务：

```
1. housekeeping_queue.md 中的 H-P1（立即执行）
2. queue.md 中的 P1（内容创建高优先级）
3. housekeeping_queue.md 中的 H-P2（每 3 轮插 1 次）
4. queue.md 中的 P2
5. queue.md 中的 P3（每 11 轮 discover 时用）
   - P3 `discover` → 先 D1 扫描确定新候选
6. 空队列回退 → discover_wanted.py --top 30 发现新候选
```

## 候选准备（步骤5，在领锁前完成）

1. 确定本轮动作类型（A1/A2/C1/H2/...）
2. 计算 `batch_n = ceil(1000 / WU)`
3. 从队列获取候选，不足时用 `discover_wanted.py --top 60` 补充
4. 对每个候选用 `corpus_search.py` 验证（命中 ≥ 2 条才纳入）
5. 准备 `batch_n × 1.5` 个候选作为冲突缓冲池

## corpus_search 验证规则

```bash
python3 wiki/scripts/butler/corpus_search.py "词条名" --max 10
```

- 命中 ≥ 3 条 → 高质量候选，可做 A1 create-page（100WU）
- 命中 2 条   → 基础候选，做 C1 stub（40WU）
- 命中 1 条   → 仅做 C3 add-alias 或跳过
- 命中 0 条   → 跳过（无语料依据）

## 候选不足扩展规则

禁止在候选数 < batch_n 时直接收手。必须按顺序尝试：

1. `discover_wanted.py --top 100` 扩大搜索
2. 对已有页面的 broken wikilinks 做 corpus_search
3. 降低命中门槛至 ≥ 1 条（接受 basic 级）
4. 三步穷尽后仍不足 → 切换低 WU 动作补足 1000 WU

## PN 引文搜索

```bash
# 搜索特定词条的所有原文出处
python3 wiki/scripts/butler/corpus_search.py "商鞅" --max 15

# 限定卷号搜索
python3 wiki/scripts/butler/corpus_search.py "变法" --vol 2

# 输出示例：
# （第002卷-015） …【商鞅】推行变法，令行禁止…
```

## D1 发现任务（每 11 轮）

```bash
python3 wiki/scripts/butler/discover_wanted.py --top 60
```

发现结果写入 queue.md P3 区域：
```markdown
- [ ] P3 discover | 项羽 | [broken-link×8] 多页引用但无词条
- [ ] P3 discover | 刘邦 | [corpus-freq×12] 第001卷高频人名
```
