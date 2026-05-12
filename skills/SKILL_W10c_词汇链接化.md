---
name: SKILL_W10c_词汇链接化
title: Wiki 内务整理 H2：词汇链接化
description: 扫描页面正文中未加 [[]] 的人名/地名/概念词，为首次出现的词补充 wikilink，每轮最多补 5 个链接。
---

# SKILL W10c: 词汇链接化（H2）

> "链接是知识图谱的血脉。每补一条链接，就多一条知识流动的通道。"

---

## 一、何时执行

| 触发场景 | 优先级 |
|---|---|
| 主页面提及重要人物/地名但无 `[[]]` | P0 |
| 高频人名在多页均无链接 | P1 |
| 普通页面有未链接的概念词 | P2 |

---

## 二、发现候选

### 批量扫描（推荐）

使用 `bulk_wikilink.py` 全量/增量扫描：

```bash
# 增量扫描：自上次提交以来的新页面
python3 wiki/scripts/butler/bulk_wikilink.py --since HEAD

# 干跑预览（不实际写入）
python3 wiki/scripts/butler/bulk_wikilink.py --dry-run --limit 10
```

### 手动筛查

对批量结果中未覆盖的页面，可手动寻找未链词汇：

```bash
# 找正文中出现了 pages.json 中已注册实体但没加 [[]] 的地方
python3 -c "
import json, re
pages = json.load(open('wiki/public/pages.json'))['pages']
# 取所有已知标签
all_labels = set()
for slug, p in pages.items():
    all_labels.add(p.get('label', slug))
    for a in p.get('aliases', []):
        all_labels.add(a)
# 对一个具体页面检查缺失链接
"
```

---

## 三、执行步骤

### Step 1：批量运行增量 wikilink

```bash
python3 wiki/scripts/butler/bulk_wikilink.py --since HEAD
```

### Step 2：人工抽查（butler 每轮抽查 1-2 页）

```bash
# 检查某页的真假阳性
grep -c '\[\[.*\]\]' wiki/public/pages/目标页.md
# 确认没有误链（如单字匹配、朝代/数字等不应链接的）
```

### Step 3：处理消歧义情形

| 情形 | 处理 |
|---|---|
| 词与页面名完全一致 | `[[词]]` |
| 页面名是 `词（限定词）` | `[[词（限定词）\|词]]` |
| 有消歧义页 | `[[词（限定词）\|词]]` 指向具体义项 |

---

## 四、成功标准

- [ ] 每个新增链接的目标页均存在（无红链）
- [ ] 只链首次出现，未重复链接同一词
- [ ] 原文字符未被修改（只添加了 `[[]]`）
- [ ] diff 行数合理（bulk_wikilink.py 自控）

---

## 五、工具

| 工具 | 用途 |
|---|---|
| `wiki/scripts/butler/bulk_wikilink.py --since HEAD` | 增量 wikilink 补充（含 revision 记录） |
| `wiki/scripts/butler/bulk_wikilink.py --dry-run` | 预览本次将要修改的链接 |

---

## 相关路径

- `wiki/logs/butler/housekeeping_queue.md` — H2 任务队列
- [W10f 断链新建条目](SKILL_W10f_断链新建条目.md) — 目标页不存在时转 H5
