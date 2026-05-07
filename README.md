# 资治通鉴 Wiki

北宋司马光《资治通鉴》中文百科，AI 辅助整理，纯静态 SPA。

**在线访问**：[tongjian.memify.wiki](https://tongjian.memify.wiki/)

## 内容

- **294 卷**原文页（战国 403 BC — 五代 959 AD，纵贯 1362 年）
- **13600+ 页面**，涵盖 46 种页面类型：

| 类型 | 数量 | 类型 | 数量 | 类型 | 数量 |
|------|------|------|------|------|------|
| 人物 | 3600+ | 年份 | 1360+ | 军事 | 970+ |
| 地点 | 690+ | 政治 | 650+ | 官职 | 600+ |
| 礼制 | 470+ | 社会 | 450+ | 概念 | 430+ |
| 经济 | 420+ | 器物 | 380+ | 章节 | 294 |
| 自然 | 330+ | 成语 | 270+ | 哲学 | 250+ |
| 事件 | 140+ | 战役 | 80+ | 名句 | 47 |
| 综述 | 77 | 国家 | 59 | 王朝 | 15 |

## 功能

- 全文检索（原文 + 词条）
- PN 段落引注（`（001-013）` 直链原文段落）
- 反向引用、参见链接
- 地名/行军路线地图（Leaflet）
- 语义查询（`:::query` 块）

## 本地运行

```bash
bash wiki/wiki.sh
# 访问 http://localhost:1084（元丰七年，通鉴完成年份）
```

## 目录结构

```
tongjian/
├── corpus/raw/          # 资治通鉴原文（只读，~300万字）
├── wiki/public/ → docs/wiki/  # 站点目录（symlink）
│   ├── pages/           # 词条页面（Markdown + YAML frontmatter）
│   ├── js/              # SPA 前端
│   └── plugins/         # 功能插件
├── wiki/scripts/        # 构建脚本
│   └── butler/          # 永续管家（自动新建/丰富/维护）
└── docs/                # GitHub Pages 输出
```

## 页面类型

Frontmatter 的 `type` 字段使用中文值：`人物`、`地点`、`事件`、`战役`、`官职`、`国家`、`王朝`、`概念`、`名句`、`章节` 等。

类型详见 `CLAUDE.md`。

## 贡献

欢迎[提交 Issue](https://github.com/baojie/tongjian/issues/new) 指出错误或补充内容。

内容基于 [CC BY-SA 4.0](https://creativecommons.org/licenses/by-sa/4.0/deed.zh) 授权，《资治通鉴》原著为公版作品。
