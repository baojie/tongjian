/* Wikilink 保护 / 展开。
 *
 * 为何两步走:
 *   MD 表格 '|' 会和 [[target|text]] 里的 '|' 冲突。
 *   渲染前用私用区占位符替换 [[...]], MD 跑完再换回真实 <a> 标签。
 *
 * 语法扩展：
 *   [[relation::target]]   语义链接，显示 target，记录 relation
 *   [[relation::target|显示文字]]  自定义显示
 *   [[target]]   /  [[target|显示文字]]  保持原样
 */

const PH_OPEN = '';
const PH_CLOSE = '';
const SEMANTIC_WIKILINK_RE = /\[\[([^\[\]|:]+?)::([^\[\]|]+?)(?:\|([^\[\]]+?))?\]\]/g;
const REGULAR_WIKILINK_RE = /\[\[([^\[\]|]+?)(?:\|([^\[\]]+?))?\]\]/g;
const PH_RE = /(\d+)/g;

export function protectWikilinks(body) {
  const tokens = [];
  // 先处理语义链接 [[rel::target]]，再处理普通 [[target]] / [[target|text]]
  // 顺序不能反，否则 :: 会被普通规则吞掉
  let text = body.replace(SEMANTIC_WIKILINK_RE, (match, relation, target, display) => {
    tokens.push({
      relation: relation.trim(),
      target: target.trim(),
      text: display ? display.trim() : target.trim(),
    });
    return PH_OPEN + (tokens.length - 1) + PH_CLOSE;
  });
  text = text.replace(REGULAR_WIKILINK_RE, (match, target, display) => {
    tokens.push({ target: target.trim(), text: display ? display.trim() : null });
    return PH_OPEN + (tokens.length - 1) + PH_CLOSE;
  });
  return { protectedText: text, tokens };
}

/**
 * @param {string} html   MD 渲染后的 HTML (含占位符)
 * @param {Array}  tokens protectWikilinks 返回的 token 数组
 * @param {object} opts
 *   @param {string}   opts.selfId   当前页 id, 用于 self 样式
 *   @param {function} opts.resolve  (target) => [pid, entry] | null
 *   @param {function} opts.onBroken (target) => void  断链记录回调
 *   @param {function} opts.escape   HTML 转义函数
 */
export function expandWikilinks(html, tokens, opts) {
  const { selfId, resolve, onBroken, escape } = opts;
  return html.replace(PH_RE, (_, idxStr) => {
    const token = tokens[+idxStr];
    const { target, text, relation } = token;
    let display = text != null ? text : target;
    // 语义链接的 display 已由 protectWikilinks 提供，不走 '/' 截断
    if (!relation && text == null && target.includes('/')) {
      display = target.split('/', 2)[1];
    }
    const resolved = resolve(target);
    const relAttr = relation ? ` data-rel="${escape(relation)}"` : '';
    if (!resolved) {
      onBroken(target);
      return `<a class="wikilink broken" href="#${encodeURIComponent(target)}"` +
        ` data-target="${escape(target)}"${relAttr}` +
        ` title="未解析: ${escape(target)}">${escape(display)}</a>`;
    }
    const [pid] = resolved;
    let cls = pid === selfId ? 'wikilink self' : 'wikilink resolved';
    if (relation) cls += ' semantic';
    return `<a class="${cls}" href="#${encodeURIComponent(pid)}"${relAttr}>${escape(display)}</a>`;
  });
}
