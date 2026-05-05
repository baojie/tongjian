# 资治通鉴 Wiki

北宋司马光《资治通鉴》中文百科，AI 辅助整理，纯静态 SPA。

**在线访问**：[baojie.github.io/tongjian](https://baojie.github.io/tongjian)

## 内容

- **294 卷**原文页（战国 403 BC — 五代 959 AD，纵贯 1362 年）
- **70+ 词条**：历史人物、重大战役、关键事件
- 11 个精选词条（司马光、唐太宗、曹操、秦始皇、韩信、项羽等）

## 功能

- 全文检索（原文 + 词条）
- PN 段落引注（`（001-013）` 直链原文段落）
- 反向引用、参见链接
- 地名/行军路线地图（Leaflet）
- 语义查询（`:::query` 块）

## 本地运行

```bash
bash wiki/wiki.sh
# 访问 http://localhost:1084
```

## 目录结构

```
tongjian/
├── corpus/raw/          # 资治通鉴原文（只读）
├── wiki/public/
│   ├── pages/           # 词条页面（Markdown）
│   ├── js/              # SPA 前端
│   └── plugins/         # 功能插件
├── wiki/scripts/        # 构建脚本
└── docs/                # GitHub Pages 输出
```

## 贡献

欢迎[提交 Issue](https://github.com/baojie/tongjian/issues/new) 指出错误或补充内容。

内容基于 [CC BY-SA 4.0](https://creativecommons.org/licenses/by-sa/4.0/deed.zh) 授权，《资治通鉴》原著为公版作品。
