---
name: skill-butler-w5
description: 资治通鉴 Wiki Butler 每29轮强制反思——七类模式识别，G类架构提案，反思报告格式。
---

# SKILL W5: 反思与自改

每 29 轮强制执行一次，或启动时距上次 > 50 轮。

## 反思输入

```bash
tail -50 wiki/logs/butler/actions.jsonl | python3 -c "
import sys,json
for line in sys.stdin:
    r=json.loads(line)
    print(f\"R{r['round']} {r['type']} {r['result']} | {r.get('reflect','')}\")
"
```

## 七类模式识别

| 类型 | 信号 | 建议行动 |
|------|------|---------|
| A 候选不足 | 连续 3 轮 discover 候选 < batch_n | 降低 corpus_search 门槛至 ≥1 条 |
| B 质量停滞 | 连续 10 轮 accept 但 quality 分不增长 | 改做 A2 enrich-page 代替 C1 stub |
| C PN 命中低 | fail 中有 "PN 捏造" | 加强 corpus_search 验证步骤 |
| D 队列积压 | P1 积压 > 20 条超过 5 轮 | 本轮只做 P1 清账 |
| E 重复词条 | 发现同人物多页（如「商鞅」「卫鞅」重复建页） | 写入 H-P1 deduplicate 任务 |
| F 卷目断层 | 某连续 10 卷无任何词条引用 | 针对该区间做 H17 coverage-scan |
| G 架构问题 | 页面类型定义混乱，或 PN 格式不统一 | 暂停，向用户提报架构提案 |

## 反思报告格式

```
[W5 反思 R{round}]
扫描轮次：R{last_reflect+1}—R{round}
accept: N 轮  fail: M 轮  skip: K 轮

识别模式：
  [A] 候选不足：第 X 轮起连续 N 轮 discover 结果 < batch_n
  → 建议：降低门槛至 corpus 命中 ≥1 条

健康指标：
  - 总词条数：N（非卷节页）
  - 质量分布：premium N / featured N / standard N / basic N / stub N
  - 本周期新增：N 页
  - broken links：N 处

下轮调整：
  [改] A1→C1：候选不足，临时降低 WU 目标
  [保] PN 验证步骤不变
```

## G 类提案格式

G 类问题必须暂停并向用户报告：

```
⚠️ [W5 G类提案] 发现架构问题，请用户 review：

问题：[具体描述]
影响：[影响范围]
建议方案A：[...]
建议方案B：[...]

等待用户指令，butler 暂停。
```
