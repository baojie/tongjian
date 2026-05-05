/**
 * pn-citation — 红楼梦 PN 段落引文插件
 *
 * PN 格式：NNN-PPP
 *   NNN = 卷号 (001–294)
 *   PPP = 段落号 (001–999)
 *
 * 功能：
 *   1. 段落锚点：将 <p>[001-006] 文字</p> → <p id="pn-001-006">文字</p>
 *   2. 引文链接：将 （001-006） → 可点击链接，跳转章节页并滚动到段落
 *
 * Hook: onAfterRender
 */

const PLUGIN_NAME = 'pn-citation';

// 匹配段落开头的 PN 标签，如 [001-006]
const RE_PN_TAG = /<p>\[(\d{3}-\d{3})\]\s*/g;

// 匹配引文写法 （001-006）（全角括号）
const RE_CITATION_PLAIN = /（(\d{3})-(\d{3})）/g;

// 匹配 wikilink 已展开形式：（<a ...>001-006</a>）
const RE_CITATION_WIKILINK = /（<a\s[^>]*class="wikilink[^"]*"[^>]*>(\d{3})-(\d{3})<\/a>）/g;

function expandAnchors(html) {
  return html.replace(RE_PN_TAG, '<p id="pn-$1"><span class="pn-label">[$1]</span> ');
}

function expandCitations(html, chapterMap) {
  // 1. wikilink 展开形式
  html = html.replace(RE_CITATION_WIKILINK, (_match, nnn, ppp) => {
    return buildCitationLink(nnn, ppp, chapterMap) ?? _match;
  });

  // 2. 纯文本形式（保护已有 <a> 标签内的内容）
  const anchors = [];
  const protected_ = html.replace(/<a[\s\S]*?<\/a>/g, m => {
    anchors.push(m);
    return `\x00a${anchors.length - 1}\x00`;
  });

  const expanded = protected_.replace(RE_CITATION_PLAIN, (_match, nnn, ppp) => {
    return buildCitationLink(nnn, ppp, chapterMap) ?? _match;
  });

  return expanded.replace(/\x00a(\d+)\x00/g, (_, i) => anchors[+i]);
}

function buildCitationLink(nnn, ppp, chapterMap) {
  const pageId = chapterMap[nnn];
  if (!pageId) return null;

  const pn = `${nnn}-${ppp}`;
  const href = `#${encodeURIComponent(pageId)}?pn=${pn}`;
  const title = `第${parseInt(nnn, 10)}卷 ¶${parseInt(ppp, 10)}`;

  return `（<a class="pn-citation" href="${href}" data-pn="pn-${pn}" title="${title}">${pn}</a>）`;
}

export default {
  name: PLUGIN_NAME,
  version: '1.0.0',

  async init(core) {
    let chapterMap = null;

    core.hooks.onBoot.add(async () => {
      try {
        const r = await fetch('data/chapter_map.json');
        chapterMap = await r.json();
        console.log(`[${PLUGIN_NAME}] 加载 ${Object.keys(chapterMap).length} 个章节映射`);
      } catch (e) {
        console.warn(`[${PLUGIN_NAME}] 无法加载 data/chapter_map.json:`, e);
      }
    });

    core.hooks.onAfterRender.add((html) => {
      html = expandAnchors(html);
      if (chapterMap) html = expandCitations(html, chapterMap);
      return html;
    });

    // PN 标签点击复制
    document.addEventListener('click', (e) => {
      const label = e.target.closest('.pn-label');
      if (label) {
        const text = label.textContent.replace(/[[\]]/g, '');
        navigator.clipboard.writeText(text).catch(() => {});
        const orig = label.textContent;
        label.textContent = '✓已复制';
        setTimeout(() => { label.textContent = orig; }, 600);
        return;
      }
    });

    // 同页点击引文：直接滚动，不触发导航
    document.addEventListener('click', (e) => {
      const a = e.target.closest('a.pn-citation');
      if (!a || !a.dataset.pn) return;
      const currentHash = location.hash.split('?')[0]; // 去掉可能携带的 ?pn=
      const targetHash = (a.getAttribute('href') || '').split('?')[0];
      if (currentHash === targetHash) {
        e.preventDefault();
        const el = document.getElementById(a.dataset.pn);
        if (el) el.scrollIntoView({ behavior: 'smooth', block: 'center' });
      }
      // 跨页：URL 已携带 ?pn=，路由器会处理滚动
    });

    core.pnCitation = {
      expand: (html) => {
        html = expandAnchors(html);
        return chapterMap ? expandCitations(html, chapterMap) : html;
      },
    };
  },
};
