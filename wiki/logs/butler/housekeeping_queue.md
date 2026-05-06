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

## H18 stub-triage (R3268, %37=19)
> 全库 body < 500B 共 7431 条（重扫更新），person 类型优先 enrich
- stub person | 刘龙仙 | 103B
- stub person | 刘休范 | 111B
- stub person | 陈立 | 116B
- stub person | 卫子夫 | 126B
- stub person | 吕纂 | 127B
- stub person | 论惟明 | 127B
- stub person | 焦延寿 | 128B
- stub person | 汉殇帝 | 137B
- stub person | 如姬 | 138B
- stub person | 马太后 | 138B
- stub person | 慕容楷 | 141B
- stub person | 翟璜 | 141B

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

## H10 housekeeping-scan (R3289, %11=0)
> 全库健康扫描结果
- NOTE: 无缺description字段
- NOTE: 无broken wikilinks（已知《资治通鉴》等引号类非页面链接不计）
- NOTE: 单字页面正常
- TODO: 无待处理内务
