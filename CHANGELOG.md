# Changelog

## 2026-05-06 — 首次发布

### 前端

- **Hero 重设计**：山水画风格 SVG（弦月、三层山脉、水墨古松）；钤印改为「資治通鑒·司馬光著」，hover 显示宋神宗赐名序
- **首页 home-body**：新增「精选词条」区块（11 个 featured 词条卡片）；卷目导航条（第1卷～第294卷）；修复竞态——`renderHome` 等待完整注册表加载后再渲染精选卡片
- **插件系统**：修复 `plugins.json` 字段名错误（`src` → `entry`）；注册全部 10 个插件

### 插件

| 插件 | 状态 |
|------|------|
| pn-citation | 段落引注链接（`（NNN-PPP）`） |
| footnote | `[^id]` 脚注 |
| semantic-block | `:::infobox / :::meta` 语义块 |
| semantic-query | `:::query` 语义查询 |
| backlinks | 反向引用 |
| sealso | 参见链接 |
| place-map | 地名/王朝 sidebar 地图（引自史记 wiki） |
| route-map | 行军路线地图（引自史记 wiki） |
| geomap | 郡国/战场分布地图（引自史记 wiki） |
| math | KaTeX 公式 |

### 内容

- 294 卷原文页导入完成
- 70+ 词条初稿（人物、战役、事件）
- 11 个精选词条：司马光、唐太宗、曹操、秦始皇、汉武帝、汉高祖刘邦、诸葛亮、韩信、项羽、赤壁之战、长平之战
