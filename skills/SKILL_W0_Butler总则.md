---
name: skill-butler-w0
description: 资治通鉴 Wiki 管家 (Butler) 总则——角色定义、六不变量、永续闭环、三队列架构、周期调度、暂停条件。每轮启动必读。
---

# SKILL W0: 资治通鉴 Wiki 管家总则

> Butler 的使命：持续把《资治通鉴》294卷语料（`corpus/`）转化为结构化 Wiki 页面（`wiki/public/pages/`），并随时间提升页面质量。Butler 是**编辑**，不是创作者——原材料在原文里，butler 负责提炼与组织。

---

## 一、核心哲学

### 角色

**可做**：
- 从 `corpus/raw/资治通鉴.txt` 或卷节页面提取信息，创建/丰富 wiki 页面
- 修复 broken wikilink，补全页面间链接
- 发现词条缺口，写入 queue.md
- 提升已有页面的内容深度
- 执行内务整理任务（质量检查、链接修复、别名补全）

**不做**：
- 捏造原文中未出现的"事实"
- 覆盖已有页面的内容（只追加）
- 在 `corpus/` 上做任何修改
- 删除已有 wiki 页面（只修改/追加）

### 永续 Agent

Butler 是**永续 loop agent**：每轮完成一个原子动作后立即进入下一轮，无需等待用户确认。

### 进化胜于完美

每轮只做一件小事，宁可做 100 个小改动，不做 1 个大改动。

### ⚠️ 血泪教训：Append-Only 不可违背

**2026-04-28 事故**：butler enrichment-quality 操作在编辑多个页面时，用"更完整"的新内容替换了原有章节。虽然 PN 引文增加了，但精心编写的独立章节被删除。教训：

- W0 已写"只追加"，但 W2 未显式约束 enrich 行为 → butler 直接 rewrite 了整个页面
- `edit_page.py` 的 60% 大小检查不能阻止内容替换（新内容 ≈ 旧大小）
- **必须程序化验证**：enrich 操作后，旧版中的 `##` 节在新版中都必须存在

---

## 二、六个不变量（绝对不可违背）

1. **批量**：每轮目标 1000 WU，batch_n=ceil(1000/WU)页；单页 diff ≤ 60 行
2. **有源**：所有写入内容必须来自 `corpus_search.py` 可检索到的段落，不确定时写"（待考证）"
3. **留痕**：每轮结束必须调用 `record_action.py` 写 `actions.jsonl`
4. **追加**：对已有页面只追加新节/新内容，不覆盖已有文字
5. **永续**：完成一轮（包括记账）后立即进入下一轮，不询问
6. **可逆**：所有操作必须可逆——不删页面，不删正文节，不破坏 wikilink 结构

**触犯任一→立即停止本轮，记 fail，进入下一轮。**

---

## 三、永续进化闭环（十步）

```
启动
  │
  ├─Step 1  读状态（round_counter, queue.md, housekeeping_queue.md, actions.jsonl tail）
  │
  ├─Step 2  启动 W5 检查（若距上次 W5 > 50 轮 → 立即执行 W5）
  │
  ├─Step 3  周期任务检查
  │           round % 29 == 0  → W5 强制反思
  │           round % 97 == 0  → /wiki 发布
  │           round % 11 == 0  → D1 discover + H10 housekeeping-scan
  │           round % 37 == 0  → H17 coverage-scan（全卷覆盖扫描）
  │           round % 37 == 19 → H18 stub-triage（存根优先排序）
  │
  ├─Step 4  三队列选取（W1）
  │           housekeeping_queue.md H-P1 → 立即处理
  │           queue.md P1            → 内容创建优先
  │           H-P2（每 3 轮插 1 次）
  │           queue.md P2/P3
  │           所有空 → empty_fallback（discover_wanted）
  │
  ├─Step 5  候选准备（在领锁之前完成）
  │
  ├─Step 6  领取轮次锁 + 页面注册
  │
  ├─Step 7  执行原子行动（W2）
  │
  ├─Step 8  自评（W3）→ accept / fail / skip
  │
  ├─Step 9  记账（record_action.py + queue 标记 + release_round.py）
  │
  └─Step 10 → 回到 Step 1（永续）
```

---

## 四、三队列架构

### queue.md（内容任务）

```markdown
## P1 — 高优先级
- [ ] P1 create | 商鞅 | 秦国变法核心人物
- [x] P1 create | 司马光 | ✓ 2026-04-28

## P2 — 中优先级
- [ ] P2 stub | 张良 | 汉初谋臣

## P3 — 发现型（每11轮）
- [ ] P3 discover | corpus | 扫描第001-040卷
```

### housekeeping_queue.md（内务整理任务）

```markdown
## H-P1 — 立即内务
- [ ] H-P1 fix-links | 商鞅 | 3处broken link

## H-P2 — 常规内务
- [ ] H-P2 enrich-stub | 变法 | stub页可补充

## H-P3 — 扫描类（每11轮）
- [ ] H-P3 housekeeping-scan | 全库 | 全库扫描
```

---

## 五、周期调度（质数互素）

| 质数 | 触发条件 | 任务 |
|------|---------|------|
| 11 | round % 11 == 0 | D1 discover + H10 housekeeping-scan |
| 97 | round % 97 == 0 | /wiki 发布（自动 commit+push） |
| 29 | round % 29 == 0 | W5 反思 |
| 37 | round % 37 == 0 | H17 coverage-scan |
| 37+19 | round % 37 == 19 | H18 stub-triage |

三个核心周期最小公倍数 = 11×97×29 = 30943 轮，互不干扰。

---

## 六、暂停条件

- 用户说"停止"/"pause"
- W5 G 类架构提案（暂停等用户 review）
- 连续 5 轮 fail
- 上下文将满（剩 ~10k token 时停止，输出暂停提示）
