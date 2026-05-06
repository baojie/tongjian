# 资治通鉴 Wiki — Onboarding

北宋司马光《资治通鉴》（294卷，BC403–AD959）中文百科，AI 辅助整理，纯静态 SPA，部署于 GitHub Pages。

## 快速上手

```bash
# 本地预览（端口 1084 = 元丰七年，通鉴完成年份）
bash wiki/wiki.sh
# 访问 http://localhost:1084

# 启动 Butler 管家（永续词条建设）
/butler --focus create --instance 司马光
```

## 目录结构

```
tongjian/
├── corpus/raw/资治通鉴.txt   # 原文（只读，~300万字，294卷）
├── wiki/
│   ├── public/
│   │   ├── pages/           # 词条页（Markdown，~2100+页）
│   │   ├── pages.json       # 注册表（build_registry.py 生成）
│   │   ├── js/renderer.js   # SPA 核心渲染器
│   │   └── css/main.css     # 样式
│   ├── scripts/
│   │   ├── add_page.py      # 新建词条（必须用此脚本）
│   │   ├── edit_page.py     # 编辑词条（保护 frontmatter）
│   │   ├── build_registry.py
│   │   ├── compute_quality.py
│   │   ├── wiki_commit.sh   # git commit + push 封装
│   │   └── butler/          # Butler 工具脚本
│   └── logs/butler/         # Butler 状态（queue/actions/round_counter）
└── docs/                    # GitHub Pages 输出（wiki/public 符号链接）
```

## 绝对禁忌

- ❌ 不得直接 Write/Edit `wiki/public/pages/*.md`，必须用 `add_page.py` / `edit_page.py`
- ❌ 不得修改 `corpus/raw/资治通鉴.txt`（原文只读）
- ❌ 不得修改 `wiki/public/pages/第???卷.md`（章节页由导入脚本生成）
- ❌ 不得 `git add -A` / `git add .`，只允许显式路径
- ❌ 编辑已有页面时只追加，不删除已有内容

## 词条页面规范

### Frontmatter 必填字段

```yaml
---
id: 曹操
type: person          # person / event / battle / place / concept / state / overview
cat: 将相             # type=person 必填，见分类表
dynasty: 东汉         # 推荐填写
label: 曹操
tags: [三国, 魏武帝]
description: 一句话描述
---
```

### PN 引注格式

```
（NNN-PPP）   # NNN=三位卷号，PPP=三位段落号
```

示例：`（068-007）` = 第68卷第7段落。**所有 PN 必须从 corpus_search.py 结果中复制，禁止伪造。**

## 常用命令

```bash
# 搜索原文
python3 wiki/scripts/butler/corpus_search.py "贾诩" --max 10

# 新建词条
python3 wiki/scripts/add_page.py "词条名" --type person

# 重建注册表
python3 wiki/scripts/build_registry.py wiki/public/pages --out wiki/public/pages.json

# 发布
/wiki
```

## Butler 管家体系

五位实例，各司其职：

| 实例 | 命令 | 职责 |
|------|------|------|
| 司马光 | `/butler --focus create --instance 司马光` | 新建词条 |
| 刘攽 | `/butler --focus enrich --instance 刘攽` | 深化内容 |
| 刘恕 | `/butler --focus discover --instance 刘恕` | 发现新词条 |
| 范祖禹 | `/butler --focus housekeeping --instance 范祖禹` | 日常维护 |
| 胡三省 | `/butler --focus publish --instance 胡三省` | 定期发布 |

## 当前状态（2026-05）

- 总词条：~2100 页（含 294 卷原文页）
- 非章节词条：~1830 条
- 质量分布：精品 604 / 标准 140 / 基础 916 / 存根 167
- W5 反思发现：concept/event/battle/place 四类 100% basic，为下阶段重点攻坚
- 年份总览页：~220 条，覆盖率 10–20%/百年

## Git 工作流

```bash
# 通过 /wiki skill（自动 build + stage + commit + push）
/wiki

# 或手动
git add docs/wiki/pages/<文件> docs/wiki/history/<文件>
git add docs/wiki/pages.json docs/wiki/pages.lite.json
bash wiki/scripts/wiki_commit.sh "wiki: 新增词条「X」「Y」"
```

staging 路径用 `docs/wiki/`（符号链接实体），不是 `wiki/public/`。
