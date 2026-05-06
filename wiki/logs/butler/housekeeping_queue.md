# 资治通鉴 Wiki Butler 内务队列

## H-P1 — 紧急内务
<!-- 空 -->

## H-P2 — 常规内务
<!-- 空，初始状态 -->

## H10 housekeeping-scan (R2519, %11=0)
> 全库健康扫描结果
- NOTE: 5页缺description字段 → 备御、劲兵、名籍、社稷、饷道（均为concept类型）
- NOTE: 无broken wikilinks
- NOTE: 无单字页面问题
- TODO: 补充5页description字段（H4 enrich-meta）

## H-P3 — 探索内务
  [ ] H-P3 housekeeping-scan | 全局 | 初始覆盖率扫描

## H18 stub-triage (R2917, after %37=19)
> 以下词条 body < 500B（R2917 重扫更新），建议优先 enrich
- stub concept | 项_(概念) | 185B
- stub concept | 敦_(概念) | 191B
- stub concept | 埙_(概念) | 311B
- stub concept | 刘汉 | 346B
- stub concept | 篙_(概念) | 360B
- stub concept | 萝_(概念) | 369B
- stub concept | 蝶_(概念) | 377B
- stub place | 小黄 | 391B
- stub concept | 萍_(概念) | 393B
- stub place | 育阳 | 397B
- stub concept | 篪_(概念) | 409B

## H17 coverage-scan (R2220, %37=0)
> 页面元数据覆盖扫描结果
- GAP: 2506/2506 person 页面缺少 cat 字段（100%）
- GAP: 180/180 event/battle 页面缺少 event_type 字段（100%）
- GAP: 7074/7074 页面缺少 dynasty 字段（100%）
- RECOMMEND: 优先补全 person.cat 字段，可批量脚本修复

## H17 re-scan (R2257, %37=0)
- person.cat: 0/2511 (0%) — unchanged
- event.event_type: 0/184 (0%) — unchanged  
- stubs (<100B): 28 条 — 较 R2220 新增 8 条
