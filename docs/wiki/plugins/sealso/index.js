/**
 * seealso — 页面底部自动「参见」区块
 *
 * 从 frontmatter 读取 seealso 字段（页面 ID 数组），
 * 在文章末尾注入 "参见" 区块，列出相关页面链接。
 *
 * Frontmatter 用法：
 *   seealso: [贾宝玉, 林黛玉, 薛宝钗]
 *
 * 依赖：
 *   core.registry（resolvePageId）——由 registry.js 提供
 */

import { resolvePageId } from '../../js/registry.js';

const PLUGIN_NAME = 'sealso';

// ---------- 工具 ----------

function esc(s) {
  return String(s)
    .replace(/&/g, '&amp;').replace(/</g, '&lt;')
    .replace(/>/g, '&gt;').replace(/"/g, '&quot;');
}

/**
 * 将 seealso 条目数组渲染为 HTML 列表。
 * 每个条目可以是页面 ID 或 "ID|显示文字" 格式。
 */
function renderSeeAlsoList(items, resolve) {
  const links = items.map((item) => {
    const str = String(item).trim();
    if (!str) return null;

    // 支持 "目标|显示文字" 格式
    let target, display;
    const pipeIdx = str.indexOf('|');
    if (pipeIdx > 0) {
      target = str.slice(0, pipeIdx).trim();
      display = str.slice(pipeIdx + 1).trim();
    } else {
      target = str;
      display = null;
    }

    const resolved = resolve(target);
    const pid = resolved ? resolved[0] : target;
    const label = display || (resolved?.[1]?.label) || target;
    const cls = resolved ? 'wikilink resolved' : 'wikilink broken';
    const title = resolved ? '' : ` title="未解析: ${esc(target)}"`;

    return `<li><a class="${cls}" href="#${encodeURIComponent(pid)}"${title}>${esc(label)}</a></li>`;
  }).filter(Boolean);

  if (!links.length) return '';

  return `<section class="sealso-section" aria-label="参见">
    <h2>参见</h2>
    <ul>${links.join('')}</ul>
  </section>`;
}

// ---------- 样式 ----------

const STYLES = `
.sealso-section {
  margin-top: 2em;
  padding: 1em 1.2em;
  background: var(--bg-box, #f8f6f0);
  border: 1px solid var(--border, #e0dcd0);
  border-radius: 6px;
}
.sealso-section h2 {
  font-size: 1em;
  margin: 0 0 .6em;
  color: var(--accent, #7a1f1f);
}
.sealso-section ul {
  margin: 0;
  padding: 0;
  list-style: none;
  display: flex;
  flex-wrap: wrap;
  gap: .4em .8em;
}
.sealso-section li {
  margin: 0;
  padding: 0;
}
.sealso-section li::before {
  content: "·";
  margin-right: .6em;
  color: var(--fg-muted, #999);
}
.sealso-section li:first-child::before {
  content: none;
  margin-right: 0;
}
`;

function injectStyles() {
  if (document.getElementById('sealso-style')) return;
  const el = document.createElement('style');
  el.id = 'sealso-style';
  el.textContent = STYLES;
  document.head.appendChild(el);
}

// ---------- 插件入口 ----------

export default {
  name: PLUGIN_NAME,
  version: '1.0.0',
  description: '页面底部自动「参见」区块',

  async init(core) {
    injectStyles();

    core.hooks.onAfterRender.add(async (html, ctx) => {
      const front = ctx?.front;
      if (!front) return html;

      // 支持 seealso / related 字段
      const items = front.seealso || front.related || [];
      if (!items || (Array.isArray(items) && items.length === 0)) return html;

      const rawList = Array.isArray(items) ? items : [items];
      if (rawList.length === 0) return html;

      const resolve = (target) => resolvePageId(target, core.registry);
      const seeAlsoHtml = renderSeeAlsoList(rawList, resolve);
      if (!seeAlsoHtml) return html;

      return html + seeAlsoHtml;
    });
  },
};
