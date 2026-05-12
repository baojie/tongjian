---
name: skill-butler-w2
description: 资治通鉴 Wiki Butler 的原子行动目录——A/B/C/D/E/H 组标准操作，WU成本，PN引文格式，页面写入铁律。
---

# SKILL W2: 原子行动目录

> 每轮按"工作量单位（WU）"批量执行同类动作，目标 **1000 WU / 轮**。
> `batch_n = ceil(1000 / WU)` — 每轮最多执行该数量的同类动作。

---

## PN 引文系统

资治通鉴 PN 格式：`（NNN-PPP）`
- NNN = 三位零填充卷号（001–294）
- PPP = 三位零填充段落号（001–999）

corpus_search.py 输出为 `（第NNN卷-PPP）`，写入页面时需去掉"第"和"卷"，转换为 `（NNN-PPP）`。

**搜索时自动获得 PN**：
```bash
python3 wiki/scripts/butler/corpus_search.py "关键词" --max 10
# 结果输出：（第002卷-015）→ 页面中写为：（002-015）
```

**行内引文**（优先使用）：
```markdown
商鞅变法推行连坐之法，令行禁止（002-015），秦国大治。
```

**blockquote 引文**（完整引用时）：
```markdown
> 令既具，未布，恐民之不信，已乃立三丈之木于国都市南门，募民有能徙置北门者予十金。
> （002-015）
```

⚠️ **PN 格式铁律**：
- PN 必须紧随被引段落，blockquote 内的 PN 以 `> ` 开头写在最后一行
- 禁止捏造 PN，必须从 corpus_search 结果复制
- 写入页面时将 `第NNN卷-PPP` 转换为 `NNN-PPP`
- **每条事实陈述（描述人物行为/言语/命运/原因）后必须附 PN**；无依据的内容写"（待考证）"，不得裸陈述
- **多条相邻 blockquote 之间必须有空行**：每条 `> （NNN-PPP）` 结尾的行之后，若下一行也是 `> `，中间必须插入一个空行。不得写为：
  ```markdown
  <!-- 错误：多条 blockquote 挤在一起 -->
  > 原文一（010-011）
  > 原文二（010-013）
  ```
  必须写为：
  ```markdown
  <!-- 正确：每条 blockquote 独立 -->
  > 原文一（010-011）

  > 原文二（010-013）
  ```



### Surface Form 铁律（CRITICAL）

**复制原文到 blockquote 时，必须使用完整 surface form**。

**规则**：
- Blockquote 中的文字必须与 corpus/卷节页中的原文**逐字一致**（surface form）
- 允许在句首截断（用省略号或直接从句中开始），但**句中不得漏字**
- 添加 `[[wikilink]]` 时不得改变原文的 surface form

**正误对比**：

```markdown
<!-- ❌ 错误：使用 [[target|...]] 替换原文，导致原文词被截断 -->
> [[商君]]之法，步过六尺者有罚

<!-- ✅ 正确：保留完整 surface form，链接仅标注关键词 -->
> [[商君]]之法，步过六尺者有罚，弃灰于道者被刑
```

**原因**：`[[target|display]]` 语法中 `display` 会替换原文显示。禁止用截断字样代替原文完整词语。

---

## 页面写入铁律

**禁止直接用 Write/Edit 工具写 `wiki/public/pages/` 下的文件。**
所有页面操作必须通过以下脚本：

```bash
# 新建页面
python3 wiki/scripts/add_page.py SLUG - --summary "新增：SLUG" --author INSTANCE_NAME << 'EOF'
[完整页面内容]
EOF

# 编辑页面（传入完整新内容；追加操作必须加 --enrich）
python3 wiki/scripts/edit_page.py SLUG - --summary "更新：SLUG" --author INSTANCE_NAME --enrich << 'EOF'
[完整新内容（必须保留旧版所有 ## 节）]
EOF
```

---

## WU 速查表

| 动作 | WU | batch_n(≈) | 典型 diff |
|------|----|-----------|---------|
| A1 `create-page` 人物/概念 | 100 | 10 | ≤ 60 行 |
| A2 `enrich-page` 丰富内容 | 50 | 20 | ≤ 25 行 |
| A3 `enrich-quality` 质量升档 | 30 | 34 | ≤ 40 行 |
| H4 `enrich-original-quote` 原文引文化 | 30 | 34 | ≤ 30 行 |
| B1 `add-quote` 补名句 | 20 | 50 | ≤ 10 行 |
| B2 `add-pn-citations` 补PN引文 | 15 | 67 | ≤ 8 行 |
| B3 `add-section` 补节原文 | 30 | 34 | ≤ 20 行 |
| C1 `stub` 建存根 | 40 | 25 | ≤ 12 行 |
| C2 `fix-links` 修链接 | 10 | 100 | ≤ 5 行 |
| C3 `add-alias` 加别名 | 5 | 200 | 1 行 |
| D1 `discover` 发现词条 | 50 | 20 | queue.md |
| H2 `enrich-stub` 存根补内容 | 40 | 25 | ≤ 20 行 |
| H3 `add-quote` 补引文 | 20 | 50 | ≤ 10 行 |
| H7 `add-section` 补必要节 | 20 | 50 | ≤ 15 行 |
| H10 `housekeeping-scan` 全库扫描 | 200 | 5 | housekeeping_queue.md |
| H17 `coverage-scan` 全卷覆盖 | 200 | 5 | queue.md |
| H18 `stub-triage` 存根排序 | 30 | 34 | housekeeping_queue.md |
| H20 `wikilink-pass` wiki链接补齐 | 50 | 20 | 扫描新增/修改页，自动添加[[wikilink]] |
| H21 `restructure-sections` 重组整合 | 40 | 25 | 对页面现有章节进行逻辑重组和整合，保留全部内容 |
| E1 `wiki-import` 百科导入 | 50 | 20 | 从 Wikipedia 导入史学特有概念 |

---

## A1 — create-page（100 WU）

**前置**：corpus_search 命中 ≥ 3 条

**slug 规则**：禁止使用单字（单个汉字）作为 id 和文件名。如果词条名是单字，必须加括号后缀消歧义（参见 CLAUDE.md 单字页面消歧义规则）。

**原则**：摘要叙述 + 原文 blockquote + PN，不得只有摘要式 inline PN。

**人物页模板**：
```markdown
---
id: SLUG
type: 人物
cat: 将相
dynasty: 秦国
label: 显示名
aliases: [别名1, 别名2]
tags: [变法, 秦国, 法家]
description: 一句话描述，含卷目出处。
quality: stub
---

# 显示名

简介段落，含 [[朝代]]、[[官职]] 等 wikilink。

## 主要事迹

- **变法推行**：简介。

> 原文段落……
> （NNN-PPP）

## 参见

- [[相关词条]]
```

> **关键规则**：每条核心事实必须有原文 blockquote（`> `）支撑，PN 放在 blockquote 最后一行。禁止仅写 inline PN `（NNN-PPP）` 而无原文引用。

**地点页模板**：
```markdown
---
id: SLUG
type: 地点
label: 显示名
aliases: [别名]
tags: [地点, 战略要地]
description: 一句话描述。
quality: stub
---

# 显示名

简介。[[相关国家]] 的重要地点/活动场所。

## 位置与特色

## 主要事件

## 参见
```

---

## A2 — enrich-page（50 WU）

在现有 stub/basic 页面追加一个新节：

- **禁止替换已有节**：不得删除/重写页面上已有的 `## 节`。只允许在现有节内补充 PN 引文，或在末尾追加新节。
- **允许的操作**：
  - 在已有节末尾追加新段落（含 PN 引文）
  - 在页面末尾追加全新节（`## 新节名`）
  - 在 frontmatter 中补充 tags/aliases（不删除已有值）
- **示例**：
  ```markdown
  <!-- 原有 ## 变法经过 节保留不动，在其后追加新节 -->
  ## 变法经过
  （原有内容，一字不改）

  ## 徙木立信
  商鞅变法之初，于都城市门立木……（002-012至002-014）

  ## 车裂之死
  秦孝公薨后，商鞅遭诬……（006-003至006-005）
  ```
- 已有人物页无「主要事迹」→ 从 corpus_search 补充
- 已有地点页无「主要相关人物」→ 补充
- PN 引文行数 < 3 → 补充 2-3 条

---

## C1 — stub（40 WU）

用最少内容建立存根，解除 broken wikilink。

**原则**：摘要句 + 原文 blockquote + PN。不得写成 `> 摘要文字（NNN-PPP）` 的形式（摘要文字加 PN 不是原文引用）。

```markdown
---
id: SLUG
type: 人物
label: 显示名
description: 一句话描述。
quality: stub
---

# 显示名

一句简介。

> 原文段落……
> （NNN-PPP）

## 参见

- [[相关词条]]
```

**示例**（正确）：

```markdown
秦国大夫，变法推行期间与众臣议政。

> 商鞅曰："治世不一道，便国不法古。"孝公曰："善。"乃以鞅为左庶长，卒定变法之令。
> （002-009）
```

**示例**（错误——不得使用摘要式 blockquote）：

```markdown
> 秦国大夫，参与商鞅变法议政。（002-009）
```

---

## H10 — housekeeping-scan（200 WU）

全库扫描，发现并写入 housekeeping_queue.md：
1. 统计 broken wikilinks（优先写入 H-P1）
2. 检查 quality=stub 但内容超过 500 字的页面（H-P2 enrich-stub）
3. 检查卷链接格式是否统一（`[[第NNN卷]]` 格式）
4. 检查 description 字段为空的页面
5. **检测单字页面**：检查是否存在 id 为单字的页面（id 长度=1），如有则列入清理队列 H-P1

---

## H17 — coverage-scan（200 WU）

扫描 294 卷，检查：
- 前10卷：人物、地点引用是否有对应词条
- 重要卷（第001卷、第002卷、第069卷）的关键词条是否已建立
- 将缺失词条写入 queue.md P2

---

## H20 — wikilink-pass（50 WU）

**用途**：扫描新增或修改页面，自动添加 `[[wikilink]]` 至正文实体名词。

**前置**：无（不依赖 corpus_search，仅依赖 pages.json 注册表）

**用法**：
```bash
# 全量处理所有 entity 页（首轮用）
python3 wiki/scripts/butler/bulk_wikilink.py

# 增量处理自某 commit 以来修改的页面（例行用）
python3 wiki/scripts/butler/bulk_wikilink.py --since HEAD
python3 wiki/scripts/butler/bulk_wikilink.py --since HEAD~5

# 预览不写入
python3 wiki/scripts/butler/bulk_wikilink.py --dry-run
```

**规则**：
- 从 pages.json 注册表构建术语→slug 映射（包含 labels + aliases）
- 最长匹配优先，避免嵌套冲突
- 保护：blockquote（不修改原文）、标题（`#`/`##`）、已有 `[[wikilink]]`
- 跳过 `## 参见` / `## 相关词条` 之后的内容
- 不自链接（同一页的 label 不链接自身）
- 不匹配单字（len<2）
- 写入后自动验证文件一致性，重试一次

**批量**：`batch_n = ceil(1000 / 50) = 20` 页/轮
**增量模式**：`--since HEAD` 通常 0-5 页，WU 按实际修改页数计

---

## H21 — restructure-sections（40 WU）

**用途**：对页面已有章节进行逻辑重组和结构整合，不增删内容（仅重排）。

**适用场景**：
- 页面经过多轮 enrich 后章节排列杂乱、缺乏逻辑线索
- 同类内容分散在多处
- 阅读体验差，需按 **身份 → 叙事 → 功绩 → 关系 → 评价 → 影响 → 杂项** 等逻辑主线重排

**规则**：
- **全部内容必须保留**——这是 append-only 的延伸。重组后的页面不得丢失任何段落、blockquote、PN 引文
- 允许调整 `##` 节顺序、合并内容相近的节、拆分过大的节
- 允许在 `##` 节下增设 `###` 二级子标题，对段落做进一步归类和分层
- 允许调整 frontmatter 字段顺序
- 允许补充缺失的章节标题/引言句以衔接上下文
- 不得删除或替换已有段落
- 不得改变原文 content 的措辞
- 禁止在重组过程中做 enrich（新增内容/引文）。如需 enrich，应作为独立 A2/H4 动作分步执行

**推荐逻辑主线**（适用于人物页）：
```
基本信息 → 生平大事 → 初登场景 → 核心功绩/事迹
  → 性情 → 军事/政治才能 → 主要情节 → 命运/结局
  → 历史评价 → 亲属关系 → 人际关系 → 史学分析
  → 相关史料 → 文化影响 → 参见
```

**前置检查**：
1. 列出页面所有 `## 节` 标题，标注当前顺序
2. 标记哪些节应合并（内容同类但分散）、哪些应前置（如"基本信息"）、哪些应后移（如"参见"）
3. 按逻辑主线排序，确认无节遗漏

**写入方式**：由于涉及全页结构变动，重组可直接 Write 覆盖（这是 append-only 原则的唯一结构例外）。写入后须运行 `build_registry.py` 更新注册表。

---

## E1 — wiki-import（50 WU / batch5）

**用途**：从 Wikipedia 广度优先爬取资治通鉴相关实体，发现并创建词条。Wikipedia 可作内容来源（尤其对史学研究和制度考证类概念），corpus 中存在的实体仍需遵循 PN 引文规范。

**入选标准**（满足任一）：
1. **资治通鉴特有实体**：人物、地点、官职、事件、制度等在原文 corpus 中出现的
2. **史学研究相关**：版本学、注疏、历史评价等虽不在原文但属史学研究的
3. **相关朝代制度**：官制、礼制、军制等历史制度概念

- **禁止导入**：非资治通鉴相关的通用概念

**爬取策略（广度优先）**：
1. 起始页：https://zh.wikipedia.org/wiki/%E8%B3%87%E6%B2%BB%E9%80%9A%E9%91%91
2. 从起始页提取所有内链，筛选资治通鉴相关实体
3. 重点页面：相关人物列表 → 从中提取更多人物 slug
4. 按"起始页→人物列表/分卷→具体实体"的广度优先顺序入队
5. 每次 batch=5，取队首 5 个候选执行

**内容规范**：
- corpus 中有原文的实体 → 用 corpus_search 获取原文 + PN，Wikipedia 内容仅作上下文补充
- 史学研究概念（corpus 0命中）→ 可用 Wikipedia 内容为主要来源，标注 `quality: basic`
- 所有页面必须有 frontmatter + 参见节
- 禁止将非资治通鉴特有的通用人物/概念导入

将页面上总结式 PN（`总结文字（NNN-PPP）`）改造为"总结 + 原文 blockquote + PN"格式。

**新旧对照**：

旧（总结式）：
```markdown
商鞅徙木立信，以十金赏徙木者，民众信服（002-012）。
```

新（原文引文化）：
```markdown
商鞅于都城南门立木，募民能徙置北门者予十金，以取信于民。

> 已乃立三丈之木于国都市南门，募民有能徙置北门者予十金。民怪之，莫敢徙。复曰："能徙者予五十金。"有一人徙之，辄予五十金，以明不欺。
> （002-012）
```

**执行步骤**：
1. 从页面现有 PN 确定目标原文段落
2. 用 `corpus_search.py` 获取原文
3. 保留总结句（可精简），其后追加 `> ` 原文 blockquote
4. PN 移至 blockquote 最后一行（`> （NNN-PPP）`）
5. 通过 `edit_page.py --enrich` 写入（已有 `##` 节不得删除）

**适用范围**：仅改造 inline PN（`文字（NNN-PPP）`）→ blockquote + PN 格式。已包含完整原文引用的页面跳过。
