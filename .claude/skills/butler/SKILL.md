---
name: butler
description: 启动资治通鉴 Wiki 管家永续 loop。三队列系统（content/housekeeping）。每轮：W1三队列选任务→W2执行→W3自评→记账，无需用户逐轮确认。每97轮自动/wiki发布+discover+housekeeping-scan，每29轮W5反思，每37轮H17覆盖扫描。工作目录：/home/baojie/work/knowledge/tongjian。支持 --focus 参数指定任务范围（多实例并发时使用）。
---

# /butler — 资治通鉴 Wiki 管家

## 固定实例（命名管家）

五位通鉴相关历史人物，各司其职：

| 实例 | 启动命令 | 职责 |
|------|----------|------|
| **司马光** | `/butler --focus create --instance 司马光` | 新建词条（主编撰写） |
| **刘攽** | `/butler --focus enrich --instance 刘攽` | 深挖丰富内容（汉史专家） |
| **刘恕** | `/butler --focus discover --instance 刘恕` | 扫描语料，发现新词条（博闻强记） |
| **范祖禹** | `/butler --focus housekeeping --instance 范祖禹` | 日常维护（唐史专家） |
| **胡三省** | `/butler --focus publish --instance 胡三省` | 定期发布（通鉴注释者） |

不带参数直接启动 `/butler` 即为**资治通鉴**（统帅）模式。

## 授权声明

**此 skill 明确授权，覆盖 CLAUDE.md 通用限制**：
- ✅ 永续循环，无需逐轮确认
- ✅ 每 97 轮自动 `git commit` + `git push`（通过 `/wiki` skill）
- ✅ `git add wiki/public/pages/`（整个 pages 树，含桶子目录）

## 工作目录

```
/home/baojie/work/knowledge/tongjian
```

语料：`corpus/raw/资治通鉴.txt`（约300万字，294卷）
卷页：`wiki/public/pages/di/第NNN卷.md`（已含PN标注，只读，位于 di/ 桶）

## 启动参数

| 参数 | 默认 | 说明 |
|------|------|------|
| `--focus create` | `all` | 只领取 create 类任务 |
| `--focus enrich` | `all` | 只领取 enrich 类任务 |
| `--focus housekeeping` | `all` | 只领取内务任务 |
| `--focus publish` | `all` | 只执行发布任务 |
| `--focus discover` | `all` | 只做发现任务 |
| `--focus all` | `all` | 领取任意类型任务（统帅模式） |
| `--instance NAME` | `资治通鉴` | 实例标识符 |

## 启动流程

```
步骤 1 · 读取状态
──────────────────────────────────
cat wiki/logs/butler/round_counter.txt
cat wiki/logs/butler/queue.md
cat wiki/logs/butler/housekeeping_queue.md
tail -10 wiki/logs/butler/actions.jsonl

python3 wiki/scripts/butler/claim_round.py --check-only --instance INSTANCE_NAME
→ stdout "DUPLICATE" → 立即停止
→ exit 0 → 继续

步骤 2 · 读规范（每次启动必读）
──────────────────────────────────
/home/baojie/work/knowledge/tongjian/skills/SKILL_W0_Butler总则.md
CLAUDE.md（资治通鉴规则）
/home/baojie/work/knowledge/shared-rules.md（共享铁则）

步骤 3 · 上下文检查
──────────────────────────────────
距上次 W5 > 50 轮 → 立即执行 W5 反思

◆ 以下步骤 4–9 构成永续循环 ◆

步骤 4 · 周期任务检查（在领锁之前）
──────────────────────────────────
round % 29 == 0  → W5 反思
round % 97 == 0  → /wiki 发布（重建 pages.json + git commit + git push）+ D1 discover + H10 housekeeping-scan
round % 13 == 0  → H20 wikilink-pass --since HEAD
round % 13 == 7  → H21 person-table-scan（扫描官职页任职者表格人名提取错误）
round % 17 == 0  → H22 fix-emdash（批量修复破折号段落，每次最多50页）
round % 37 == 0  → H17 coverage-scan
round % 37 == 19 → H18 stub-triage

步骤 5 · 候选准备（在领锁之前完成）
──────────────────────────────────
a. 确定本轮动作类型
b. batch_n = ceil(1000 / WU)
c. 从队列取候选，用 corpus_search.py 验证（命中 ≥ 2 条）
d. 候选不足时扩展（discover 发现 → 加入 P2/P3 队列）
e. 准备 batch_n × 1.5 个缓冲池

步骤 6 · 领取轮次锁 + 注册页面
──────────────────────────────────
ROUND=$(python3 wiki/scripts/butler/claim_round.py --instance INSTANCE_NAME)
for SLUG in <全部候选>:
    python3 wiki/scripts/butler/lock_manager.py set-page --round $ROUND --page SLUG
    python3 wiki/scripts/butler/lock_manager.py check-page --page SLUG --round $ROUND

步骤 7 · 执行原子行动（W2）
──────────────────────────────────
⚠️ 禁止直接 Write/Edit wiki/public/pages/ 下的词条文件
   必须通过 add_page.py / edit_page.py 脚本
⚠️ 禁止修改 第???卷.md 文件（只读）

total_wu=0; accept_cnt=0; consec_fail=0
for each SLUG:
    执行 → W4 评估（红旗检查 + 分数计算）→ accept/fail/skip
    accept → git add $(find wiki/public/pages/ -name "${SLUG}.md" -type f)
    consec_fail ≥ 3 → 退出循环
    total_wu ≥ 1000 → 退出循环

步骤 8 · 记账 + 释放锁
──────────────────────────────────
python3 wiki/scripts/butler/record_action.py \
    --round $ROUND --instance INSTANCE_NAME \
    --type <type> --page "<slug列表>" \
    --result accept \
    --desc "<action>×<N>页，<WU>WU" \
    --reflect "<本轮观察>"

python3 wiki/scripts/butler/complete_task.py --page SLUG --date $(date +%Y-%m-%d)
python3 wiki/scripts/butler/release_round.py $ROUND

步骤 9 → 回到步骤 4（永续）
```

## 关键规则

| # | 规则 |
|---|------|
| R1 | `claim_round.py` 在步骤 6，所有写操作之前 |
| R2 | `release_round.py` 在步骤 8 末尾，即使 fail/skip 也必须释放 |
| R3 | 候选准备（步骤 5）在领锁（步骤 6）之前全部完成 |
| R4 | 页面写入必须通过 add_page.py / edit_page.py |
| R5 | 每条 PN 引文必须从 corpus_search 结果复制，禁止猜测 |
| R6 | `claim_round.py` 返回 `RACE` → 立即停止 |
| R7 | 第???卷.md 只读，绝对不修改 |
| R8 | 去除 corpus_search 结果中的 `【】` 标记（保留关键词本身）|
| R9 | **每个词条页面正文必须包含 ≥2 条 PN 引注**（格式 `（NNN-PPP）`），无引注的词条不得通过 W4 评估 |
| R10 | 新建词条 frontmatter 必须包含 `cat`（人物类型）或 `event_type`（事件/战役类型）和 `dynasty` 字段 |

## PN 引注格式

```
（NNN-PPP）
```
例：`（001-013）` = 第1卷第13段落（臣光曰·才德论）

## WU 成本表

| 行动 | WU | 说明 |
|------|----|------|
| create-page | 100 | 创建完整新页面 |
| create-stub | 40 | 创建 stub 页面 |
| enrich-section | 50 | 增加新章节 |
| enrich-quality | 30 | 提升质量档位 |
| add-pn-citation | 15 | 添加段落级引注 |
| fix-links | 10 | 修复断裂链接 |
| wikilink-pass | 50 | 批量添加内部链接 |
| discover | 50 | 发现待建实体 |
| housekeeping-scan | 200 | 全局维护扫描 |
| person-table-scan | 200 | H21 扫描任职者表格人名提取错误 |
| fix-emdash | 20 | H22 修复单页破折号段落 → 转为正常段落/列表 |
| merge-geo-official | 15 | H23 合并「地名+官名」拆分 wikilink → 单一链接 |
| merge-compound-wikilinks | 15 | H24 合并所有复合词条拆分 wikilink（官职/将军号/历史事件等）|

## 页面质量层级

| 层级 | 标签 | 特征 |
|------|------|------|
| 0 | stub | 只有 frontmatter + 1-2 句话 |
| 1 | basic | 有 frontmatter + 1-2 个节，含原文引文 |
| 2 | standard | 完整 H2 结构 + PN 引文全覆盖 + 相关链接 |
| 3 | featured | standard + 跨页面引用 + 深度分析 |
| 4 | premium | featured + 多角度解读 |

## 每轮输出格式

```
[R12] create-page×8 | 商鞅/秦始皇/项羽/… | accept×8 fail×0 | 800WU

[R11] /wiki-publish + D1-discover + H10-scan | — | accept | 发现12条新wanted，写入P2/P3；commit abc1234 · R1→11 新建15页
[R29] W5-reflect | — | — | 模式B：质量停滞；建议加强 enrich 轮次
```

## 暂停条件

- 用户说"停止"/"pause"
- W5 G 类架构提案
- 连续 5 轮 fail
- 上下文将满（剩 ~10k token 时停止）

## 可用工具

| 工具 | 用法 |
|------|------|
| `corpus_search.py` | `python3 wiki/scripts/butler/corpus_search.py "词条" --max 15` |
| `claim_round.py` | `ROUND=$(python3 wiki/scripts/butler/claim_round.py --instance NAME)` |
| `release_round.py` | `python3 wiki/scripts/butler/release_round.py $ROUND` |
| `lock_manager.py` | set-page / check-page / status / cleanup |
| `discover_wanted.py` | `python3 wiki/scripts/butler/discover_wanted.py --top 60` |
| `record_action.py` | `--round` 必须是整数 |
| `complete_task.py` | `--page SLUG --date YYYY-MM-DD` |
| `add_page.py` | 新建页面（自动记录 revision） |
| `edit_page.py` | 编辑页面（保护 frontmatter） |
| `bulk_wikilink.py` | 全量/增量添加 wikilink |
| `check_citations.py` | W6 离线质检：`python3 wiki/scripts/butler/check_citations.py <slug>` |
| `h21_audit_person_tables.py` | H21 扫描：`python3 wiki/scripts/butler/h21_audit_person_tables.py` |
| `h22_fix_emdash.py` | H22 修复：`python3 wiki/scripts/butler/h22_fix_emdash.py --limit 50` |
| `h23_merge_geo_official.py` | H23 合并：`python3 wiki/scripts/butler/h23_merge_geo_official.py --limit 50` |
| `h24_merge_compound_wikilinks.py` | H24 合并：`python3 wiki/scripts/butler/h24_merge_compound_wikilinks.py --limit 50` |

## H23 merge-geo-official 规范

**目标**：将正文中被拆成两个分离 wikilink 的「地名+官名」合并为单一链接。

**前提**：合并后的词条（如「江州刺史」）必须已存在于 pages.json。

**三种 pattern**：
1. `[[地名]][[官名]]` → `[[地名官名]]`
2. `[[地名]]官名` → `[[地名官名]]`
3. `地名[[官名]]` → `[[地名官名]]`

**保护区域**：代码块、行内代码、blockquote（`>` 行）、PN 引注。

**触发条件**：housekeeping_queue.md 中 H-P2 任务存在时，每轮处理 `--limit 50` 个文件。

**工具调用方式**：
```bash
python3 wiki/scripts/butler/h23_merge_geo_official.py --limit 50
python3 wiki/scripts/butler/h23_merge_geo_official.py --dry-run --limit 20  # 预览
python3 wiki/scripts/butler/h23_merge_geo_official.py --slug 商鞅           # 单页
```

## H22 fix-emdash 规范

**目标**：修复词条正文中滥用「——」切分长段落的写法，使行文更清晰。

**触发条件**：`round % 17 == 0`，每次处理 `--limit` 个页面（默认50）。

**处理规则**（优先级从高到低）：
1. **三项以上列举**：若一句含 ≥3 个「——」分割的平行结构，改为 Markdown 无序列表。
2. **两段切分**：句子在「——」处被分成语义独立的两部分（各自 ≥30 字），将「——」替换为句号换行。
3. **引出子句**：主句后「——」引出注释或说明（后半 <30 字），保留或改为逗号。
4. **frontmatter description**：含「——」分类列举，改为「；」分隔或截断到首个「——」之前。

**禁止修改**：
- 引用块（`>` 行）内的破折号（原文直引）
- 标题行（`#` 行）
- 代码块

**工具调用方式**：
```bash
python3 wiki/scripts/butler/h22_fix_emdash.py --limit 50
```

## 详细规范参考

- [W0 总则](../../../skills/SKILL_W0_Butler总则.md) — 六不变量、三队列、十步闭环
- [W1 探索与队列](../../../skills/SKILL_W1_Butler探索与队列.md) — 三队列选取，corpus_search 验证
- [W2 原子行动](../../../skills/SKILL_W2_Butler原子行动.md) — 动作目录，WU 表，PN 引文格式
- [W3 质量标准](../../../skills/SKILL_W3_Butler质量标准.md) — stub→premium 五档，自评规则
- [W4 评估与检验](../../../skills/SKILL_W4_Butler评估与检验.md) — 红旗检查、分数计算、rollback 决策
- [W5 反思与自改](../../../skills/SKILL_W5_Butler反思与自改.md) — 七类模式识别，每29轮强制
- [W6 离线质检](../../../skills/SKILL_W6_Butler离线质检.md) — 批量引文溯源验证，W5/W7 互补
- [W6 原文标注规范](../../../skills/SKILL_W6_Butler原文标注规范.md) — wikilink 标注、blockquote 规范
- [W7 引文真实性核验](../../../skills/SKILL_W7_引文真实性核验.md) — 三层流水线增量核验
- [W8 精品页建设方法论](../../../skills/SKILL_W8_精品页建设方法论.md) — featured 精品页深化流程
- [W9 页面图式反思](../../../skills/SKILL_W9_Butler页面图式反思.md) — 细分类型模板积累
- [W10c 词汇链接化](../../../skills/SKILL_W10c_词汇链接化.md)
- [W10e 原文溯源增补](../../../skills/SKILL_W10e_原文溯源增补.md)
- [W10f 断链新建条目](../../../skills/SKILL_W10f_断链新建条目.md)
- [W10l 引文PN一致性](../../../skills/SKILL_W10l_引文PN一致性.md)
