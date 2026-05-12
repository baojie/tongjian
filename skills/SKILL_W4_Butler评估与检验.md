---
name: skill-butler-4
description: Butler 行动后的评估逻辑 — 对比 before/after, 用 W3 rubric 打分, 决定 accept / rollback。包含红旗检查、分数计算、rollback 触发条件、评估日志字段。每个 atomic action 执行后必走一次。评估失败不等于内容 bug, 是进化反馈信号。
---

# SKILL W4: 评估与检验

> 每个行动后, butler 要**自问**: 这一步让 wiki 变好了吗? 如果变坏, 立即回滚, 记到 failures.jsonl, 留给 W5 反思。

---

## 一、评估时机

W2 执行完动作、写完 diff, 进入评估:

```
[action done] → [W4 评估] → accept → git commit
                         → fail → git restore + actions.result=rollback
```

**绝不跳过**。评估是不变量"可逆"的兑现。

---

## 二、评估步骤 (自顶向下)

### 步骤 0 · 溯源验证 (内容写入前的前置门槛，v0.2 新增)

**每次写入内容前，先问：这段内容从哪里来？**

Butler 只允许以下来源的内容进入 wiki：

| 内容类型 | 必须来自 | 验证方法 |
|---|---|---|
| 直接引文（引号内文字） | `corpus/raw/资治通鉴.txt` 原文 | `corpus_search.py "引文关键字" --max 5` 能命中 |
| 人物/事件事实 | `corpus/raw/资治通鉴.txt` 原文中的 PN 标注段落 | 对应卷节页（`第NNN卷.md`）有 PN 标注 |
| 事件/关系 | `corpus/raw/资治通鉴.txt` 原文段落 | 有对应卷目和段落编号 |
| 分析性结论 | 原文事实的归纳 | 必须有原文依据，不可凭空推测 |

**不允许**的内容来源：
- ❌ 训练数据中的历史知识（即使"大概率正确"）
- ❌ 其他史书中与资治通鉴记载不一致的内容（除非特别标注）
- ❌ 无法在原文中找到对应出处的任何断言

验证操作：
```bash
# 验证引文是否存在于原文
python3 wiki/scripts/butler/corpus_search.py "引文关键字" --max 5

# 验证 PN 是否对应正确卷目
grep "\[080-PPP\]" wiki/public/pages/第080卷.md
```

> ⚠️ **不得用 `corpus_search.py` 返回的标注片段直接做字符串匹配**：结果含 `【】` 标注，匹配前需去除。

**验证失败 → 删除该内容，不写入，记 actions.jsonl `citation_fail`**。

---

### 步骤 0.5 · 字数损失审查（每次编辑后强制执行）

**在步骤 1 之前**，对所有 edit 类动作必须运行：

```bash
python3 wiki/scripts/butler/check_size_loss.py <slug>
```

| 退出码 | 含义 | 处置 |
|---|---|---|
| `0` (safe) | 字数正常或增加 | 继续步骤 1 |
| `1` (warning) | 字数轻度缩减 10%–20% | 继续步骤 1，但在 actions.jsonl 记录 `size_warning: true`；若步骤 1 还发现其他问题则一并 rollback |
| `2` (critical) | **铁律违反 / 字数缩减 ≥ 20% / 其他关键节丢失** | **立即 rollback**，无需执行步骤 1–2；reasons 写入 failures.jsonl |

**铁律（独立于阈值参数，无条件 critical）**：`## 原文引文` 节丢失
- 此项由 `edit_page.py` 在写入前拦截（前置守卫），理论上不会到达此检查
- 若绕过脚本直接写入，此检查作为兜底检测

**其他关键节**（丢失即 critical）：`## 性格`、`## 主要事迹`

**frontmatter 字段**（丢失即 critical）：`pn:`、`tags:`

---

### 步骤 1 · 红旗检查 (一票否决)

对改动后的目标页, 检查 W3 §三 所有红旗:

- 🚩 frontmatter id 空或与 filename 不符 → **fail**
- 🚩 body 全表格无叙述 (create-stub 新页除外, 允许) → fail
- 🚩 broken 比例 > 50% → fail
- 🚩 单一源 (且本次动作未贡献跨源) → fail (可 observe-only 拉队列)
- 🚩 auto_generated 持续 > 30 天 → 非本次动作引入的不罚, **仅标记**给 W5
- 🚩 字数 < 50 (非 stub 新页) → fail
- 🚩 直接引文无法在 corpus 中 grep 到 → fail (v0.2)
- 🚩 有结论性陈述但无 PN 出处标注 → fail (v0.2)
- 🚩 blockquote 引文与页面主题不直接相关（见 W3 §引文相关性审计）→ fail

**任一红旗 → rollback**。

### 步骤 2 · 分数计算

5 维度 each 0–2 分:
- 0 = 不及格 (触红旗或明显不满足量化阈值)
- 1 = 及格 (满足最低量化阈值)
- 2 = 优秀 (明显超阈值 或命中加分项)

加分项 (W3 §四) 累计 += 1 (最多 +3)。

**总分** = sum(5 维度) + bonus, 范围 0–13。

**accept 门槛**:
- 原先页面分数 S_before
- 改动后分数 S_after
- 接受条件: `S_after >= S_before + 1` 或 `S_after >= 8` (已高分页面不要求每次都进步)

### 步骤 3 · 变动合理性

除了分数外, 检查**这次 diff 是否合理**:

- diff ≤ 20 行 (不变量) — 否 → rollback
- diff 只动 1 个文件 (除 `rebuild-registry`) — 否 → rollback
- 无意外删除 (git show 看 + 行 vs − 行, − 应为 0 或很少)
- 无引入新 broken link 却没在动作本意内

---

## 三、评估日志字段

追加到 `actions.jsonl` 当前行 (update, 不是新行):

```json
{
  ...(前面字段),
  "score_before": 6,
  "score_after": 7,
  "red_flags": [],
  "diff_lines": 8,
  "verdict": "accept",
  "commit": "abc1234"
}
```

若 `verdict:"fail"`:
```json
{
  ...,
  "verdict": "fail",
  "reason": "broken_ratio_too_high",
  "red_flags": ["broken_ratio>50%"]
}
```

若字数损失审查返回 warning：
```json
{
  ...,
  "size_warning": true,
  "size_loss_ratio": 0.15,
  "size_warning_reason": "字数轻度缩减 15%：1200 → 1020 bytes"
}
```

且同时在 `failures.jsonl` 追加相同的行 (便于 W5 专门扫失败)。

---

## 四、工具脚本

| 脚本 | 调用时机 | 退出码含义 |
|---|---|---|
| `wiki/scripts/butler/check_size_loss.py <slug>` | **每次 edit 后必调** | 0=safe, 1=warning, 2=critical→rollback |
| `wiki/scripts/butler/corpus_search.py <词条>` | 步骤 0 溯源验证 | 返回命中数和片段 |

### 分数计算脚本 (建议)

`wiki/scripts/butler/score_page.py` (v0 先不实现, 手工打分):
```
输入: 页面路径
输出: {
  "completeness": 2,
  "accuracy": 1,
  "link_density": 1,
  "source_diversity": 0,   ← 红旗来源
  "readability": 2,
  "bonus": 1,
  "total": 7,
  "red_flags": []
}
```

v0 期间 butler 手动打, 每次评估在 reflections/ 下或 actions.jsonl 里写分。

---

## 五、Rollback 决策

**硬性 rollback** (无条件):
- 任一红旗
- diff 违反原子性
- `git status` 显示 staged 文件有预期外文件

**软性 rollback** (提示人工):
- 分数不降不升 (S_after == S_before)
- 但本动作是 `create-stub` 且新页分 < 3

**不 rollback**:
- 分数小幅下降 (S_after = S_before - 1) 但属于 `fix-broken-link` 类"事情本该如此"动作

---

## 六、连续失败应对

`failures.jsonl` 最近 N 条命中**同一 action type**:

| N | 动作 |
|---:|---|
| 1 | 本次动作 rollback, 继续 |
| 2 | 下次 invocation 此 action type 禁用, 尝试其他 |
| 3 | **自动触发 W5 反思** |

---

## 七、手动评估 (用户 review 路径)

用户可随时抽查:

```bash
# 查最近 10 次 butler 动作
tail -50 wiki/logs/butler/actions.jsonl

# 查失败
cat wiki/logs/butler/failures.jsonl
```

若用户发现 accept 的动作其实有问题, 可:
1. git revert 那条 commit
2. 在 actions.jsonl 手动把 verdict 改 `user_reject`
3. 写一段说明放 `reflections/<date>-user-override.md`, 交 W5 下次处理

---

## 八、非目标

- 不做**绝对** quality 度量 (这是 W3 的渐进 rubric, 不是绝对值)
- 不做 A/B (一个改动, 对比前后)
- 不追溯历史 (S_before 是动作前的分, S_after 是动作后的分)

---

## 相关
- [W3 质量标准](SKILL_W3_Butler质量标准.md) — 打分 rubric 来源
- [W5 反思与自改](SKILL_W5_Butler反思与自改.md) — 连续失败的下一站
