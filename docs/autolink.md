# 自动链接（autoWikilink）功能说明

## 功能描述

自动链接会扫描正文，把已知词条名（包括别名）自动转为可点击的 wikilink。

例如正文中裸写"商鞅"，会自动变为 `[[商鞅]]` 并渲染为链接。

## 默认状态

**默认关闭。**

## 开关方式

### 方式一：顶栏按钮（推荐）

页面右上角 topnav 有"自动链接：关/开"按钮，点击即切换，状态保存到 `localStorage`，刷新后保持。

### 方式二：URL 参数（临时，不保存）

在 URL 后加 `?autolink=1`，仅当次访问生效。

### 方式三：浏览器控制台

```js
window.__wiki.setSetting('autoWikilink', true)   // 开启
window.__wiki.setSetting('autoWikilink', false)  // 关闭
```

执行后刷新页面生效。

## 实现位置

| 文件 | 作用 |
|------|------|
| `docs/wiki/js/core.js` | `core.settings` / `core.setSetting()`，读写 `localStorage` key `wiki_settings` |
| `docs/wiki/js/parser.js` | 读 `core.settings.autoWikilink`，决定是否调用 `autoWikilink()` |
| `docs/wiki/js/autolink.js` | 实际的 Trie 前缀树扫描逻辑 |
| `docs/wiki/index.html` | topnav 按钮 `#autolink-toggle` 及初始化脚本 |
| `docs/wiki/css/main.css` | `.topnav-btn` / `.topnav-btn.active` 样式 |

## 保护区域（永不被自动链接）

- 代码块 ` ``` ` 与行内代码
- 标题行 `#`
- 已有 `[[wikilink]]`
- Markdown 链接与图片
- PN 引注 `（NNN-PPP）` 与段落锚点 `[NNN-PPP]`
