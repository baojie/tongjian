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

## H18 stub-triage (R2128, %37=19)
> 以下词条 body < 100B 且无 PN 引注，建议优先 enrich
- stub concept | 窑 | 42B
- stub concept | 项 | 55B
- stub concept | 敦 | 55B
- stub concept | 瓢 | 84B
- stub concept | 饴 | 92B
- stub concept | 五运 | 92B
- stub concept | 驿 | 93B
- stub concept | 迁居 | 96B
- stub concept | 辂 | 96B
- stub concept | 锐兵 | 96B
- stub concept | 砚 | 96B
- stub concept | 轺 | 97B
- stub concept | 船舰 | 97B
- stub concept | 贾让 | 97B
- stub concept | 羽檄 | 97B
- stub concept | 麾下 | 97B
- stub concept | 船运 | 98B
- stub concept | 膳 | 99B
- stub concept | 肴 | 99B
- stub concept | 地道 | 99B

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
