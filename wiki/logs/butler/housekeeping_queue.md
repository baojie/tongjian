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

## H18 stub-triage (R2683, %37=19)
> 以下词条 body < 500B（R2683 重扫更新），建议优先 enrich
- stub person | 赵韪 | 320B
- stub concept | 簟 | 322B
- stub person | 王奂 | 329B
- stub person | 刘汉 | 346B
- stub person | 李育 | 357B
- stub person | 李农 | 367B（R2683 enrich）
- stub place | 柏谷 | 362B
- stub concept | 简_(概念) | 368B
- stub place | 湖 | 369B
- stub place | 胶西王 | 372B
- stub place | 南康 | 386B（R2683 enrich）
- stub concept | 杖刑 | 386B
- stub place | 萧县 | 387B（R2683 enrich）
- stub concept | 驿道 | 387B
- stub place | 襄武 | 388B（R2683 enrich）
- stub place | 小黄 | 391B
- stub place | 浮阳 | 393B（R2683 enrich）
- stub concept | 荒田 | 393B（R2683 enrich）
- stub place | 育阳 | 397B
- stub place | 封丘 | 398B

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
