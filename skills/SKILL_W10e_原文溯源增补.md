---
name: SKILL_W10e_原文溯源增补
title: Wiki 内务整理 H4：原文溯源增补
description: 为有内容但缺乏原文溯源字段（pn/tags 等）的页面补充 PN 引注，确保每个断言都有原文出处。
---

# SKILL W10e: 原文溯源增补（H4）

> "无源之水不长久。每个关于《资治通鉴》的断言，都应该能追溯到具体的段落。"

---

## 一、何时执行

| 触发场景 | 优先级 |
|---|---|
| 人物页有 ≥3 行描述内容，但正文无 PN 引注 | P1 |
| 概念页有内容但无任何溯源字段 | P2 |
| W6/W7 质检标记为 unsourced | P1 |

**不处理的情形**：
- 页面只有 stub 一行描述（等 H18 Stub扩展后再溯源）
- 页面已有充足 PN 引注（≥5 处）

---

## 二、发现候选

```bash
# 手动扫描：找有内容但无 PN 引注的人物页
grep -L "(0[0-9][0-9]-" wiki/public/pages/*/*.md | \
    xargs grep -l "^type: 人物" | head -20

# 找无 PN 引注的页面（任意类型）
grep -L "(0[0-9][0-9]-" wiki/public/pages/*/*.md | \
    xargs grep -l "^quality: basic\|^quality: standard" | head -20
```

---

## 三、执行步骤

### Step 1：读页面内容，列出断言句

```bash
# 读取页面内容（resolve_page_file 自动定位分桶路径）
python3 -c "from wiki.scripts.page_bucket import resolve_page_file; from pathlib import Path; print(resolve_page_file(Path('wiki/public/pages'), '人物名').read_text(encoding='utf-8'))"
```

找出正文中的事实性断言句，如：
- "XX 是 XX 的丞相"
- "XX 于第 N 卷出场"
- "XX 与 XX 有君臣关系"

### Step 2：用 corpus_search 查找原文段落

```bash
python3 wiki/scripts/butler/corpus_search.py "断言关键词" --max 10
```

**匹配标准**：
- 搜索结果中 PN 段落直接包含断言中的关键词 → 可信
- 搜索结果无命中 → 记入 `failures.jsonl`，不强行附注

### Step 3：确认匹配正确性

对照卷节页，确认：
1. 该段落确实记载了页面中的断言
2. PN 编号格式正确（如 `(003-024)` 表示第3卷第24段）

### Step 4：补充行内 PN 引注

在断言句末尾追加行内引注：

```markdown
商鞅入秦，以强国之术说秦孝公，孝公大悦，遂以商鞅为左庶长（002-009）。
```

### Step 5：写入并记录

```bash
# 编辑页面（遵守 Append-Only 原则，只加不删）
cat << 'EOF' | python3 wiki/scripts/edit_page.py 人物名 - \
    --summary "w10e: 补充PN溯源引注" --author "butler"
[完整新内容（含已有节+新增引注）]
EOF
```

---

## 四、成功标准

- [ ] 补充的 PN 经核实指向正确段落
- [ ] PN 格式符合 `（NNN-PPP）` 规范
- [ ] 每轮处理 ≤ 5 个页面
- [ ] 无法确认的断言记入 `wiki/logs/butler/failures.jsonl`（不强行附注）

---

## 五、工具

| 工具 | 用途 |
|---|---|
| `wiki/scripts/butler/corpus_search.py` | 根据关键词搜索对应 PN |
| `wiki/scripts/edit_page.py` | 写入修改（自动记录 revision） |
| `wiki/logs/butler/failures.jsonl` | 记录无法匹配的断言 |

---

## 相关路径

- `wiki/logs/butler/housekeeping_queue.md` — H4 任务队列
- [W10l 引文PN一致性](SKILL_W10l_引文PN一致性.md) — 已有 PN 但内容不符时走此流程
