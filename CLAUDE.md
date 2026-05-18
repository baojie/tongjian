# 资治通鉴 Wiki — Claude 工作规则

> 📖 跨项目共享铁则参见：`/home/baojie/work/knowledge/shared-rules.md`
> 所有知识库 wiki 通用的规则（Append-Only、原文只读等）定义在共享文件中，本文件仅包含资治通鉴特有规则。

## 项目简介

本项目是北宋司马光《资治通鉴》（294卷）的中文百科 Wiki，使用纯静态 SPA 前端。

```
tongjian/
├── corpus/
│   └── raw/
│       └── 资治通鉴.txt   # 原文（只读，不可修改）
├── wiki/
│   ├── public/ → ../docs/wiki/   # 符号链接
│   │   ├── index.html
│   │   ├── pages/                # Wiki 页面（294卷原文页 + 词条页）
│   │   │   ├── li/               # 拼音分片子目录（首字拼音前2字母）
│   │   │   ├── zh/               # 109 个子目录
│   │   │   └── ...
│   │   ├── history/              # 修订历史 JSONL（与 pages 同规则分片）
│   │   │   ├── li/               # 同上 109 个子目录
│   │   │   ├── si/
│   │   │   └── ...
│   │   ├── pages.json            # 页面注册表（含 path 字段）
│   │   └── pages.lite.json
│   ├── scripts/           # 构建脚本
│   │   ├── page_bucket.py # 拼音分片算法（共享模块）
│   │   └── butler/        # Butler 工具脚本
│   ├── server/            # 本地服务器
│   ├── logs/
│   │   └── butler/        # Butler 状态：queue.md / actions.jsonl
│   └── wiki-daemon.sh     # 守护进程管理
├── docs/                  # GitHub Pages 输出（wiki/public → docs/wiki）
└── .claude/
    └── skills/
        └── butler/
            └── SKILL.md   # /butler skill 定义
```

## 页面分片：拼音前缀桶

`wiki/public/pages/` 下的 **19,258 个 .md 文件** 按页面名的拼音前缀分散到 **109 个子目录**。

### 分片算法（`wiki/scripts/page_bucket.py`）

| 页面名首字符 | 桶名规则 | 示例 |
|-------------|----------|------|
| CJK 汉字 | 取第一字拼音的前 2 字母 | `刘备` → `li/刘备.md` |
| ASCII 字母/数字 | 取前 2 个字母数字（小写） | `About` → `ab/About.md` |
| 前导标点 | 剥离后按剩余首字算 | `《资治通鉴》` → `zi/《资治通鉴》.md` |
| 单字名 | 拼音不足 2 字母时 + "0" | `阿` → `a0/阿.md` |

### 辅助函数

- `page_bucket(slug)` — 返回桶名（如 `"li"`）
- `page_path(slug)` — 返回 pages/ 下的相对路径（如 `"li/刘备.md"`）
- `resolve_page_file(pages_root, slug)` — 返回 Path 或 None

### 分布数据（2026-05-14）

| 桶 | 文件数 | 示例 |
|----|--------|------|
| `zh/` | 1520 | 中国, 诸侯, 诸葛亮, 中, 之 |
| `li/` | 1165 | 刘备, 李广, 李斯, 礼, 立 |
| `go/` | 1121 | 公, 功, 宫, 共, 供养 |
| `qi/` | 1014 | 七国之乱, 齐, 前, 秦, 器 |
| `ji/` | 989 | 九卿, 军, 家, 将, 计 |
| 其余 104 桶 | 1~862 | — |
| **合计** | **19,258** | **109 桶, 平均 177/桶** |

### 注册表中的 path 字段

`pages.json` / `pages.lite.json` 的每条 entry 带有 `path` 字段：

```json
{
  "刘备": {
    "type": "人物",
    "label": "刘备",
    "path": "li/刘备.md"
  }
}
```

SPA 通过 `meta.path` 取页面内容，而非硬拼接。无 `path` 字段时 fallback 到 `{pid}.md`（向前兼容）。

## History 文件分片

`wiki/public/history/` 下的 **20,629 个 .jsonl 文件** 也与 pages 同样规则分片到 109 个子目录。

### 分片规则

与 `page_bucket(slug)` 相同——以页面名的拼音前缀确定桶名。

```
history/刘备.jsonl    →  history/li/刘备.jsonl
history/曹操.jsonl    →  history/ca/曹操.jsonl
history/司徒.1.jsonl  →  history/si/司徒.1.jsonl
```

### 前端读取规则

前端通过 registry 中的 `path` 字段提取桶名：

```javascript
const bucket = meta.path ? meta.path.split('/')[0] : '';
const prefix = bucket ? bucket + '/' : '';
const r = await fetch(`history/${prefix}${page}.jsonl`);
```

### 写入规则（后端）

所有后端脚本写入 history 时使用 `page_bucket(page)` 计算桶：

```python
from page_bucket import page_bucket
bucket = page_bucket(page)
hist_dir = HIST / bucket
hist_dir.mkdir(parents=True, exist_ok=True)
page_jsonl = hist_dir / f"{page}.jsonl"
```
```

## 绝对禁止事项（CRITICAL）

- ❌ **禁止自动 `git commit`** — 需用户明确要求，或使用 `/wiki` skill
- ❌ **禁止 `git add -A` / `git add .` / `git add --all`** — 只允许显式路径
- ❌ **禁止 `git push --force`**
- ❌ **禁止 `git reset --hard` / `git checkout --` / `git restore`**
- ❌ **禁止自动修改 `corpus/` 下的原文** — 自动化脚本和 Claude 自主操作禁止；用户明确指令下可修改
- ❌ **禁止修改 `wiki/public/pages/第???卷.md`** — 卷原文页由导入脚本生成，只读

**唯一例外**：使用已授权的 skill（`/wiki`、`/rfc` 等）时，自动 commit + push 已被授权。

## 内容保护原则（CRITICAL）

详见宪法 §1.1。**禁止整节替换，enrich/重组操作必须保留旧版所有 `##` 节标题，节内内容可提升，节不得消失。**

## Wiki 页面规范

### Frontmatter 字段

```yaml
---
id: 词条名
type: person        # 见下方页面类型表
dynasty: 西汉       # 【person/event推荐】所属朝代或时代
event_type: 战争    # 【event必填】见下方事件分类表
label: 显示名
aliases: [别名1, 别名2]
tags: [帝王, 标签]  # 人物分类用 tag 表示（见下方分类参考）；朝代/诸侯国/身份等补充标签
description: 一句话描述
featured: true      # 可选，首页精选
---
```

### 页面类型（type 字段）

| type | 含义 |
|------|------|
| 人物 | 历史人物 |
| 国家 | 王朝/诸侯国 |
| 事件 | 重大事件（非战役） |
| 战役 | 战役（优先于事件） |
| 地点 | 地点/地名 |
| 概念 | 概念/制度（礼制、官职、思想等） |
| 章节 | 原文卷目（第NNN卷.md，由导入脚本生成） |
| 综述 | 综述/列表 |
| 名句 | 名句/臣光曰 |

### 人物分类 tag（type=person 时在 tags 中填写）

| tag | 含义 | 代表人物 |
|-----|------|---------|
| `帝王` | 皇帝/天子/诸侯国君主 | 秦始皇、汉武帝、唐太宗 |
| `宗室` | 皇族宗室、诸侯子弟 | 信陵君、平原君 |
| `将相` | 将领兼丞相，文武双全 | 曹操、诸葛亮、萧何 |
| `将领` | 主要以军事著称 | 韩信、白起、卫青、霍去病 |
| `谋臣` | 谋士/策士/外交家 | 苏秦、张仪、范雎 |
| `谏臣` | 以直言谏诤著称 | 魏征、司马光 |
| `权臣` | 专权误国的大臣 | 王莽、赵高、司马懿 |
| `忠臣` | 以忠义节操著称 | 豫让、蔺相如、张良 |
| `外戚宦官` | 后宫外戚或宦官 | 赵高（宦官）、王莽（外戚） |
| `学者文士` | 思想家/文学家/史家 | 司马光 |
| `刺客游侠` | 刺客/游侠 | 荆轲、豫让 |
| `将领外交` | 兼具军事与外交 | 班超 |

> **多重身份**：在 tags 中并列填写，如 `tags: [刺客游侠, 忠臣]`。

### 事件分类（event_type 字段，type=event/battle 时必填）

| event_type | 含义 |
|-----------|------|
| `战争` | 大规模战争（非单次会战） |
| `战役` | 单次决定性会战（用于 battle type） |
| `政变` | 宫廷政变/权力更迭 |
| `改革` | 制度/法律变革 |
| `外交` | 会盟/朝贡/结盟 |
| `叛乱` | 起义/叛变 |
| `继位` | 帝位传承/禅让 |
| `礼制` | 礼仪/文化事件 |
| `灾害` | 自然灾害/瘟疫 |

### 朝代标签（dynasty 字段推荐值）

`周` / `春秋` / `战国` / `秦` / `西汉` / `新朝` / `东汉` / `三国` / `西晋` / `东晋` / `南北朝` / `十六国` / `隋` / `唐` / `五代十国` / `北宋`

诸侯国可用具体名称：`秦国` `赵国` `魏国` `楚国` `燕国` 等。

### PN 引注格式（必须遵守）

格式：卷-段落，`（NNN-PPP）`，NNN 为三位数卷号，PPP 为三位数段落号。

示例：`（001-003）` 表示第1卷第3段落。

**两种用法：**

1. **行内引注**：
   ```
   智伯被三家所灭（001-012）。
   ```

2. **引用块末尾**：
   ```markdown
   > 才胜德谓之小人。
   > （001-013）
   ```

**禁止**：伪造 PN，所有 PN 必须从 `corpus_search.py` 搜索结果中获取。

### Wikilink 格式

使用 `[[词条名]]` 或 `[[词条名|显示文字]]`。

### 卷页面只读

`wiki/public/pages/第???卷.md` 由 `wiki/scripts/import_volumes.py` 生成，不得手动编辑。
如需修改格式，修改导入脚本后重新生成（`--force`）。

## 工作流程

### 新建词条页面

```bash
python3 wiki/scripts/add_page.py "词条名" --type person
```

### 构建 pages.json

```bash
python3 wiki/scripts/build_registry.py wiki/public/pages --out wiki/public/pages.json --out-lite wiki/public/pages.lite.json
```

### 本地预览

```bash
bash wiki/wiki.sh
# 访问 http://localhost:1084
```

端口 1084 为《资治通鉴》完成年份（元丰七年）。

### 发布

```bash
bash wiki/scripts/publish.sh
git add wiki/public docs
git commit -m "wiki: 更新词条"
git push
```

## Corpus Search

```bash
python3 wiki/scripts/butler/corpus_search.py "关键词" --max 10
python3 wiki/scripts/butler/corpus_search.py "关键词" --vol 1 --vol 2 --max 5
```

## Butler 管家

详见 `.claude/skills/butler/SKILL.md`。

启动方式：`/butler`

## Commit 消息规范

```
wiki: 新增词条「商鞅」「秦始皇」

Wiki:
- 新增 商鞅（秦国变法者）
- 新增 秦始皇（中国第一位皇帝）
```
