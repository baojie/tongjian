---
name: skill-butler-7
description: W7 增量引文真实性核验 — 三层流水线（缓存→规则→LLM），每次检查一个页面，已验证的句子不重复检查。与 W6 离线质检互补：W6 批量扫描，W7 增量精查+自动修复。
---

# SKILL W7: 增量引文真实性核验

> **核心问题**: 每个 wiki 引文是真实来自《资治通鉴》原文，还是 AI 编造/改写的？
> **与 W6 的分工**: W6 批量全扫（detect-only），W7 增量精查（detect+fix，用 LLM 二审）。

---

## 一、流水线

```
L0: 缓存命中（quote_cache.json，key = sha256[:16]）
      ok/llm_ok → 跳过 L1/L2，仍做 PN 比对
      fabricated/llm_fail → 完全跳过
      ↓ 未命中
L1: corpus_search 规则匹配
      score ≥ 0.90 → ✅ ok，写缓存 → PN 比对
      score 0.55–0.90 → 近似命中（情况 A）→ L2 修复
      score < 0.55   → 未命中（情况 B/C）

PN 比对（quote 存在 + 有 cited PN）
      cited PN ≠ actual PN → ⚠️ WRONG_PN (warning, fix_pn)
      cited PN = actual PN → ✅

L2: LLM 修复（本 butler 实例直接操作，≤8次/轮）
  情况 A：近似命中 → 取 corpus_search 最佳匹配条目 + wiki 上下文，LLM 提取正确原文引文
  情况 B：未命中 + 有 cited PN → 取对应卷节页 PN 段落 + wiki 上下文
  情况 C：未命中 + 无 cited PN → 直接 FABRICATED，不调 LLM

  LLM 返回：
    replacement   → 从原文提取的正确引文（≤60字，原文字面）
    context_ok    → "yes|partial|no"（周围解释文字是否含义匹配）
    context_issue → 解释文字存在的问题描述（≤30字）

  决策：
    replacement 有效 → ⚠️ NEAR_MATCH (warning, replace_quote)
                       若 context_ok≠yes → 附加 context_issue
    replacement 为空  → ❌ FABRICATED (critical)
```

**token 控制**：每次运行最多 8 次 LLM 调用。

---

## 二、触发时机（在 butler 周期中的位置）

### 主触发：每 10 次 action 后

累计 action ≥ 10 条未做 W7 → 插入一次 `verify-citations` 动作。

### 补充触发：queue 为空时

当 `queue.md` 无 P0/P1 任务时，优先跑 W7 而非 explore。

### 手动触发

```bash
# 检查下一个未扫描页（butler 每轮调用一次）
# 按 W7 步骤手动执行

# 查看已有问题
tail -20 wiki/logs/butler/citation_issues.jsonl
```

---

## 三、执行步骤

### 步骤 1 · 选页

从 `wiki/public/pages/` 中选取一个尚未检查的页面。

判断是否已检查：
- 查 `wiki/logs/butler/verify_state.json`（若不存在则新建空状态）
- 查 `wiki/public/pages/*/*.md` 中未被 `verify_state.json` 记录的页面

### 步骤 2 · L0 缓存检查

对页面中每个 `"…"` 引文，计算 `sha256[:16]`，查 `wiki/logs/butler/quote_cache.json`：
- `"ok"` / `"llm_ok"` → 跳过
- `"fabricated"` / `"llm_fail"` → 完全跳过
- 未命中 → 进入 L1

### 步骤 3 · L1 corpus_search 匹配

```bash
# 从页面提取引文片段，用 corpus_search 验证
python3 wiki/scripts/butler/corpus_search.py "引文片段" --max 5
```

判断标准：
- 首条结果 score 接近 1.0（PN 段落精确包含该片段）→ ✅ 通过
- 找到近似段落但文字不完全一致 → 进入 L2 情况 A
- 无结果但有 cited PN → 进入 L2 情况 B
- 无结果且无 cited PN → ❌ FABRICATED

### 步骤 4 · L2 LLM 修复

对需要 LLM 的案例：
1. 从 `corpus_search.py` 结果复制最佳匹配的原文段落
2. 从 wiki 页面复制含引文的上下文段落
3. 让 LLM 判断：引文是真实来自原文还是编造的？
4. 若要修复，从原文提取正确的字面片段

### 步骤 5 · 写入结论

更新缓存 `wiki/logs/butler/quote_cache.json`：

```json
{
  "sha256[:16]": {
    "status": "ok|fabricated|llm_ok|llm_fail",
    "method": "rule|llm",
    "confidence": 0.95,
    "found_pn": "002-010",
    "suggestion": "原文正确引法（如适用）",
    "checked_at": "2026-04-23T..."
  }
}
```

追加到 `wiki/logs/butler/citation_issues.jsonl`（与 W6 共用）：

```json
{
  "ts": "2026-04-23T...",
  "page": "商鞅",
  "issue_type": "FABRICATED_QUOTE|NEAR_MATCH|WRONG_PN",
  "severity": "critical|warning",
  "content": "引文原文",
  "action": "delete_and_replace|fix_pn|human_review",
  "status": "open"
}
```

### 步骤 6 · 自动修复

若 `NEAR_MATCH` 且 `context_ok=yes`：
1. 用 `edit_page.py` 替换引文为原文正确字面
2. 调用 `record_revision.py` 记录修订

若 `FABRICATED`：标记删除候补，但不自动删除（需人工确认）

---

## 四、持久化文件

| 文件 | 作用 |
|------|------|
| `wiki/logs/butler/quote_cache.json` | 引文验证缓存；key = sha256(标准化引文)[:16] |
| `wiki/logs/butler/verify_state.json` | 页面扫描进度；记录已检查的页面列表 |
| `wiki/logs/butler/citation_issues.jsonl` | 问题输出；与 W6 共用（追加写） |

---

## 五、butler 动作记录

W7 运行后需写 `actions.jsonl`：

```json
{
  "ts": "2026-04-23T...",
  "mode": "observe",
  "action": "verify-citations",
  "target": "商鞅.md",
  "rationale": "W7 增量引文核验",
  "score_before": null,
  "score_after": null,
  "red_flags": [],
  "diff_lines": 0,
  "verdict": "accept",
  "commit": null
}
```

---

## 六、错误处理

- **corpus_search 失败**：自动降级为 L0 缓存 → 直接标记 `UNVERIFIED_QUOTE (warning)` 待复查
- **缓存文件损坏**：删除后重建
- **页面路径不存在**：写 failures.jsonl，跳下一页

---

## 七、非目标

- 不验证语言风格或文学质量
- 不做跨版本比对（仅验证资治通鉴原文）
- 不处理已有 `status: fixed/rejected/skipped` 的 issues

---

## 相关

- [W6 离线质检](SKILL_W6_Butler离线质检.md) — 批量扫描，W7 的前置互补
- [W3 质量标准](SKILL_W3_Butler质量标准.md) — 引文溯源标准
- [W4 评估与检验](SKILL_W4_Butler评估与检验.md) — 步骤0溯源验证
- `wiki/scripts/butler/corpus_search.py` — L1 规则匹配工具
- `wiki/logs/butler/quote_cache.json` — L0 缓存
- `wiki/logs/butler/citation_issues.jsonl` — 问题日志
