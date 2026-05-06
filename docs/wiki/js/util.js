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
  // 国家/王朝
  state: '国家',
  // 物理/科学概念
  concept: '概念',
  law: '法则',
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
