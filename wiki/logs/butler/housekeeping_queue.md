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

## H10 housekeeping-scan (R3344, %11=0)
> 全库健康扫描结果
- NOTE: 无缺description字段（9771页全覆盖）
- NOTE: 无严重broken wikilinks
- NOTE: 无待处理内务

## H10 housekeeping-scan (R3366, %11=0)
> 全库健康扫描结果
- NOTE: 5页缺description字段 → 北伐、币_(概念)、廨舍、漕_(概念)、陂_(概念)（均为concept类型）
- NOTE: 无严重broken wikilinks
- NOTE: 单字页面正常（573单字非章节页属已知现象）
- TODO: 补充5页description字段（H4 enrich-meta）

## H10 housekeeping-scan (R3399, %11=0)
> 全库健康扫描结果
- NOTE: 无缺description字段
- NOTE: 无严重broken wikilinks
- NOTE: 3条stub <100B → 埙_(概念)(82B)、敦_(概念)(55B)、项_(概念)(55B)
- TODO: 待 enrich 实例处理残余 stub

## H10 housekeeping-scan (R3498, %11=0)
> 全库健康扫描结果
- NOTE: 无缺description字段
- NOTE: 无严重broken wikilinks
- NOTE: 2条stub <100B → 埙_(概念)(82B)、项_(概念)(55B)
- TODO: 待 enrich 实例处理残余 stub

## W5 反思 (R3393, %29=0)
> 全库状态扫描与模式分析
- 库规模：9882页（concept 4428 / person 3126 / place 601 / year 353 / chapter 294）
- 缺description：5页（北伐、币_(概念)、廨舍、漕_(概念)、陂_(概念)）
- 多实例协同：6实例并行（司马光/create、刘攽/enrich、刘恕/discover、范祖禹/housekeeping、战争挖掘/军事、资治通鉴/全局）
- 观察A：发现轮次稳定产出8条/轮，但 P2 消费滞后（积累大量待建 concept）
- 观察B：enrich-quality 轮次活跃，质量提升在持续
- 观察C：H20 wikilink-pass 每13轮自动执行，覆盖充分
- 建议：P2 concept 消费速度需加快，建议 enrich 实例关注 P2 队列

## H17 coverage-scan (R3441, %37=0)
> 页面元数据覆盖扫描结果
- GAP: 3126/3126 person 页面缺少 cat 字段（100%）— 持续
- GAP: 225/225 event/battle 页面缺少 event_type 字段（100%）— 持续
- GAP: 9953/9953 页面缺少 dynasty 字段（100%）— 持续
- RECOMMEND: 三个字段均需批量脚本修复，建议开发 batch_fix_meta.py

## W5 反思 (R3451, %29=0)
> 多实例协同状态
- 最近20行动：discover×7 / enrich-quality×5 / enrich-page×3 / housekeeping×2 / create-page×2 / create×1
- 活跃实例：司马光、刘攽、刘恕、范祖禹、资治通鉴（5实例并行）
- 观察A：discover 持续产出（刘恕主导），稳定 8条/轮
- 观察B：enrich-quality 和 enrich-page 轮次活跃（刘攽/司马光），质量提升持续
- 观察C：H17 仍在全 gap 状态，需开发批量脚本
- 观察D：库规模已达 ~9953页，概念词条持续丰富
- 建议：P2 消费仍然滞后，可考虑启动专用 enrich 实例消费 P2 concept 队列
