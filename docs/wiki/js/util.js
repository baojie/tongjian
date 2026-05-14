/* 纯工具函数, 无模块依赖。 */

export const TYPE_LABELS = {
  // 人物
  person: '人物',
  // 地点/文明
  place: '地点',
  civilization: '文明',
  // 科技/设备
  technology: '科技',
  weapon: '武器',
  // 组织
  organization: '组织',
  // 事件
  event: '事件',
  battle: '战役',
  // 国家/王朝/民族
  state: '国家',
  dynasty: '王朝',
  tribe: '民族',
  // 官职
  official: '官职',
  // 年份
  year: '年份',
  // 典籍
  classic: '典籍',
  // 制度/法律/经济/军事
  institution: '制度',
  law: '法律',
  economy: '经济',
  military: '军事',
  // 器物/天文/礼制
  artifact: '器物',
  astronomy: '天文',
  ritual: '礼制',
  // 通用概念
  concept: '概念',
  // 纪元
  era: '纪元',
  // 书册/章节
  book: '卷册',
  chapter: '章节',
  // 名句
  quote: '名句',
  // 故事（云天明童话等）
  story: '故事',
  // 页面类型
  topic: '主题',
  overview: '综述',
  list: '列表',
  disambiguation: '消歧义',
  redirect: '重定向',
  special: '特殊页面',
  meta: '元页',
  unknown: '未知',
  // 红楼梦专用
  family: '家族',
  object: '器物',
  poem: '诗词',
  // 新类别
  food: '饮食',
  姓氏: '姓氏',
  clothing: '服饰',
  medicine: '医药',
  game: '游戏',
  classic: '典籍',
  ritual: '礼仪',
  time: '时间',
  symbol: '象征',
  painting: '书画',
  mythology: '神话',
  music: '音乐',
  study: '红学',
  edition: '版本',
  adaptation: '改编',
  skill: '技能',
  // 动物/植物
  animal: '动物',
  plant: '植物',
  // 概念子类（由 concept_cat 拆分，已与英文类型合并）
  '军事': '军事', '政治': '政治', '社会': '社会', '礼制': '礼制',
  '自然': '自然', '经济': '经济', '哲学': '哲学', '成语': '成语',
  '器物': '器物', '道德': '道德', '官职': '官职', '法律': '法律',
  '官制': '官制', '度量': '度量', '器用': '器用', '年号': '年号',
  '人体': '人体', '动物': '动物', '情感': '情感', '地理': '地理',
  '时间': '时间', '建筑': '建筑', '典籍': '典籍', '天文': '天文',
  '植物': '植物', '服饰': '服饰', '文艺': '文艺', '爵位': '爵位',
  '教育': '教育', '民族': '民族', '历法': '历法', '神话': '神话',
  '生物': '生物', '宗教': '宗教',
};

export function escapeHtml(s) {
  return String(s).replace(/[&<>"']/g, (c) =>
    ({'&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'}[c]));
}

export function escapeAttr(s) { return escapeHtml(s); }

export function setStatus(msg) {
  const el = document.getElementById('status');
  if (el) el.textContent = msg;
}

export function showFatal(msg) {
  const article = document.getElementById('article');
  if (article) {
    article.innerHTML = `<h1>错误</h1><p class="error">${escapeHtml(msg)}</p>`;
  }
  setStatus('');
}
