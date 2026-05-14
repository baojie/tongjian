---
name: skill-butler-6
description: Butler 离线质检 — 异步扫描 wiki/public/pages/ 所有词条，验证引文可溯源、事实有出处、无幻觉内容。独立于 W4 在线评估，可批量运行，输出可疑列表供人工复核或自动修复。
---

# SKILL W6: 离线质检 (Citation Integrity Check)

> **核心问题**：wiki 里的每一句话，是真的来自《资治通鉴》原文，还是 AI 编造的？

---

## 一、触发时机

- W5 反思发现大量新页后，主动触发
- 用户手动运行 `check_citations.py`
- 每 20 次 butler invocation 自动触发一次（W5 负责调度）

---

## 二、检查项目

### 2.1 直接引文验证（最高优先级）

**规则**：页面中用 `"…"` 全角引号或 `>` 引用块包裹的文字，必须能在 `corpus/raw/资治通鉴.txt` 中 grep 到。

> ⚠️ **验证目标是 `corpus/raw/资治通鉴.txt`（294卷原文），不是卷节页**
> 卷节页含 `[NNN-PPP]` 标注和 wikilink `[[]]`，字符串匹配会误判。

```bash
# 提取页面中所有引文，逐条验证（resolve_page_file 定位分桶路径）
PAGE=$(python3 -c "from wiki.scripts.page_bucket import resolve_page_file; from pathlib import Path; print(resolve_page_file(Path('wiki/public/pages'), '商鞅'))")
python3 wiki/scripts/butler/check_citations.py "$PAGE"
```

**判定**：
- ✅ `corpus/raw/资治通鉴.txt` 中精确/模糊命中 → 通过
- ❌ 未命中 → 标记 `FABRICATED_QUOTE`，列入修复队列

**已知局限**：行内 `"…"` 可能包含分析性叙事而非人物对话，blockquote（`>` 引用块）检出的 false positive 率更低。质检结果需人工复核确认后再自动修复。

### 2.2 事实断言溯源

**规则**：以下类型的断言必须有出处：
- 人物关系（原文中有对应段落 + PN 编号）
- 重要事件（原文中有对应卷目和段落编号）
- 诏令奏疏出处（原文中有完整文本）

**验证方法**：
```bash
# 检查页面中的结论性陈述是否有 PN 标注支撑（resolve_page_file 自动定位）
python3 -c "from wiki.scripts.page_bucket import resolve_page_file; from pathlib import Path; import re; text=resolve_page_file(Path('wiki/public/pages'), '商鞅').read_text(); print(len(re.findall(r'（\d{3}-\d{3}）', text)))"
```

### 2.3 内容来源比例

每个旗舰页（quality: premium）需满足：
- 至少 60% 的内容段落能追溯到具体卷目
- 不得有超过 2 段"纯推断性"文字（无任何原文支撑）

---

## 三、输出格式

扫描完成后写入 `wiki/logs/butler/citation_issues.jsonl`，每行一个问题：

```json
{
  "ts": "2026-04-23T10:00",
  "page": "商鞅",
  "issue_type": "FABRICATED_QUOTE",
  "severity": "critical",
  "content": "疑似编造的引文内容",
  "line_no": 116,
  "quote_type": "blockquote",
  "grep_result": "not_found",
  "action": "delete_and_replace",
  "status": "open"
}
```

`severity` 级别：
- `critical`：直接引文无法在原文找到（必须修）
- `warning`：断言无出处（建议修）
- `info`：出处存在但标注不规范（可选修）

---

## 四、修复流程

### 自动修复（critical 级别）

Butler 可自动执行：
1. 删除无法溯源的引文，替换为 `<!-- [W6质检删除] ... -->` 占位符
2. 调用 `record_revision.py` 写入修订历史
3. 重新计算 quality 标签（可能降级）

```bash
PAGE=$(python3 -c "from wiki.scripts.page_bucket import resolve_page_file; from pathlib import Path; print(resolve_page_file(Path('wiki/public/pages'), '商鞅'))")
python3 wiki/scripts/butler/check_citations.py --fix-critical "$PAGE"
```

> ⚠️ **编辑接口规范（W0 不变量）**：所有修改 `wiki/public/pages/` 下文件的操作，
> 无论是脚本、`fix_critical`，还是人工直接编辑——都必须随后调用：
> ```bash
> python3 wiki/scripts/record_revision.py <slug> --summary "W6质检/fix-critical: ..." --author butler
> ```
> 跳过此步骤将导致修订历史断档，页面变更对用户不可见。

### 人工复核（warning 级别）

Butler 生成修复建议，但不自动执行：
1. 在 `citation_issues.jsonl` 标记 `action: human_review`
2. 在 W5 反思报告中列出清单
3. 等待用户确认或提供正确出处

---

## 五、check_citations.py 规格

`wiki/scripts/butler/check_citations.py` 已实现，支持：

```
输入: 页面路径（或 --all 扫全部，--featured 扫精品页）
输出: citation_issues.jsonl 追加

检查逻辑:
1. 提取页面中所有 "…"/"…" 引号内文字 和 > 引用块
2. 清洗标点空格，取核心片段（≥8字，去掉省略号两端）
3. 模糊匹配 corpus/raw/资治通鉴.txt（精确→标准化→滑动窗口三级）
4. 未命中 → FABRICATED_QUOTE (critical)
5. 匹配成功 → 记录通过
```

---

## 六、质检覆盖计划

| 阶段 | 范围 | 预期 |
|---|---|---|
| 第一轮 | quality=premium/featured 精品页 | 快速验证脚本有效性 |
| 第二轮 | 全部人物页 | 系统性排查 |
| 持续 | 每次 butler 写新页后增量扫 | 按页增量 |

---

## 七、与其他 Skill 的关系

- **W3**：定义溯源红旗（W6 是批量实现）
- **W4**：单页在线检查（W6 是离线批量检查）
- **W5**：W6 发现的 critical 问题自动进入下轮反思议程

---

## 八、非目标

- 不检查语言风格（那是可读性问题，W3 维度5）
- 不验证历史分析的"正确性"（只验证是否来自原文）
- 不做跨版本比对（只验证知识库内部一致性）

---

## 相关

- [W3 质量标准](SKILL_W3_Butler质量标准.md) — 溯源红旗定义
- [W4 评估与检验](SKILL_W4_Butler评估与检验.md) — 步骤0溯源验证
- `wiki/scripts/butler/check_citations.py` — 验证脚本
- `wiki/logs/butler/citation_issues.jsonl` — 质检结果日志
