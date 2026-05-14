---
name: SKILL_W10f_断链新建条目
title: Wiki 内务整理 H5：断链新建条目
description: 统计 wiki 中被多个页面引用但目标页不存在的断链（红链），优先为高频断链建立最小可用 stub 页面。
---

# SKILL W10f: 断链新建条目（H5）

> "红链是未来的蓝链。高频红链说明知识库缺少一块重要拼图。"

---

## 一、何时执行

| 触发场景 | 优先级 |
|---|---|
| 同一链接目标在 ≥3 个页面中出现，但目标页不存在 | P1 |
| H2（词汇链接化）发现词汇无对应页 | P1 |
| 1-2 个页面的引用红链 | P2 |

---

## 二、发现候选

使用 `discover_wanted.py` 扫描高频断链：

```bash
# 查看待创建候选（按引用频率排序）
python3 wiki/scripts/butler/discover_wanted.py --top 30

# JSON 格式输出（供解析）
python3 wiki/scripts/butler/discover_wanted.py --json --top 30
```

**手动扫描备选**：

```bash
# 找所有 [[词]] 格式但无对应文件的链接（递归扫描分桶目录）
grep -roh '\[\[[^\]|]*\]\]' wiki/public/pages/*/*.md | \
    sed 's/.*\[\[\(.*\)\]\]/\1/' | sort | uniq -c | sort -rn | \
    while read cnt name; do
        # 用 resolve_page_file 检查页面是否存在（自动处理分桶）
        python3 -c "from wiki.scripts.page_bucket import resolve_page_file; from pathlib import Path; print('found' if resolve_page_file(Path('wiki/public/pages'), '$name') else '')" | grep -q found || echo "$cnt $name"
    done | head -20
```

---

## 三、执行步骤

### Step 1：选候选

从 `discover_wanted.py` 输出中取 **引用频次 ≥ 3** 且 **页面不存在的** 前 3 名。

### Step 2：判断类型

| 链接格式特征 | 推断类型 |
|---|---|
| 历史人名 | 人物 |
| 以"之战"结尾 | 战役 |
| 地名/建筑名 | 地点 |
| 官职/制度词 | 概念 |
| 卷目名（第NNN卷）| 章节 |

### Step 3：建立 stub 页面

**最小 stub 模板**：

```markdown
---
id: 页面名
type: 人物  # 或 地点/概念/战役
label: 页面名
quality: stub
tags: []
description: 一句话描述
---

# 页面名

（待补充）

## 原文引文

（待补充原文引文）
```

```bash
echo '...' > /tmp/stub.md
python3 wiki/scripts/add_page.py "页面名" /tmp/stub.md \
    --summary "w10f: 新建stub（高频断链，N处引用）" \
    --author "butler"
```

### Step 4：确认

```bash
# 确认页面已创建（resolve_page_file 自动定位分桶路径）
python3 -c "from wiki.scripts.page_bucket import resolve_page_file; from pathlib import Path; p=resolve_page_file(Path('wiki/public/pages'), '页面名'); print(p or 'NOT FOUND')"
```

### Step 5：更新队列

在 `housekeeping_queue.md` 中将该条目标记为 `done`。

---

## 四、成功标准

- [ ] 每轮最多建 3 个 stub
- [ ] stub 必须包含：id, type, label, quality: stub, description
- [ ] 建立后原有红链变为有效蓝链

---

## 五、工具

| 工具 | 用途 |
|---|---|
| `wiki/scripts/butler/discover_wanted.py` | 扫描高频断链 |
| `wiki/scripts/add_page.py` | 建立新页面（自动记录 revision） |

---

## 相关路径

- `wiki/logs/butler/housekeeping_queue.md` — H5 任务队列
- [W10c 词汇链接化](SKILL_W10c_词汇链接化.md) — H2，发现词汇无页面时触发 H5
