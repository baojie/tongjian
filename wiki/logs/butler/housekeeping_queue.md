# 资治通鉴 Wiki Butler 内务队列

## H-P1 — 紧急内务
<!-- 空 -->

## H-P2 — 常规内务

### W5 反思 (R9309, R9312 发布)
> 全库状态扫描与模式分析（上次W5: R9019，间隔290轮）

- **轮次**: R9019—R9312, 293轮, accept 291/291 (100%)
  - enrich-quality 主导（~95%），~870页 inline PN→blockquote 转换
  - 其他周期任务 H20/H21/H22/H23/H24 正常执行，全部收敛
  - R9312 %97=0 /wiki publish：3d647a72b，732文件变更清账

- **库规模**: 17261页（不变）
  - 质量: standard 4691 / featured 604 / basic 1259 / none 10707
  - 非章节页: 16967
  - 知识量 K=255,551

- **候选池**: 409页待转换（ic≥2且ic⊆bp）
  - ic=2: 73页（易处理）
  - ic=3: 102页
  - ic=4: 74页
  - ic≥5: 160页
  - ic⊈bp: 784页（不匹配，需另案处理）

- **发布状态**: R9028→R9312 积压已清，732文件提交推送

- **观察A**: enrich-quality 仍为主导模式，候选池尚余409页（ic⊆bp），其中73页ic=2可快速消耗
- **观察B**: 周期任务全部正常收敛
- **观察C**: 无新页创建，库规模完全冻结于17261页
- **观察D**: featured 精品页40，未增长
- **观察E**: ic⊈bp 的784页需要不同的enrich策略（inline PN未被blockquote完全覆盖）

- **建议**:
  1. 继续 enrich-quality ic=2 候选消耗（73页存量）
  2. ic=3/4 页逐步处理
  3. ic⊈bp 类型需下游分析后再决策
### W5 反思 (R9135, %29)
> 全库状态扫描与模式分析（上次W5: R9106）

- **轮次**: R9106—R9134, 28轮, accept 28/28 (100%)
  - enrich-quality×21（~63页 inline PN→blockquote 转换）
  - H22 fix-emdash×3（R9112: 5/50, R9129: 1/50 → 持续低量收敛）
  - H21 person-table-scan×3（连续零错误）
  - H20 wikilink-pass×1（R9126: 0/2308修改，绝对饱和）
  - W5×1（R9106）

- **库规模**: 17261页（与R9106一致，无新页）
  - 质量: standard 4691 / featured 604 / basic 1259 / none 10707
  - 非章节页: 16967

- **候选池**: ~604页 <800B 待转换 inline PN→blockquote
- **精选页**: 40

- **暂存状态**: 87文件, 980新增, 129删减（自R9028发布后积压）

- **观察A**: enrich-quality 持续为主导模式（75%），薄页池仍有~604页存量
- **观察B**: H21/H22/H20 均达收敛终端，连续多轮零错误/零修改
- **观察C**: 无 create-page 轮次（0 新页创建），focus 纯在质量提升
- **观察D**: 距上次发布（R9028）已~107轮，下次发布 R9193（%97=0）尚有 58 轮

- **建议**: 
  1. 继续 enrich-quality inline→blockquote 转换（存量充裕）
  2. 候选池如枯竭可转向 person 类型薄页（<700B 无 blockquote）
  3. dynasty 批量填充仍待规划（~3935 页缺）

### W5 反思 (R9044, >50轮强制)
> 全库状态扫描与模式分析（上次W5: R8941）

- **库规模**: 17261页
  - 人物5509 / 官职1699 / 年份1364 / 地点1058 / 军事944 / 概念862 / 政治621 / 事件472 / 礼制451 / 社会440 / 经济397 / 器物374 / 自然311 / 章节294 / 成语270 / 哲学230 / 法律223 / 道德192 / 官制172 / 战役112 / 器用108 / 天文97 / 年号96 / 制度95 / 综述88 / 国家84 / 情感70 / 动物61 / 时间59 / 建筑53 / 民族52 / 地理49 / 典籍48 / 名句47 / 植物36 / 服饰34 / 爵位32 / redirect12 / 历法7 / 神话5 / 宗教2

- **质量分布**: standard 4692 / featured 604 / basic 1259
  - 6555页有quality字段（38%），10706页无quality字段（含章节页和早期页）
  - 正文>1500B页数: 5880
  - stub<300B的enrichable页: 19页（天册/澧州/神功/道州/辰州等）

- **元数据覆盖**:
  - 缺description: 0 ✅（全覆盖）
  - 缺dynasty: 4229/17261（24.5%）— 较R8941的22.8%略升（新建年号页未带dynasty）
  - person.cat: 全覆盖 ✅
  - event/battle event_type: 全覆盖 ✅

- **最近103轮模式（R8941-R9044）**:
  - enrich-quality×45（主导，~135页enriched）
  - create-page×16（年号创建为主，至R8983基本覆盖全部年号）
  - H23 merge-geo-official×10（R8940-R8982完全收敛，清除~891处）
  - H20 wikilink-pass×6（增量递减：18页/轮→2页/轮，接近饱和）
  - H21 person-table-scan×3（连续零错误）
  - H22 fix-emdash×3（完全收敛，0修改）
  - H17/H18/W5×3（周期扫描均正常）
  - publish×1（R9028发布）

- **观察A: enrich-quality池近枯竭** — 35/50（70%），可enrich的概念/官职/地点薄页仅剩19页，本模式已近终端
- **观察B: 年号创建完成** — 三国至南北朝年号已全部补齐，create-page转向枯竭
- **观察C: H23完全收敛** — 历时10轮清除~891处合并，新建页不再产出拆分模式
- **观察D: H20 wikilink接近饱和** — 从R8996的25页/422链接降至R9034的15页/233链接，全库wikilink填充率极高
- **观察E: H21/H22持续零错误** — 已达终极收敛状态
- **观察F: 无G类架构问题** — 页面类型统一，PN格式一致，heading格式标准化

- **建议**: enrich-quality池即将耗尽，下一阶段策略可考虑：
  1. **H4 enrich-original-quote** — 将现有inline PN（`文字（NNN-PPP）`）改造为blockquote+PN格式，提升引文规范
  2. **D1 corpus-discover** — 用corpus_discover.py从原文挖掘新候选（州名/事件类）
  3. **dynasty批量填充** — 开发脚本批量补全4229页的dynasty字段
  4. **featured精品页制作** — 筛选重要词条深化至featured级

### H24 merge-compound-wikilinks — 合并所有复合词条拆分 wikilink ✅ 已完成
> 状态：已完成（2026-05-09 R8710 完全收敛，0 文件待处理）
- 原发现 470 种复合词条被拆开，共 ~2376 处
- 经 R8676-R8710 共 15 轮 ~750 页处理后完全收敛
- 工具：`python3 wiki/scripts/butler/h24_merge_compound_wikilinks.py --limit 50`
- 执行记录：R8657(81处)→R8672(92处)→R8674(69处)→R8676(85处)→R8677(80处)→R8678(79处)→R8679(77处)→R8680(71处)→R8681(77处)→R8683(101处)→R8684(87处)→R8685(87处)→R8686(81处)→R8688(89处)→R8690(102处)→R8691(78处)→R8692(92处)→R8693(74处)→R8694(100处)→R8695(76处)→R8696(75处)→R8697(67处)→R8698(83处)→R8699(74处)→R8702(89处)→R8703(81处)→R8704(85处)→R8705(91处)→R8706(104处)→R8707(54处)→R8709(3处)→R8710(0处)
- [x] H-P2 merge-compound-wikilinks | 全库 | 合并复合词条拆分wikilink（约2376处）

### W5 反思 (R9077, %29)
> 全库状态扫描与模式分析（上次W5: R9019）

- **轮次**: R9019—R9077, 58轮, accept 58/58 (100%)
- **本周期 enrich-quality**: ~96页 inline PN→blockquote 转换
- **H20**: 4次扫描, 链接递减 (422→130→53), 趋近饱和
- **H21/H22**: 继续零错误, 完全收敛
- **暂存状态**: 87文件, 1087行新增, 上次发布R9028
- **剩余池**: ~215页 <650B 待转换 inline PN→blockquote
- **结论**: 稳态维护, 无架构问题, 继续 enrich-quality 转换

### W5 反思 (R9106, %29)
> 全库状态扫描与模式分析（上次W5: R9077）

- **轮次**: R9078—R9105, 28轮, accept 28/28 (100%)
  - enrich-quality×19（~57页 inline PN→blockquote 转换）
  - H22×2（0/50, 0/50, 完全收敛）
  - H21×2（0错误, 完全收敛）
  - H20×1（R9087: 仅1页/1链接, 接近绝对饱和）

- **库规模**: 17261页（与R9077一致, 无新建页）
  - 非章节页: 16967
  - 质量: standard 4691 / featured 604 / basic 1259 / none 10707
  - 缺dynasty: ~3935（23.2%, 与R9077持平）

- **暂存状态**: 24文件, 302新增, 8删减（自R9028发布后积压）

- **观察A**: enrich-quality 池持续消耗, 约430页待转换（较R9077的~215页池扩至包括所有无blockquote非人物页）
- **观察B**: H20 绝对饱和（仅1链接/轮）, H21/H22 持续零错误
- **观察C**: 无新页面创建（0 create-page轮次）, focus纯在质量提升
- **观察D**: 暂存24文件无异常, 等待R9193（%97=0）发布

- **建议**: 
  1. 继续 enrich-quality inline→blockquote 转换
  2. 剩余池中可考虑转向人物类型薄页（person <700B, 无blockquote）
  3. dynasty批量填充仍待规划（~3935页缺）

### H23 merge-geo-official — 合并地名+官名拆分 wikilink ✅ 已完成
> 状态：已完成（2026-05-09 R8676 完全收敛，0 文件待处理）
- 原发现 1144 处「地名+官名」被拆成两个分离 wikilink，涉及 165 个词条
- 经 R8649/R8660/R8676 共 13 页处理后完全收敛
- 工具：`python3 wiki/scripts/butler/h23_merge_geo_official.py --limit 50`
- [x] H-P2 merge-geo-official | 全库 | 合并地名+官名拆分wikilink（约1144处）

### H22 fix-emdash — 修复破折号段落 ✅ 基本完成
> 状态：已完成（R5159 命中率降至 6%，原始 463 页池基本清空）
- 发现463个词条含「——」切分段落（2026-05-07 R4544首次扫描）
- 根源：Butler 写作时将论述句用「——」连接为超长行，影响可读性
- 修复策略：
  - description 字段：截断到首个「——」前
  - 正文两段切分（各≥40字）：改为两段（句号+空行）
  - 正文三项以上短列举（各5-50字）：转为无序列表
  - 正文三项以上长论述：「——」改为「。」连接
- 禁止修改：引用块 `>` 行（原文直引），章节页（第???卷.md）
- 工具：`python3 wiki/scripts/butler/h22_fix_emdash.py --limit 50`
- 执行记录：R5105(6/50)→R5112(6/50)→R5118(5/50)→R5122(5/50)→R5140(5/50)→R5152(5/50)→R5154(4/50)→R5159(3/50)

## H10 housekeeping-scan (R2519, %11=0)
> 全库健康扫描结果
- NOTE: 5页缺description字段 → 备御、劲兵、名籍、社稷、饷道（均为concept类型）
- NOTE: 无broken wikilinks
- NOTE: 无单字页面问题
- TODO: 补充5页description字段（H4 enrich-meta）

## H-P3 — 探索内务
  [x] H-P3 housekeeping-scan | 全局 | 初始覆盖率扫描（R8829完成: 14929页/0缺desc/0 stub<100B）

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

## H10 housekeeping-scan (R3685, %11=0)
> 全库健康扫描结果
- NOTE: 无缺description字段
- NOTE: 无严重broken wikilinks（5381条broken links中多为label/别名未匹配，非真正断裂）
- NOTE: 无stub <100B（10377页全覆盖）
- TODO: 无待处理内务

## H10 housekeeping-scan (R3740, %11=0)
> 全库健康扫描结果
- NOTE: 无缺description字段（10539页全覆盖）
- NOTE: 无严重broken wikilinks（12392条broken links多为label/别名未匹配，非真正断裂）
- NOTE: 2条stub <100B → 项_(概念)(55B)、埙_(概念)(82B)（持续多轮无变化）
- TODO: 残余stub待 enrich 实例处理

## H10 housekeeping-scan (R3762, %11=0)
> 全库健康扫描结果
- NOTE: 无缺description字段（10562页全覆盖）
- NOTE: 无严重broken wikilinks
- NOTE: 2条stub <100B → 项_(概念)(55B)、埙_(概念)(82B)
- TODO: 待 enrich 实例处理残余 stub

## H10 housekeeping-scan (R3894, %11=0)
> 全库健康扫描结果
- NOTE: 无缺description字段（10675页全覆盖）
- NOTE: 无严重broken wikilinks
- NOTE: 无stub <100B
- TODO: 无待处理内务

## D1 discover-wanted (R3894, %11=0)
> 全库broken wikilink扫描，top 60
- NOTE: 高频broken links包括「《资治通鉴》」(1741次)、「唐代」(150)、「权力」(69)等
- NOTE: 可建设的概念类页面：财政(33)、边防(21)、行政(20)、宫廷(11)、商业(17)等
- TODO: 待消费P2队列中的concept类词条

## H18 stub-triage (R3941, %37=19)
> 全库 person body < 500B 共 1355 条，person 类型优先 enrich
- stub person | 如姬 | 163B
- stub person | 翟璜 | 166B
- stub person | 杨炯 | 173B
- stub person | 卢照邻 | 174B
- stub person | 汉殇帝 | 185B
- stub person | 吕纂 | 187B
- stub person | 缇萦 | 190B
- stub person | 干宝 | 196B
- stub person | 马太后 | 214B
- stub person | 徐淑 | 215B
- stub person | 李光仕 | 216B
- stub person | 刘长 | 217B
- stub person | 唐穆宗 | 219B
- stub person | 杨俊 | 220B
- stub person | 慕容宝 | 221B
- stub person | 窦后 | 226B
- stub person | 杨谅 | 229B
- stub person | 赵飞燕 | 232B
- stub person | 刘柏根 | 233B
- stub person | 杨法琛 | 233B
- stub person | 栾巴 | 233B
- stub person | 程日华 | 234B
- stub person | 薛王业 | 234B
- stub person | 郭躬 | 235B
- stub person | 唐懿宗 | 236B
- stub person | 孙秀 | 236B
- stub person | 张永 | 236B
- stub person | 少翁 | 237B
- stub person | 徐商 | 237B
- stub person | 窦皇后 | 237B

## H10 housekeeping-scan (R4070, %11=0)
> 全库健康扫描结果
- NOTE: 无缺description字段（10850页全覆盖）
- NOTE: 无严重broken wikilinks
- NOTE: 无stub <100B
- TODO: 无待处理内务

## D1 discover-wanted (R4070, %11=0)
> 全库broken wikilink扫描，top 60
- NOTE: 高频broken links包括「《资治通鉴》」(1717次)、「唐代」(175)、「权力」(98)等
- NOTE: 可建设的概念类页面：财政(43)、中央(30)、地方(27)、边疆(26)、行政(24)等
- TODO: 待消费P2队列中的concept类词条

## H21 person-table-scan（round % 13 == 7 自动触发）
> 扫描 type=official 页面任职者表格中的人名提取错误（h21_audit_person_tables.py）
- NOTE: 85页含598条可疑条目（短指代残留、官职前缀粘入、虚词开头、动词短语、含标点）
- NOTE: 常见错误模式：[[会闾出]]→[[高闾]]、[[太仆卿王昱]]→[[王昱]]、[[欢袭击]]→[[高欢]]（+清除verb后缀）
- TODO: 逐页运行 python3 wiki/scripts/butler/h21_audit_person_tables.py --fix 交互式修正

## H17 coverage-scan (R4070, %37=0)
> 页面元数据覆盖扫描结果
- GOOD: person.cat 已全覆盖（3126/3126，0%缺失）
- GOOD: event.event_type 已全覆盖（225/225，0%缺失）
- GAP: 4409/10856 页面缺少 dynasty 字段（40.6%）
- RECOMMEND: 需批量脚本修复 dynasty 字段

## H10 housekeeping-scan (R4125, %11=0)
> 全库健康扫描结果
- NOTE: 无缺description字段（10628页全覆盖）
- NOTE: 无严重broken wikilinks
- NOTE: 无stub <100B
- TODO: 无待处理内务

## D1 discover-wanted (R4125, %11=0)
> 全库broken wikilink扫描，top 60
- NOTE: 高频broken links包括「《资治通鉴》」(1697次)、「唐代」(194)、「权力」(119)等
- NOTE: 可建设的概念类页面：财政(47)、中央(33)、地方(35)、边疆(29)、行政(24)等
- TODO: 待消费P2队列中的concept类词条

## W5 反思 (R4503, %29=0 delayed)
> 全库状态扫描与模式分析

- **库规模**：11378页
  - concept 5724 / person 3162 / place 606 / year 416 / chapter 294 / event 144 / battle 81 / state 59
  - 其他：official 139 / artifact 137 / military 119 / economy 96 / institution 94 / ritual 72

- **多实例协同**：4~5实例并行
  - 刘恕/discover：主导发现，持续产出南北朝宗室人物
  - 刘攽/enrich-quality：稳定提升页面质量
  - 司马光/create-page：新建词条（概念+人物）
  - 资治通鉴：enrich-page + publish

- **P2队列**：4843条待消费，3423条已完成（消费率41.4%）
  - discover 持续 > 消费速度，P2积压仍在增长

- **观察A**：发现轮次稳定产出8条/轮，多实例并行（刘恕×10 / 最近20轮）
- **观察B**：enrich-quality 轮次活跃（刘攽×5 / 最近20轮），质量提升持续
- **观察C**：P2 person 类别逐步覆盖南北朝宗室，池子趋窄但仍有存量
- **观察D**：库规模从 ~9953页（R3451）增长至 11378页（+1425页，+14.3%）
- **观察E**：W5长期未执行（距上次W5已~1052轮），多实例自动运行无需干预
- **建议**：P2消费仍需加速，建议司马光/enrich实例更多消费P2队列而非新建

## W5 反思 (R4553, %29=0)
> 全库状态扫描与模式分析

- **库规模**：11378+页（持续增长中）
- **多实例协同**：刘恕/discover、刘攽/enrich-quality、司马光/create-page、资治通鉴/enrich+publish
- **发现趋势**：人物发现已从南北朝宗室→先秦→两汉→魏晋→唐，覆盖逐步全面
- **观察A**：P2待消费仍远大于已完成（~4800+ vs ~3400），消费端需加速
- **观察B**：P3/P2队列中人物类型条目积累量大，enrich/create实例可优先消费
- **观察C**：H20 wikilink-pass（R4537）正常执行，64页+464链接
- **观察D**：R4375-R4553 连续~180轮稳定产出，无中断
- **建议**：人物发现池趋窄，可切换至 concept/place 类型发现

## H10 housekeeping-scan (R4598, %11=0)
> 全库健康扫描结果
- NOTE: 49页缺description字段 → 不知所措、侵暴、侵盗、关_(概念)、剑履、勋绩、北伐、华_(概念)、卷旗、咸宁等
- NOTE: 无严重broken wikilinks
- NOTE: 无stub <100B（11495页全覆盖）
- TODO: 补充49页description字段（H4 enrich-meta）

## D1 discover-wanted (R4598, %11=0)
> 全库broken wikilink扫描，top 60
- NOTE: 高频broken links包括「《资治通鉴》」(1621次)、「唐代」(322)、「权力」(182)等
- NOTE: 可建设的概念类页面：财政(53)、中央(60)、地方(71)、边疆(71)、行政(43)等
- TODO: 待消费P2队列中的concept类词条

## H10 housekeeping-scan (R4763, %11=0)
> 全库健康扫描结果
- NOTE: 2页缺description字段 → 卢毓(person)、甓_(概念)(concept)
- NOTE: 无stub <100B（13200页全覆盖）
- NOTE: broken wikilinks仍以《资治通鉴》/唐代/权力等高频词为主，无严重断裂
- TODO: 补充2页description字段（H4 enrich-meta）

## D1 discover-wanted (R4763, %11=0)
> 全库broken wikilink扫描，top 60
- NOTE: 高频broken links包括「《资治通鉴》」(1547次)、「唐代」(354)、「权力」(222)等
- NOTE: 可建设的人物类页面：张黎(30)、李云(30)、陈杲仁(30)、晋安王宝义(84)等
- TODO: 待消费P2队列中的concept类词条

## R4994 %11 批量发布
> wiki: R4994 批量发布 — 资治通鉴 enrich-quality×48 + create-page×8 + 多实例积累
- create-page×8: 财产/棣州/安州/武力/王国/李离/冯宿/孟宗
- enrich-quality×48: 法律/宗教/经济/交通/官制/礼制/社会等概念词条
- 修复大量 concept 页面 type 字段（哲学→concept, 法律→concept, 礼制→concept 等）
- 多实例积累：含其他实例新建页及 enrich 成果
- D1 discover: 高频broken links仍以《资治通鉴》(1511)、唐代(371)、权力(225)为主

## H10 housekeeping-scan (R5131)
> 全库健康扫描结果
- NOTE: 无缺description字段（13306页全覆盖）
- NOTE: 无stub <100B
- NOTE: 无严重broken wikilinks（29125条中《资治通鉴》/通鉴/资治通鉴占3568条为已知别名匹配，非真正断裂）
- TODO: 无待处理内务

## W5 反思 (R5148, %29=0)
> 全库状态扫描与模式分析

- **库规模**：13310页
  - 人物3632 / 年份1363 / 军事978 / 地点697 / 政治655 / 官职600 / 礼制477 / 社会456 / 概念437 / 经济420 / 器物385 / 自然337 / 成语270 / 哲学257 / 法律236 / 道德221 / 官制172 / 度量146 / 器用145 / 事件144 / 天文105 / 年号96 / 制度94 / 战役81 / 人体79 / 综述77 / 动物74 / 情感71 / 地理66 / 时间65 / 建筑63 / 国家59 / 民族52 / 典籍49 / 名句47 / 植物45 / 服饰39 / 爵位33 / 文艺28 / 教育22 / 王朝15 / 历法7 / 神话6

- **多实例协同**：5实例并行
  - 刘恕/discover：1286次行动，主导发现，近期转向州名官职
  - 刘攽/enrich-quality：1125次，持续人物补世系
  - 资治通鉴：1038次，年号创建+小页富化
  - 司马光/create-page：922次，批量创建人物/概念
  - 范祖禹/housekeeping：387次，H10扫描+H22修复+H21扫描

- **元数据覆盖**：
  - 缺description：0 ✅（13310页全覆盖）
  - person缺cat：0 ✅
  - event/battle缺event_type：0 ✅
  - 缺dynasty：4839/13310（36.3%）— 持续缺口
  - stub <100B：0 ✅
  - featured pages：20
  - 正文大小：avg=1225B, median=954B

- **最近20轮模式**：discover×5（刘恕州名发现）/ enrich×7（刘攽补世系）/ create×4（资治通鉴年号+司马光8人物）/ housekeeping×2（范祖禹）

- **观察A**：库从R4503（11378页）增长至13310页（+1932页，+17%），人物主导
- **观察B**：刘恕发现从南北朝宗室→州名地名→官职制度，词条类型持续扩展
- **观察C**：dynasty字段36%缺失为持续瓶颈，建议批量脚本修复
- **观察D**：H22进入低量收尾（~10%命中率），预计2-3轮后完全收敛
- **观察E**：类型名称未统一（"概念"vs"concept"、"人物"vs"person"共存），属历史迁移遗留
- **建议**：dynasty字段批量修复可考虑开发batch_fix_meta.py；type名称统一待规划

## H18 stub-triage (R5165, %37=19)
> 全库 person body < 500B 共 14 条
- stub person | 陶青 | 176B
- stub person | 韩嫣 | 255B
- stub person | 王臧 | 264B
- stub person | 伏湛 | 273B
- stub person | 宋弘 | 298B
- stub person | 赵绾 | 348B
- stub person | 周仁 | 357B
- stub person | 宋昌 | 360B
- stub person | 元行冲 | 383B
- stub person | 硃买臣 | 387B
- stub person | 张武 | 407B
- stub person | 庄助 | 410B
- stub person | 皇甫真 | 441B
- stub person | 异人 | 476B

## H21 person-table-scan (R5610, %13=7)
> 扫描 type=official 页面任职者表格中的人名提取错误
- NOTE: 4条可疑条目，分布在4页面（丞相/太尉/都指挥使/镇东节度使）
- NOTE: 全部为吴越钱氏短指代（弘亿/弘昌/弘义/弘倧），保留原名待页面创建
- NOTE: 较R5480（同4条）无变化，H21已达收敛终端
- TODO: 吴越钱氏人物页面创建后自动解除短指代

## H17 coverage-scan (R5594, %37=0)
> 页面元数据覆盖扫描结果
- GOOD: person.cat 已全覆盖（3954/3954，0%缺失）
- GOOD: event.event_type 已全覆盖（225/225，0%缺失）
- GAP: 5135/14159 页面缺少 dynasty 字段（36.3%）
- RECOMMEND: 需批量脚本修复 dynasty 字段

## D1 discover-wanted (R5193)
> 全库broken wikilink扫描，top 60
- NOTE: 高频broken links包括「《资治通鉴》」(1478次)、「唐代」(437)、「权力」(227)等
- NOTE: 可建设的概念类页面：财政(65)、中央(68)、地方(80)、边疆(75)、行政(52)等
- TODO: 待消费P2队列中的concept类词条

## H18 stub-triage (R5643, %37=19)
> 全库 person body < 500B 共 0 条 — 全部达标
- NOTE: 全库无 person < 500B，无全类型 < 200B
- NOTE: H18 已达完全终端

## H10 housekeeping-scan (R5204)
> 全库健康扫描结果
- NOTE: 无缺description字段（13371页全覆盖）
- NOTE: 无stub <100B
- NOTE: person.cat全覆盖
- NOTE: broken wikilinks仍以《资治通鉴》/通鉴/资治通鉴为主（3612条），非真正断裂
- TODO: 无待处理内务

## W5 反思 (R5216, %29=0 delayed)
> 全库状态扫描与模式分析

- **库规模**: 13676页
  - 人物3632 / 年份1363 / 军事978 / 地点697 / 政治655 / 官职600 / 礼制477 / 社会456 / 概念437 / 经济420 / 器物385 / 自然337 / 章节294 / 成语270 / 哲学257 / 法律236 / 道德221 / 官制172 / 器用145 / 事件144 / 天文105 / 年号96 / 制度94 / 度量90 / 战役81

- **多实例协同**: 5实例并行
  - 资治通鉴(16/最近50轮): enrich-page + create-page + fix-type
  - 刘攽(14): enrich-quality + enrich-person，持续补世系
  - 范祖禹(7): housekeeping（H10/H18/W5）
  - 刘恕(7): discover，持续发现南北朝人物
  - 司马光(6): create-page + enrich-quality，概念标准化

- **元数据覆盖**:
  - 缺description: 0 ✅
  - person.cat全覆盖: 0 ✅
  - 缺dynasty: 5133/13676（37.5%）— 持续
  - stub <150B: 49条（爵位batch + 新创建person）
  - type名称碎片化: 「人物」3632+「person」73；「概念」437+「concept」50

- **最近50轮模式**: enrich-page×20 / create-page×9 / discover×7 / housekeeping×7 / enrich-quality×7

- **观察A**: 库从R5148（13310页）增长至13676页（+366，+2.7%），增长放缓
- **观察B**: dynasty缺失37.5%仍为最大元数据缺口
- **观察C**: R5213（%13=0）H20未被执行，周期任务存在争抢遗漏
- **观察D**: enrich-page占40%为主导，质量提升优先于规模扩张
- **观察E**: stub<150B共49条，主要为爵位批量创建残余，person stubs等待富化
- **建议**: dynasty批量填充脚本可优先开发；H20遗漏需关注

## W5 反思 (R5630, %29=0 delayed)
> 全库状态扫描与模式分析

- **库规模**: ~14233页
  - 人物3980 / 年份1363 / 军事978 / 地点780 / 政治655 / 官职600 / 礼制477 / 社会456 / 概念760 / 经济420 / 器物385 / 自然337 / 章节294 / 成语270 / 哲学257 / 法律236 / 道德221

- **多实例协同**（最近50轮）:
  - 刘恕: 17 (discover主导，34%)
  - 刘攽: 14 (enrich-quality，28%)
  - 资治通鉴: 9 (create-page，18%)
  - 范祖禹: 5 (housekeeping，10%)
  - 司马光: 5 (create-page，10%)

- **最近20轮模式**: discover×9(45%) / enrich-quality×4 / create-page×4 / housekeeping×3

- **元数据覆盖**:
  - 缺description: 0 ✅
  - person.cat全覆盖 ✅
  - dynasty缺失: 5135/14233（36.1%，较R5594的36.3%略降0.2pp）

- **观察A**: 刘恕discover占45%主导，远超其他实例
- **观察B**: R5626 发布+W5被刘恕discover抢占，R5627 H22也被discover抢占 — 周期任务持续丢失
- **观察C**: dynasty缺口稳定在~5135条(36.1%)，绝对数未减（新页无dynasty抵消补全）
- **观察D**: 实例竞争加剧，刘恕独占半壁，housekeeping 10%覆盖有限
- **建议**: discover占比过高需平衡；dynasty批量填充最有效投资

## 新发现策略 (R7808+)
> 从 R7808 起，housekeeping 实例的发现策略从 D1 broken wikilink 改为：
> **直接从 294 章原文（corpus/raw/资治通鉴.txt）挖掘未建页面的人名/地名/官职**
> 
> 工具: `wiki/scripts/butler/corpus_discover.py [--top N]`
> 
> 策略说明:
> - 人名: 使用「以XX为」「封XX」「拜XX」等任命/封赏模式+姓氏校验
> - 地名: 提取「X州」「X郡」「X城」「X县」后缀模式
> - 官职: 全词匹配已知官职名表
> - 所有候选均经过 all_known 去重（含 ID/label/alias）

### R7808 corpus-discover 结果
- person: 僧怀义(×7)、梁王肜(×5)、秦王俊(×5)
- place top10: 湘州(30)、洛州(29)、宣城(24)、相州(24)、司州(23)、陕州(22)、代州(22)、宁州(21)、齐州(20)、南徐州(18)
- title top5: 常侍(531)、庶子(121)、大司空(85)、大司徒(76)、安西将军(41)
- NOTE: 地名和官职发现池仍较充裕，人物发现已近饱和（4813 person页面）

## W5 反思 (R8004, %29=0)
> 全库状态扫描与模式分析

- **库规模**: 14140页
  - 人物4071 / 年份1363 / 军事944 / 地点916 / 概念848 / 政治621 / 官职598 / 礼制451 / 社会440 / 经济397 / 器物374 / 自然311 / 章节294 / 成语270 / 哲学230 / 法律223 / 道德192 / 官制172 / 事件144 / 器用108 / 天文97 / 年号96 / 制度95 / 综述88 / 国家84 / 战役81 / 情感70 / 动物61 / 时间59 / 建筑53 / 人体53 / 民族52 / 地理49 / 典籍48 / 名句47 / 植物36 / 服饰34 / 爵位32 / redirect12 / 历法7 / 神话5 / 宗教2

- **质量分布**: stub 8556 / basic 1259 / standard 3723 / featured 602
  - 正文平均: 2108B，中位数: 1190B
  - stub<200B: 12页（全部为重定向页面）

- **元数据覆盖**:
  - 缺description: 11页 → 两汉、坎瘗、市租、散、是_(概念)、毫_(概念)、素_(概念)、考第、衣食、铢_(概念)、银印（多为概念类）
  - person.cat: 4071/4071全覆盖 ✅
  - event/battle event_type: 225/225全覆盖 ✅
  - dynasty: 9304/14140（65.8%）— 4836条缺失

- **最近50轮模式**: housekeeping×35 / enrich-quality×9 / create-page×4 / discover×1 / publish×1
  - 100% 资治通鉴单实例（近期无多实例并行）
  - 核心事件：heading格式修复（R7973-7996，610页）、重定向批量创建（R7998-8003，11页）

- **高频断裂链接**：古代(124)、帝国(113)、皇权(109)、秦汉(107)、司法(80)、地方(79)、王朝(75)、中央(67)、财政(65)、文化(64) — 均为现代学术术语，难以通过简单重定向解决

- **观察A**: heading格式修复项目完成（R7973-R7996，+24轮，~610页），全库heading格式统一
- **观察B**: 重定向批量创建（R7998-8003，+11页）修复~5750断裂链接，高频term仍有~8500余
- **观察C**: 人物发现池已饱和（corpus中无可发现新人名），当前P2/P3队列steady state
- **观察D**: 所有周期任务（H10/H17/H18/H20/H21/H22）均处于收敛/完成状态，无积压待办
- **观察E**: 11个缺description的概念类页面可补，建议H4 enrich-meta处理
- **建议**: 转入稳态维护模式，重点处理dynasty字段批量填充和低挂description补全；新内容创建方向可考虑corpus内置地名（州/郡/城）而非人物发现

## H18 stub-triage (R8011, %37=19)
> 全库 person body < 500B 共 0 条 — 全部达标
- NOTE: 0 person < 500B，0 非redirect < 200B
- NOTE: H18 持续完全收敛（自R5643起持续零stub）

## H21 person-table-scan (R8015, %13=7)
> 扫描 type=official 页面任职者表格中的人名提取错误
- NOTE: 4条可疑条目（弘亿/弘昌/弘义/弘倧，吴越钱氏），均为合法人名
- NOTE: H21 已达收敛终端，无待修复

## 全库重定向创建汇总 (R7998-R8017)
> 集中创建多批重定向修复断裂链接
- 第一批 R7998: 光武帝/刘秀→光武帝刘秀, 通鉴/资治通鉴/《资治通鉴》→资治通鉴概述 (5页, ~4008链接)
- 第二批 R7999: 唐代/唐→唐朝, 秦→秦朝, 汉→汉代 (4页, ~1641链接)
- 第三批 R8000: 魏晋南北朝→南北朝 (1页, ~28链接)
- 第四批 R8003: 晚唐→唐朝, 孝文帝→北魏 (2页, ~102链接)
- 第五批 R8006: 魏孝文帝/北魏孝文帝→北魏, 秦末→秦朝, 苻生→前秦, 陈宣帝→陈朝, 吴主→吴国, 宋明帝→刘宋 (7页, ~167链接)
- 第六批 R8009: 高演→北齐, 汉赵→前赵, 成帝→汉成帝, 慕容儁→前燕 (4页, ~74链接)
- 第七批 R8010: 南唐→五代, 中国古代→中国 (2页, ~90链接)
- 第八批 R8013: 宣帝→汉宣帝, 前废帝/宋武帝→刘宋, 太武帝/宣武帝/道武帝→北魏 (6页, ~70链接)
- 第九批 R8014: 魏太武帝/魏献文帝→北魏, 晋怀帝→西晋, 汉高帝→汉高祖, 晋明帝→东晋, 楚顷襄王→楚国 (6页, ~56链接)
- 第十批 R8016: 唐哀帝→唐朝, 北魏孝武帝→北魏, 齐后主→北齐, 光武→光武帝刘秀, 僖宗→唐僖宗, 景帝→汉景帝, 李唐→唐朝 (7页, ~58链接)
- 第十一批 R8017: 曹芳→曹魏, 刘彧→刘宋, 苻丕→前秦, 慕容暐→前燕, 高殷→北齐, 石遵→后赵, 司马昱→东晋, 慕容熙→后燕, 曹彰→曹魏, 杨勇→隋, 萧詧→后梁, 苻融→前秦 (12页, ~114链接)

## W5 反思 (R8941, >50轮强制)
> 全库状态扫描与模式分析

- **库规模**: 17226页
  - 人物5507 / 官职1698 / 年份1363 / 地点1057 / 军事944 / 概念862 / 政治621 / 事件472 / 礼制451 / 社会440 / 经济397 / 器物374 / 自然311 / 章节294 / 成语270 / 哲学230 / 法律223 / 道德192 / 官制172 / 战役112 / 器用108 / 天文97 / 年号96 / 制度95 / 综述88 / 国家84 / 情感70 / 动物61 / 时间59 / 建筑53 / 民族52 / 地理49 / 典籍48 / 名句47 / 植物36 / 服饰34 / 爵位32 / redirect12 / 历法7 / 神话5 / 宗教2

- **精选页**: 40 ✅（较R8845+1）

- **元数据覆盖**:
  - 缺description: 0 ✅（全覆盖）
  - 缺dynasty: 3935/17226（22.8%）— 较R8845(32.6%)下降9.8pp
  - person.cat: 全覆盖 ✅
  - event/battle event_type: 全覆盖 ✅

- **最近22轮模式**: create-page×12(55%) / discover×3(14%) / enrich-quality×3(14%) / enrich-page×2(9%) / housekeeping×2(9%)
  - 全部为资治通鉴单实例（近期无多实例并行）

- **观察A**: create-page占55%主导，以地点和官职为主。P2队列中人物/地点/官职几乎全覆盖，新建候选池趋窄
- **观察B**: 最近发现转向事件类型（平城之围/迁都长安/中朝/大业律），可继续拓展
- **观察C**: H23(merge-geo-official)在新页中仍有69处可修复，说明新创建页持续产出此模式
- **观察D**: dynasty缺失从32.6%降至22.8%（因新建页带dynasty+后台修复），但仍需批量脚本根治
- **观察E**: P2队列12611条待办中绝大多数为单字概念页（器物/刑罚/建筑），消费意愿低
- **建议**: 下一阶段可转向高质量enrich/发现事件类型词条，或批量修复dynasty字段
