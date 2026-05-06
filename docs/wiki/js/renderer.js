/* 页面 / 首页 / 404 / infobox 的 DOM 挂载。
 *
 * 解析逻辑 (frontmatter + MD + wikilink + hook) 全在 parser.js。
 * 本模块只把解析结果填到 DOM, 并管元数据/导航/状态栏。
 */

import { escapeHtml, TYPE_LABELS } from './util.js';
import { parseMarkdown } from './parser.js';
import { resolvePageId } from './registry.js';

const QUALITY_BADGE = { premium: '旗舰', featured: '精品', standard: '标准' };
const QUALITY_RANK = { premium: 1000, featured: 500, standard: 100, basic: 10, stub: 0 };

/* DOM 级加粗：在 article 内找到页面名/别名所在的文本节点并加粗。
 * 跳过标题（h1-h6）、已有链接（a）、代码块（pre/code）、已加粗的（strong）。 */
function boldPageTermsInDOM(root, pageTerms) {
  const terms = [...new Set(pageTerms)].filter(Boolean);
  if (terms.length === 0) return;
  const sorted = terms.sort((a, b) => b.length - a.length);
  const re = new RegExp(
    sorted.map(t => t.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')).join('|'),
    'g'
  );

  const skipTags = new Set(['H1', 'H2', 'H3', 'H4', 'H5', 'H6', 'PRE', 'CODE', 'STRONG']);
  const walker = document.createTreeWalker(root, NodeFilter.SHOW_TEXT, {
    acceptNode: (node) => {
      for (let el = node.parentElement; el && el !== root; el = el.parentElement) {
        if (skipTags.has(el.tagName)) return NodeFilter.FILTER_REJECT;
        if (el.classList && (el.classList.contains('pn-label') || el.classList.contains('pn-citation'))) return NodeFilter.FILTER_REJECT;
      }
      return re.test(node.textContent) ? NodeFilter.FILTER_ACCEPT : NodeFilter.FILTER_REJECT;
    },
  });

  const toReplace = [];
  let n;
  while ((n = walker.nextNode())) {
    re.lastIndex = 0;
    const text = n.textContent;
    const frag = document.createDocumentFragment();
    let lastIdx = 0;
    let m;
    while ((m = re.exec(text)) !== null) {
      if (m.index > lastIdx) frag.appendChild(document.createTextNode(text.slice(lastIdx, m.index)));
      const strong = document.createElement('strong');
      strong.textContent = m[0];
      frag.appendChild(strong);
      lastIdx = m.index + m[0].length;
    }
    if (lastIdx < text.length) frag.appendChild(document.createTextNode(text.slice(lastIdx)));
    toReplace.push([n, frag]);
  }

  for (const [node, frag] of toReplace) {
    node.parentNode.replaceChild(frag, node);
  }
}

/* 只在本地开发服务器上启用"想要"按钮 */
function isLocalhost() {
  return location.hostname === 'localhost' || location.hostname === '127.0.0.1';
}

/* 渲染"想要此页面"按钮 HTML + 绑定点击事件（异步注入）。
 * 仅在 localhost 下注入；远程部署时返回空字符串。 */
function injectWantButton(pid) {
  if (!isLocalhost()) return;
  const btn = document.createElement('button');
  btn.className = 'want-btn';
  btn.textContent = '⭐ 想要此页面';
  btn.title = '标记此页面待改进';
  btn.addEventListener('click', async () => {
    btn.disabled = true;
    btn.textContent = '提交中…';
    try {
      const res = await fetch('/api/want?page=' + encodeURIComponent(pid));
      const data = await res.json();
      if (data.added) {
        btn.textContent = '✅ 已加入队列';
        btn.classList.add('want-btn--done');
      } else {
        btn.textContent = '已在队列中';
        btn.classList.add('want-btn--exists');
      }
    } catch (e) {
      btn.textContent = '❌ 提交失败';
      btn.disabled = false;
    }
  });
  const article = document.getElementById('article');
  if (article) article.appendChild(btn);
}

function buildPager(current, total) {
  const mk = (n, label, cls = '') =>
    n === current
      ? `<span class="pager-current">${label}</span>`
      : `<a class="pager-link${cls ? ' ' + cls : ''}" href="#${encodeURIComponent('Special:Recent')}?page=${n}">${label}</a>`;
  const parts = [];
  if (current > 1) parts.push(mk(current - 1, '← 上一页', 'prev'));
  // 页码数字 (window of 5)
  const lo = Math.max(1, current - 2);
  const hi = Math.min(total, current + 2);
  if (lo > 1) parts.push(mk(1, '1'));
  if (lo > 2) parts.push('<span class="pager-gap">…</span>');
  for (let i = lo; i <= hi; i++) parts.push(mk(i, String(i)));
  if (hi < total - 1) parts.push('<span class="pager-gap">…</span>');
  if (hi < total) parts.push(mk(total, String(total)));
  if (current < total) parts.push(mk(current + 1, '下一页 →', 'next'));
  return `<nav class="pager">${parts.join(' ')}</nav>`;
}


/* 右侧栏图像区. 支持两种格式：
   单图: frontmatter image / image_caption / image_credit
   多图: frontmatter images: [{file, caption, credit}, ...] */
function renderSidebarPortrait(front) {
  const el = document.getElementById('sidebar-portrait');
  if (!el) return;

  // 统一成图片条目数组
  let items = [];
  if (Array.isArray(front.images) && front.images.length) {
    items = front.images.map(img => ({
      src:     img.file    || img.src || '',
      caption: img.caption || '',
      credit:  img.credit  || '',
    }));
  } else if (front.image) {
    items = [{
      src:     front.image,
      caption: front.image_caption || '',
      credit:  front.image_credit  || '',
    }];
  }

  if (!items.length) { el.hidden = true; el.innerHTML = ''; return; }

  el.hidden = false;
  el.innerHTML = items.map((img, i) => `
    <div class="portrait-item${i > 0 ? ' portrait-item--sep' : ''}">
      <a href="${escapeHtml(img.src)}" target="_blank" rel="noopener" class="portrait-zoom" title="点击放大">
        <img src="${escapeHtml(img.src)}"
             alt="${escapeHtml(img.caption || front.label || '')}"
             loading="lazy"
             onerror="this.closest('.portrait-item').style.display='none'">
      </a>
      ${img.caption ? `<figcaption>${escapeHtml(img.caption)}${img.credit ? `<br><span class="credit">${escapeHtml(img.credit)}</span>` : ''}</figcaption>` : ''}
    </div>`).join('');
}

function renderSidebarMap(front) {
  const el = document.getElementById('sidebar-map');
  if (!el) return;

  const coords = front.coords;
  if (!Array.isArray(coords) || coords.length < 2) {
    el.hidden = true; el.innerHTML = '';
    return;
  }

  const [lon, lat] = coords;
  const name = front.coords_name || front.label || '';
  const source = front.coords_source ? `<span class="map-source">${escapeHtml(front.coords_source)}</span>` : '';
  const delta = 0.4;
  const bbox = `${lon - delta},${lat - delta},${lon + delta},${lat + delta}`;
  const osmEmbed = `https://www.openstreetmap.org/export/embed.html?bbox=${bbox}&layer=mapnik&marker=${lat},${lon}`;

  el.hidden = false;
  el.innerHTML = `
    <iframe
      src="${osmEmbed}"
      style="width:100%;height:180px;border:none;display:block;"
      loading="lazy"
      title="${escapeHtml(name)}地图"
      referrerpolicy="no-referrer">
    </iframe>
    <div class="map-caption">${escapeHtml(name)}${source}</div>`;
}

function hideSidebar() {
  const sidebar = document.getElementById('sidebar');
  if (sidebar) sidebar.hidden = true;
  const ib = document.getElementById('infobox');
  if (ib) { ib.hidden = true; ib.innerHTML = ''; }
  const portrait = document.getElementById('sidebar-portrait');
  if (portrait) { portrait.hidden = true; portrait.innerHTML = ''; }
  const mapEl = document.getElementById('sidebar-map');
  if (mapEl) { mapEl.hidden = true; mapEl.innerHTML = ''; }
  const toc = document.getElementById('toc-sidebar');
  if (toc) { toc.hidden = true; toc.innerHTML = ''; }
}

/**
 * 从 #article 中提取 h2/h3 生成左侧可折叠章节目录。
 * 同时为每个标题赋予 id（供定位锚用）。
 */
function buildPageToc(core, pid) {
  const article = document.getElementById('article');
  if (!article) return;
  const toc = document.getElementById('toc-sidebar');
  if (!toc) return;

  const headings = article.querySelectorAll('h2, h3');
  if (headings.length === 0) {
    toc.hidden = true;
    toc.innerHTML = '';
    // 清除残留的折叠按钮
    const oldToggle = article.querySelector('.toc-toggle');
    if (oldToggle) oldToggle.remove();
    return;
  }

  // 为标题生成唯一 ID 并收集条目
  // 使用 § 前缀区分页内锚点与页面名称，避免路由混淆
  const seen = new Set();
  const entries = [];
  headings.forEach(h => {
    const text = h.textContent.trim();
    let id = text.replace(/\s+/g, '-')
      .replace(/[^\w一-鿿　-鿿-]/g, '')
      .substring(0, 60);
    if (!id) id = 'heading';
    let n = 0;
    let uid = id;
    while (seen.has(uid)) { n++; uid = id + '-' + n; }
    seen.add(uid);
    h.id = '§' + uid;
    entries.push({ level: h.tagName === 'H2' ? 2 : 3, id: h.id, text });
  });

  // 构建树：h2 为根，h3 挂载到前一个 h2 下
  const tree = [];
  let stack = null;
  for (const e of entries) {
    if (e.level === 2) {
      stack = { id: e.id, text: e.text, children: [] };
      tree.push(stack);
    } else if (e.level === 3 && stack) {
      stack.children.push({ id: e.id, text: e.text });
    }
  }

  // 生成链接：目录条目始终链接到页内锚点（§前缀ID），不跳转到同名页面
  const html = tree.map(entry => {
    const href = `#${encodeURIComponent(entry.id)}`;
    const link = `<a href="${href}">${escapeHtml(entry.text)}</a>`;
    if (entry.children.length === 0) {
      return `<div class="toc-h2">${link}</div>`;
    }
    return `<details class="toc-section" open>
      <summary>${link}</summary>
      <div class="toc-children">
        ${entry.children.map(c => {
          const ch = `#${encodeURIComponent(c.id)}`;
          return `<div class="toc-h3"><a href="${ch}">${escapeHtml(c.text)}</a></div>`;
        }).join('')}
      </div>
    </details>`;
  }).join('');

  toc.innerHTML = html;
  toc.hidden = false;

  // 添加 TOC 折叠按钮（置于 h1 内）
  const h1 = article.querySelector('h1');
  let toggle = article.querySelector('.toc-toggle');
  if (!toggle && h1) {
    toggle = document.createElement('span');
    toggle.className = 'toc-toggle';
    toggle.title = '章节目录';
    toggle.role = 'button';
    toggle.tabIndex = 0;
    toggle.textContent = '☰';
    h1.insertBefore(toggle, h1.firstChild);
  }

  // 折叠按钮点击切换 TOC 显示
  if (toggle) {
    toggle.onclick = (e) => {
      e.preventDefault();
      document.body.classList.toggle('toc-collapsed');
    };
  }

  // 移除旧的点击监听器，防止累积
  if (toc._tocClick) {
    toc.removeEventListener('click', toc._tocClick);
  }

  toc._tocClick = (e) => {
    const link = e.target.closest('a[href^="#"]');
    if (!link) return;
    // 目录链接始终是页内 §前缀锚点 → 平滑滚动
    const hash = decodeURIComponent(link.getAttribute('href').slice(1));
    const el = document.getElementById(hash);
    if (el) {
      e.preventDefault();
      el.scrollIntoView({ behavior: 'smooth', block: 'start' });
    }
  };
  toc.addEventListener('click', toc._tocClick);
}

function fmtTimestamp(iso) {
  // ISO → "2026-04-22 16:10" (本地时区)
  try {
    const d = new Date(iso);
    const pad = (n) => String(n).padStart(2, '0');
    return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())} ` +
      `${pad(d.getHours())}:${pad(d.getMinutes())}`;
  } catch { return iso; }
}

// 将事件页中 **主要人物**：XXX、YYY 和 **地点**：ZZZ 的纯文本转为 wikilink
const LINKIFY_FIELDS = new Set(['主要人物', '地点']);

function linkifyEventFields(articleEl, registry) {
  articleEl.querySelectorAll('strong').forEach(strong => {
    const label = strong.textContent.trim();
    if (!LINKIFY_FIELDS.has(label)) return;
    // 紧跟在 <strong> 后面的文本节点，形如 "：name1、name2"
    const textNode = strong.nextSibling;
    if (!textNode || textNode.nodeType !== Node.TEXT_NODE) return;
    const text = textNode.textContent;
    const sep = text[0];
    if (sep !== '：' && sep !== ':') return;
    const rest = text.slice(1).trim();
    if (!rest) return;

    // 分割：以 、或 ，分隔，保留分隔符样式
    const parts = rest.split(/([、，])/);
    const fragment = document.createDocumentFragment();
    fragment.appendChild(document.createTextNode(sep));
    for (const part of parts) {
      if (part === '、' || part === '，') {
        fragment.appendChild(document.createTextNode(part));
        continue;
      }
      const name = part.trim();
      if (!name) continue;
      const resolved = resolvePageId(name, registry);
      const a = document.createElement('a');
      a.href = `#${encodeURIComponent(resolved ? resolved[0] : name)}`;
      a.className = resolved ? 'wikilink resolved' : 'wikilink broken';
      if (!resolved) a.title = `未解析: ${name}`;
      a.textContent = name;
      fragment.appendChild(a);
    }
    textNode.replaceWith(fragment);
  });
}

export async function renderPage(core, pid, meta, mdText) {
  document.body.classList.remove('is-home');
  const { front, html, broken } = await parseMarkdown(core, mdText, { pid, meta });

  const tagsFooter = renderTagsFooter(front, meta);
  const articleEl = document.getElementById('article');
  articleEl.innerHTML = html + tagsFooter;
  articleEl.dataset.type = front.type || '';

  linkifyEventFields(articleEl, core.registry);

  // 章节页增强：对话高亮、诗词检测（必须在 boldPageTermsInDOM 之前运行）
  if (meta.type === 'chapter') {
    highlightDialog(articleEl);
    detectPoemsInChapter(articleEl);
    indentDialogueContinuation(articleEl);
  }

  // 加粗：当前页名 + 别名在正文中加粗（DOM 级，避免与 markdown-it html:false 冲突）
  const pageTerms = [pid, front.label || meta?.label, ...(front.aliases || [])].filter(Boolean).map(String);
  boldPageTermsInDOM(articleEl, pageTerms);
  const infoboxContent = await renderInfobox(core, front, meta, pid);
  const ibEl = document.getElementById('infobox');
  const sidebarEl = document.getElementById('sidebar');
  if (infoboxContent) {
    const expandedInfobox = core.pnCitation ? core.pnCitation.expand(infoboxContent) : infoboxContent;
    ibEl.innerHTML = expandedInfobox;
    ibEl.hidden = false;
  } else {
    ibEl.innerHTML = '';
    ibEl.hidden = true;
  }
  renderSidebarPortrait(front);
  renderSidebarMap(front);
  const portraitEl = document.getElementById('sidebar-portrait');
  const mapEl = document.getElementById('sidebar-map');
  sidebarEl.hidden = ibEl.hidden && (!portraitEl || portraitEl.hidden) && (!mapEl || mapEl.hidden);

  const label = front.label || meta.label;
  const qBadge = QUALITY_BADGE[front.quality || meta.quality]
    ? `<span class="page-quality page-quality-${front.quality || meta.quality}">${QUALITY_BADGE[front.quality || meta.quality]}</span>`
    : '';
  const qScore = (front.quality_score || meta.quality_score) != null
    ? `<span class="page-quality-score">Q=${front.quality_score || meta.quality_score}</span>`
    : '';
  document.getElementById('crumb').innerHTML =
    (TYPE_LABELS[meta.type] || meta.type) + ' / ' + escapeHtml(label) + ' ' + qBadge + qScore;
  document.title = label + ' · 资治通鉴 Wiki';

  // 如果正文没有 h1，自动从 label 生成一个
  const article = document.getElementById('article');
  if (!article.querySelector('h1')) {
    const h1 = document.createElement('h1');
    h1.textContent = label;
    article.insertBefore(h1, article.firstChild);
  }

  // 源码查看链接 —— 在标题右侧注入，点击进入专用源码页
  const srcHref = `#?source=${encodeURIComponent(pid)}`;
  const h1 = article.querySelector('h1');
  if (h1) {
    const existing = h1.querySelector('.src-tab');
    if (existing) existing.remove();
    const existingOrig = h1.querySelector('.orig-tab');
    if (existingOrig) existingOrig.remove();
    const tab = document.createElement('a');
    tab.href = srcHref;
    tab.className = 'src-tab';
    tab.textContent = '查看源码';
    h1.appendChild(tab);
    const histTab = document.createElement('a');
    histTab.href = `#?history=${encodeURIComponent(pid)}`;
    histTab.className = 'src-tab hist-tab';
    histTab.textContent = '修订历史';
    h1.appendChild(histTab);
  }
  // footer 保留原始文件链接（开发用）
  const srcSpan = document.getElementById('src-info');
  srcSpan.innerHTML = `<a href="${escapeHtml(meta.path)}" class="src-link" target="_blank">源文件: ${escapeHtml(meta.path)}</a>`;
  // 清除残留 panel
  const srcPanel = document.getElementById('src-panel');
  if (srcPanel) srcPanel.remove();

  const brokenInfo = document.getElementById('broken-info');
  if (broken.length) {
    const uniq = [...new Set(broken)].sort();
    brokenInfo.innerHTML = ` · 断链 ${uniq.length}：` +
      uniq.map((b) => `<code>${escapeHtml(b)}</code>`).join(' ');
  } else {
    brokenInfo.textContent = '';
  }


  // 章节页：注入前后章导航
  if (meta.type === 'chapter') {
    injectChapterNav(core, pid, meta);
  }

  buildPageToc(core, pid);

  // 阅读进度条（所有页面）
  setupReadingProgress();

  window.scrollTo(0, 0);
}

function injectChapterNav(core, pid, meta) {
  const pages = core.registry.pages;
  const book = meta.book;
  // 同书所有章节，按 book_seq 排序
  const siblings = Object.entries(pages)
    .filter(([, m]) => m.type === 'chapter' && m.book === book)
    .sort(([, a], [, b]) => (a.book_seq || 0) - (b.book_seq || 0));

  const idx = siblings.findIndex(([id]) => id === pid);
  const prev = idx > 0 ? siblings[idx - 1] : null;
  const next = idx >= 0 && idx < siblings.length - 1 ? siblings[idx + 1] : null;

  const bookFirstId = siblings[0]?.[0];
  const bookLabel = book || '资治通鉴';

  const prevHtml = prev
    ? `<a class="chapnav-prev" href="#${encodeURIComponent(prev[0])}">← ${escapeHtml(prev[1].label)}</a>`
    : `<span class="chapnav-prev chapnav-disabled">← 已是第一章</span>`;
  const nextHtml = next
    ? `<a class="chapnav-next" href="#${encodeURIComponent(next[0])}">${escapeHtml(next[1].label)} →</a>`
    : `<span class="chapnav-next chapnav-disabled">已是最后一章 →</span>`;
  const tocHtml = `<a class="chapnav-toc" href="#${encodeURIComponent(bookLabel + '目录')}">↑ ${escapeHtml(bookLabel)}目录</a>`;

  const nav = document.createElement('nav');
  nav.className = 'chapnav';
  nav.innerHTML = prevHtml + tocHtml + nextHtml;

  const article = document.getElementById('article');
  // 顶部插在 h1 后面
  const h1 = article.querySelector('h1');
  if (h1) h1.after(nav.cloneNode(true));
  // 底部追加
  article.appendChild(nav);
}

export async function renderSource(core, pid, meta) {
  document.body.classList.remove('is-home');
  const r = await fetch(`pages/${pid}.md`);
  if (!r.ok) throw new Error('HTTP ' + r.status);
  const mdText = await r.text();

  const label = meta.label || pid;
  document.getElementById('crumb').textContent = '源码 / ' + label;
  document.title = label + ' 源码 · 资治通鉴 Wiki';

  document.getElementById('article').innerHTML = `
    <h1 class="src-view-title">${escapeHtml(label)} <span class="src-view-badge">源码</span></h1>
    <p class="muted"><a href="#${encodeURIComponent(pid)}">← 返回阅读页</a></p>
    <pre class="src-pre">${escapeHtml(mdText)}</pre>
  `;
  hideSidebar();
  document.getElementById('src-info').textContent = '';
  document.getElementById('broken-info').textContent = '';
  window.scrollTo(0, 0);
}

// 字段名 → 中文标签（仅用于改善显示，未收录的字段直接用 key 显示）
const FIELD_LABELS = {
  event_type: '事件类型', date: '日期', location: '地点', description: '描述',
  sources: '来源', event_ids: '事件编号', essay_type: '散文类型',
  author: '作者', chapter_no: '章节', canonical_name: '规范名',
  aliases: '别名', birth_ce: '生', death_ce: '卒', tags: '标签',
  pn: '原文位置',
  gender: '性别', books: '出没书册', seealso: '参见',
  birthday: '生日',
  father: '父亲', mother: '母亲', spouse: '配偶',
  siblings: '兄弟姐妹', cousins: '堂表亲', grandparents: '祖父母',
  uncles: '叔伯', nephews: '侄子', nieces: '侄女',
  children: '子女', residence: '居所', occupation: '身份',
  master: '主人', servants: '仆从',
  fate: '结局',
  date: '时间', location: '地点', participants: '参与人物', result: '结果',
  region: '所属', modern_name: '今地名', place_type: '地点类型',
  author: '作者', genre: '体裁', context: '创作场景',
  owner: '所属者', material: '材质', object_type: '器物类型',
  food_type: '饮食类型', occasion: '场合',
  house: '堂号', members: '成员',
  concept_type: '概念类型',
  era: '时代', dynasty: '朝代', cat: '人物类别',
};

// 纯内部字段，不对用户展示
const INFOBOX_SKIP = new Set([
  'id', 'label', 'title', 'type', 'featured', 'auto_generated',
  'quality_score', 'path', 'paragraph_refs', 'quality',
  // 图片由 sidebar-portrait 渲染，无需在 infobox 表格里重复显示
  'image', 'image_caption', 'image_credit', 'image_prompt', 'images',
]);

/* 将 infobox 字段值转为 wikilink（若该值有对应页面）。 */
function linkifyValue(val, registry) {
  const s = String(val);
  if (!registry) return escapeHtml(s);
  const resolved = resolvePageId(s, registry);
  if (resolved) {
    return `<a href="#${encodeURIComponent(resolved[0])}">${escapeHtml(s)}</a>`;
  }
  return escapeHtml(s);
}

/* 字段分组：按性质排序 infobox 字段 */
const FIELD_GROUPS = [
  { label: '基本', fields: ['gender', 'description'] },
  { label: '家族', fields: ['father', 'mother', 'spouse', 'siblings', 'cousins', 'grandparents', 'uncles', 'aunts', 'nephews', 'nieces', 'children'] },
  { label: '生平', fields: ['birthday', 'era', 'dynasty', 'cat'] },
  { label: '主仆', fields: ['master', 'servants'] },
  { label: '关联', fields: ['seealso', 'location', 'residence', 'occupation', 'pn'] },
];
/* 分组合并，用于快速查找字段归属 */
const FIELD_IN_GROUP = new Map();
for (const g of FIELD_GROUPS) for (const k of g.fields) FIELD_IN_GROUP.set(k, g.label);

export async function renderInfobox(core, front, meta, pid) {
  let rows = [];
  const handled = new Set();
  const push = (k, v) => {
    if (v != null && v !== '') {
      rows.push(`<tr><th>${escapeHtml(k)}</th><td>${v}</td></tr>`);
    }
  };

  // ── 特殊字段（先于分组处理）──
  if (front.canonical_name && front.canonical_name !== (front.label || meta.label)) {
    push('规范名', escapeHtml(front.canonical_name));
  }
  handled.add('canonical_name');

  if (front.aliases && front.aliases.length) {
    push('别名', front.aliases.map(a => {
      const escaped = escapeHtml(a);
      if (a !== pid && core.registry.pages[a]) {
        return `<a href="#${encodeURIComponent(a)}">${escaped}</a>`;
      }
      return escaped;
    }).join(' · '));
  }
  handled.add('aliases');

  push('类型', TYPE_LABELS[front.type || meta.type] || front.type || meta.type);
  handled.add('type');

  if (front.tags && front.tags.length) {
    push('标签', front.tags.map(t => linkifyValue(t, core.registry)).join(' · '));
  }
  handled.add('tags');

  if (front.birth_ce != null) {
    const bce = front.birth_ce < 0 ? `公元前 ${-front.birth_ce} 年` : `公元 ${front.birth_ce} 年`;
    push('生', bce);
  }
  handled.add('birth_ce');

  if (front.death_ce != null) {
    const dce = front.death_ce < 0 ? `公元前 ${-front.death_ce} 年` : `公元 ${front.death_ce} 年`;
    push('卒', dce);
  }
  handled.add('death_ce');

  // "出没书册" 几乎都是红楼梦，infobox 中无展示必要
  handled.add('books');

  // ── 分组字段（按 FIELD_GROUPS 顺序）──
  for (const group of FIELD_GROUPS) {
    const hasContent = group.fields.some(k => {
      if (handled.has(k)) return false;
      const val = front[k];
      return val != null && val !== '';
    });
    if (!hasContent) continue;

    rows.push(`<tr class="infobox-group"><th colspan="2">${escapeHtml(group.label)}</th></tr>`);

    for (const key of group.fields) {
      handled.add(key);
      const val = front[key];
      if (val == null || val === '') continue;
      const label = FIELD_LABELS[key] || key;

      if (key === 'gender') {
        const genderLabels = { male: '男', female: '女', other: '其他' };
        push(label, genderLabels[String(val)] || escapeHtml(String(val)));
      } else if (key === 'birthday') {
        const CN_MONTH = ['', '正', '二', '三', '四', '五', '六', '七', '八', '九', '十', '十一', '十二'];
        const CN_DAY = ['', '初一', '初二', '初三', '初四', '初五', '初六', '初七', '初八', '初九', '初十',
          '十一', '十二', '十三', '十四', '十五', '十六', '十七', '十八', '十九', '二十',
          '廿一', '廿二', '廿三', '廿四', '廿五', '廿六', '廿七', '廿八', '廿九', '三十'];
        const m = String(val).match(/^(\d{1,2})-(\d{1,2})$/);
        if (m) {
          const mi = parseInt(m[1]), di = parseInt(m[2]);
          push(label, `${CN_MONTH[mi] || mi}月${CN_DAY[di] || di}`);
        } else {
          push(label, escapeHtml(String(val)));
        }
      } else if (key === 'pn') {
        // 半角括号转全角，供 pn-citation 插件展开为链接
        const s = String(val).trim().replace(/\(/g, '（').replace(/\)/g, '）');
        push(label, s);
      } else if (Array.isArray(val)) {
        push(label, val.map(v => linkifyValue(v, core.registry)).join(' · '));
      } else {
        push(label, linkifyValue(val, core.registry));
      }
    }
  }

  // ── 剩余未分组字段（兜底）──
  for (const [key, val] of Object.entries(front)) {
    if (handled.has(key) || INFOBOX_SKIP.has(key)) continue;
    if (val == null || val === '') continue;
    const label = FIELD_LABELS[key] || key;
    if (Array.isArray(val)) {
      if (val.length) {
        push(label, val.map(v => linkifyValue(v, core.registry)).join(' · '));
      }
    } else if (typeof val === 'object') {
      // 嵌套对象跳过
    } else {
      push(label, linkifyValue(val, core.registry));
    }
  }

  // ── Hook ──
  rows = await core.hooks.onInfobox.run(rows, front, meta);

  if (!rows.length) return null;
  return `<h2>${escapeHtml(front.label || meta.label)}</h2>
    <table>${rows.join('')}</table>`;
}

const BOOK_META = [
  { key: '鉴', label: '资治通鉴', subtitle: '294卷 · 纵贯1362年', min: 1, max: 294 },
];

function buildHomeSvg() {
  return `<img class="hero-cosmos" src="images/guoguo-spring.jpg" alt="虢国夫人游春图 · 张萱 · 唐代">
<div class="hero-gradient"></div>
<div class="hero-seal" role="img" aria-label="通鉴之印">
  <svg viewBox="0 0 100 100" width="100" height="100">
    <rect x="2" y="2" width="96" height="96" fill="none" stroke="#c04a30" stroke-width="3" rx="4"/>
    <rect x="8" y="8" width="84" height="84" fill="none" stroke="#c04a30" stroke-width="1.5" rx="2"/>
    <text x="50" y="42" text-anchor="middle" font-size="24" font-weight="700"
      fill="#c04a30" font-family="serif" letter-spacing="4">通</text>
    <text x="50" y="72" text-anchor="middle" font-size="24" font-weight="700"
      fill="#c04a30" font-family="serif" letter-spacing="4">鉴</text>
  </svg>
  <div class="seal-tip">虢国夫人游春图 · 张萱 · 唐代</div>
</div>`;
}


export function renderHeroShell() {
  const article = document.getElementById('article');
  article.dataset.type = '';
  article.innerHTML = `<div class="wiki-home">
    <div class="home-hero">
      ${buildHomeSvg()}
      <div class="hero-overlay">
        <div class="hero-eyebrow">北宋 · 司马光 · 历史百科</div>
        <h1 class="hero-title">资治通鉴</h1>
        <div class="hero-tagline">司马光著 · 纵贯十六朝 1362 年 · <span class="hero-count"></span></div>
        <div class="hero-search">
          <input id="wiki-search" type="search"
            placeholder="搜索词条（如「曹操」「赤壁之战」「武则天」）"
            autocomplete="off" autofocus>
          <div class="search-mode-toggle">
            <label class="mode-opt">
              <input type="checkbox" id="fts-toggle"> 全文检索
            </label>
          </div>
          <ul id="search-results" hidden></ul>
        </div>
      </div>
    </div>
    <div class="home-body"></div>
  </div>`;

  document.body.classList.add('is-home');
  hideSidebar();
  document.getElementById('crumb').textContent = '首页';
  document.title = '资治通鉴 Wiki — 司马光百科';
}

function bindHomeSearch(core) {
  const input = document.getElementById('wiki-search');
  if (!input) return;
  const resultsEl = document.getElementById('search-results');
  if (!resultsEl) return;
  const ftsToggle = document.getElementById('fts-toggle');

  ftsToggle.addEventListener('change', () => {
    input.placeholder = ftsToggle.checked
      ? '搜索原文（如「鉴于往事」「贞观之治」「永怀英贤」）'
      : '搜索词条（如「曹操」「赤壁之战」「武则天」）';
    if (input.value.trim()) {
      const ev = new Event('input');
      input.dispatchEvent(ev);
    }
  });

  input.addEventListener('input', () => {
    const q = input.value.trim();
    if (!q) {
      resultsEl.hidden = true; resultsEl.innerHTML = ''; return;
    }

    if (ftsToggle.checked) {
      loadFTSIndex().then(index => {
        const hits = searchFTS(q, index);
        resultsEl.hidden = false;
        if (hits.length === 0) {
          resultsEl.innerHTML =
            `<li class="search-empty">原文中没有匹配: "${escapeHtml(q)}"</li>`;
          return;
        }
        const ftsHtml = hits.slice(0, 30).map(h => {
          const chapLabel = '第' + String(h.chapterN).padStart(3,'0') + '回';
          const snippet = makeFTSSnippet(h.text, q);
          const chapName = escapeHtml(h.chapterTitle.replace(/[　 ]+/g, ' '));
          return `<li class="search-result-item fts-item">
            <a href="#${encodeURIComponent(h.chapterId)}?pn=${h.paraId}">
              <span class="fts-chap">${chapLabel}</span>
              <span class="fts-pn">${h.paraId}</span>
              <span class="fts-snip">${snippet}</span>
              <span class="fts-title">${chapName}</span>
            </a>
          </li>`;
        }).join('');
        const moreLink = hits.length > 30
          ? `<li class="search-result-item fts-all"><a href="search.html?q=${encodeURIComponent(q)}">查看全部 ${hits.length} 个结果 →</a></li>`
          : '';
        resultsEl.innerHTML = ftsHtml + moreLink;
      });
      return;
    }

    const matches = searchPages(q, core.registry);
    resultsEl.hidden = false;
    if (matches.length === 0) {
      resultsEl.innerHTML =
        `<li class="search-empty">没有匹配: "${escapeHtml(q)}"</li>`;
      return;
    }
    resultsEl.innerHTML = matches.map((m) => {
      const labelHtml = escapeHtml(m.entry.label);
      const altHtml = m.matched !== m.entry.label
        ? `<span class="match-alt">[${escapeHtml(m.matched)}]</span>` : '';
      const meta = m.entry.total_refs != null
        ? `<span class="match-meta">${m.entry.total_refs} 次 / ${m.entry.total_chapters} 篇</span>`
        : '';
      return `<li class="search-result-item">
        <a href="#${encodeURIComponent(m.pid)}">
          <span class="match-label">${labelHtml}</span>${altHtml}${meta}
        </a>
      </li>`;
    }).join('');
  });
  input.addEventListener('keydown', (e) => {
    if (e.key === 'Enter') {
      if (ftsToggle.checked) {
        const q = input.value.trim();
        if (q) window.location.href = 'search.html?q=' + encodeURIComponent(q);
        return;
      }
      const first = resultsEl.querySelector('a');
      if (first) location.hash = first.getAttribute('href').slice(1);
    } else if (e.key === 'Escape') {
      input.value = ''; resultsEl.hidden = true; resultsEl.innerHTML = '';
    }
  });
}

function buildHomeBodyHtml(bookCardsHtml, sections, totalPages) {
  const sectionHtml = sections.map(s => {
    if (!s.cardsHtml) return '';
    const headerHtml = s.subtitle
      ? `<span class="home-section-sub">${escapeHtml(s.subtitle)}</span>`
      : '';
    return `<div class="home-section-header${s.minor ? ' home-section-header--minor' : ''}">
        <h2 class="home-section-title">${escapeHtml(s.title)}</h2>
        ${headerHtml}
      </div>
      <div class="featured-grid">${s.cardsHtml}</div>`;
  }).join('');
  return `<div class="home-volumes">${bookCardsHtml}</div>
    ${sectionHtml}
    <nav class="home-links">
      <a href="#${encodeURIComponent('Special:AllPages')}" class="home-link">全部 ${totalPages} 页 →</a>
      <a href="#${encodeURIComponent('Special:Recent')}" class="home-link">最近修订 →</a>
      <a href="#${encodeURIComponent('Special:Random')}" class="home-link">随机词条 →</a>
    </nav>
    <p class="home-disclaimer">本 Wiki 内容由 AI 整理，基于北宋司马光《资治通鉴》294卷，纵贯战国至五代十国 1362 年史事。如发现错误欢迎<a href="https://github.com/baojie/tongjian/issues/new" target="_blank" rel="noopener">提交 Issue</a>。</p>`;
}

function buildFullHomeHtml(entityCount, bookCardsHtml, sections, totalPages) {
  return `<div class="wiki-home">
    <div class="home-hero">
      ${buildHomeSvg()}
      <div class="hero-overlay">
        <div class="hero-eyebrow">北宋 · 司马光 · 历史百科</div>
        <h1 class="hero-title">资治通鉴</h1>
        <div class="hero-tagline">司马光著 · 纵贯十六朝 1362 年 · <span class="hero-count">${entityCount} 个词条</span></div>
        <div class="hero-search">
          <input id="wiki-search" type="search"
            placeholder="搜索词条（如「曹操」「赤壁之战」「武则天」）"
            autocomplete="off" autofocus>
          <div class="search-mode-toggle">
            <label class="mode-opt">
              <input type="checkbox" id="fts-toggle"> 全文检索
            </label>
          </div>
          <ul id="search-results" hidden></ul>
        </div>
      </div>
    </div>
    <div class="home-body">
      ${buildHomeBodyHtml(bookCardsHtml, sections, totalPages)}
    </div>
  </div>`;

}

/**
 * 诗词检测：在章节页中找到 3+ 连续短行段落或含 \n 的韵文段落，标记为诗词。
 *   — 3+ 连续短行（≤50 字）→ 传统诗词块
 *   — 单个段落正文含 \n → 韵文（将 \n 替换为 <br> 渲染）
 */
function detectPoemsInChapter(articleEl) {
  const paragraphs = articleEl.querySelectorAll('p[id^="pn-"]');
  if (paragraphs.length < 3) return;

  const bodyText = (p) => {
    const label = p.querySelector('.pn-label');
    return label
      ? p.textContent.replace(label.textContent, '').trim()
      : p.textContent.trim();
  };

  // --- 模式 1：3+ 连续短行 ---
  const SHORT = 50;
  const runs = [];
  let start = -1;

  for (let i = 0; i < paragraphs.length; i++) {
    const text = bodyText(paragraphs[i]);
    const len = text.length;
    if (len >= 3 && len <= SHORT) {
      if (start === -1) start = i;
    } else {
      if (start >= 0 && i - start >= 3) runs.push([start, i]);
      start = -1;
    }
  }
  if (start >= 0 && paragraphs.length - start >= 3) runs.push([start, paragraphs.length]);

  for (const [s, e] of runs) {
    // 排除历史散文：若 ≥65% 的行以句号结尾，是独立陈述句（继位/薨殁/年号等），非诗词
    // 真正的诗词行末交替出现 ，和 。，句号占比通常 ≤50%
    const runLen = e - s;
    const periodCount = Array.from({ length: runLen }, (_, i) => bodyText(paragraphs[s + i]))
      .filter(t => t.endsWith('。')).length;
    if (periodCount / runLen >= 0.65) continue;

    for (let j = s; j < e; j++) {
      const text = bodyText(paragraphs[j]);
      if (text.endsWith('：')) continue;
      paragraphs[j].classList.add('chapter-poem');
      if (text.length <= 25) {
        paragraphs[j].classList.add('chapter-poem-short');
      }
    }
  }

  // --- 模式 2：含 \n 的韵文段落（如好了歌） ---
  // 需排除模式 1 已标记的段落，避免重复处理
  for (const p of paragraphs) {
    if (p.classList.contains('chapter-poem')) continue;
    const text = bodyText(p);
    if (!text.includes('\n')) continue;

    p.classList.add('chapter-poem');
    // 判断每行长度：全部 ≤25 则为居中短行
    const lines = text.split('\n');
    if (lines.every(l => l.length <= 25)) {
      p.classList.add('chapter-poem-short');
    }
    // 将 \n 替换为 <br>（在 innerHTML 上操作以保留 wikilink 等标签）
    p.innerHTML = p.innerHTML.replace(/\n/g, '<br>');
  }
}

/**
 * 对话高亮：将章节正文中 「」 括住的内容包裹 .dialog-text span。
 * 按段落处理 innerHTML，正确处理跨 wikilink 标签的情况。
 */
function highlightDialog(articleEl) {
  const paragraphs = articleEl.querySelectorAll('p');
  for (const p of paragraphs) {
    if (!p.innerHTML.includes('「')) continue;

    let html = p.innerHTML;
    let result = '';
    let depth = 0;
    let last = 0;

    for (let i = 0; i < html.length; i++) {
      if (html[i] === '「') {
        if (depth === 0) {
          result += html.slice(last, i);
          last = i;
        }
        depth++;
      } else if (html[i] === '」') {
        if (depth > 0) depth--;
        if (depth === 0) {
          result += '「<span class="dialog-text">' + html.slice(last + 1, i) + '</span>」';
          last = i + 1;
        }
      }
    }
    if (last < html.length) result += html.slice(last);

    if (result !== html) p.innerHTML = result;
  }
}

/**
 * 对话续段缩进：跟踪「」深度，同一对话拆成多段后，
 * 第二段起自动缩进两个汉字宽度（前端渲染，不修改原文）。
 */
function indentDialogueContinuation(articleEl) {
  const paras = articleEl.querySelectorAll('p');
  let depth = 0;
  for (const p of paras) {
    const text = p.textContent || '';
    const hasPN = /^\s*\[\d+-\d+\]/.test(text);
    // 每个 PN 段落独立追踪深度，避免跨段泄漏
    if (hasPN) depth = 0;
    const hasQuote = text.includes('「');
    // 前一段有未闭合引号、本段无「且无 PN 标记 → 对话续段
    if (depth > 0 && !hasQuote && !hasPN) p.classList.add('dialogue-cont');
    for (const ch of text) {
      if (ch === '「') depth++;
      if (ch === '」') depth = Math.max(0, depth - 1);
    }
  }
}

/**
 * 阅读进度条：固定到页面顶部，随滚动更新宽度。
 */
let _progressBar = null;
function setupReadingProgress() {
  if (!_progressBar) {
    _progressBar = document.createElement('div');
    _progressBar.className = 'reading-progress';
    _progressBar.id = 'reading-progress';
    document.body.prepend(_progressBar);
  }

  const update = () => {
    if (document.body.classList.contains('is-home')) {
      _progressBar.style.width = '0%';
      return;
    }
    const scrollTop = window.scrollY;
    const docHeight = document.documentElement.scrollHeight - window.innerHeight;
    const progress = docHeight > 0 ? Math.min(scrollTop / docHeight * 100, 100) : 0;
    _progressBar.style.width = progress + '%';
  };

  if (!_progressBar._bound) {
    window.addEventListener('scroll', update, { passive: true });
    _progressBar._bound = true;
  }
  update();
}

export async function renderHome(core) {
  // 首页精选卡片需要 featured/quality 等全量字段，等待完整注册表加载完成
  if (!core.registry._fullLoaded && core.fullRegistryReady) {
    await core.fullRegistryReady;
  }
  const pages = core.registry.pages;
  const ids = Object.keys(pages);

  // 固定头三张：三部书卡片
  const bookCardsHtml = BOOK_META.map((meta) =>
    renderBookCard(meta, pages)
  ).join('');

  // 实体词条卡片：featured 优先，其次按 quality 降序；chapter 不上首页
  const allPages = ids.map(id => ({ id, ...pages[id] }));
  const scoreOf = p => (QUALITY_RANK[p.quality] || 0) + (p.quality_score || 0) + (p.featured ? 500 : 0);
  const entityCandidates = allPages
    .filter(p => !['redirect','disambiguation','special','chapter','overview'].includes(p.type||''))
    .filter(p => p.featured || (p.quality || 'stub') !== 'stub')
    .sort((a, b) => scoreOf(b) - scoreOf(a));

  // 按类型分组展示
  const topFeatured = entityCandidates.filter(p => p.featured || p.quality === 'premium');
  const normalCards = entityCandidates.filter(p => !p.featured && p.quality !== 'premium');

  const sections = [];
  if (topFeatured.length) {
    sections.push({
      title: '精选词条',
      subtitle: '历史人物 · 重大战役 · 关键事件 · 典章制度',
      cardsHtml: topFeatured.map(renderFeaturedCard).join('')
    });
  }

  const personCards = normalCards.filter(p => p.type === 'person');
  const eventCards = normalCards.filter(p => ['event','battle'].includes(p.type));
  const conceptCards = normalCards.filter(p => ['concept','place','state','organization'].includes(p.type));
  const otherCards = normalCards.filter(p => !['person','event','battle','concept','place','state','organization'].includes(p.type));

  if (personCards.length) sections.push({ title: '人物', subtitle: null, cardsHtml: personCards.slice(0, 12).map(renderFeaturedCard).join(''), minor: true });
  if (eventCards.length) sections.push({ title: '事件与战役', subtitle: null, cardsHtml: eventCards.slice(0, 12).map(renderFeaturedCard).join(''), minor: true });
  if (conceptCards.length) sections.push({ title: '制度与概念', subtitle: null, cardsHtml: conceptCards.slice(0, 12).map(renderFeaturedCard).join(''), minor: true });
  if (otherCards.length) sections.push({ title: '其他', subtitle: null, cardsHtml: otherCards.slice(0, 8).map(renderFeaturedCard).join(''), minor: true });

  const entityCount = allPages.filter(p =>
    !['redirect','disambiguation','special','chapter'].includes(p.type||'')).length;

  const article = document.getElementById('article');
  const existingBody = article.querySelector('.wiki-home > .home-body');
  const hasHero = article.querySelector('.home-hero');

  if (existingBody && hasHero) {
    // 增量更新：英雄区已在 renderHeroShell 中预渲染
    const countEl = article.querySelector('.hero-count');
    if (countEl) countEl.textContent = `${entityCount} 个词条`;
    existingBody.innerHTML = buildHomeBodyHtml(bookCardsHtml, sections, ids.length);
  } else {
    // 完整渲染（直接导航到首页，无预渲染英雄区）
    article.innerHTML = buildFullHomeHtml(entityCount, bookCardsHtml, sections, ids.length);
    document.body.classList.add('is-home');
    hideSidebar();
    document.getElementById('crumb').textContent = '首页';
    document.title = '资治通鉴 Wiki — 司马光百科';
  }

  document.getElementById('src-info').textContent = 'pages.json';
  document.getElementById('broken-info').textContent = '';

  bindHomeSearch(core);
}

/**
 * 每页底部分类标签 (语义化):
 *   <footer class="entity-tags" role="contentinfo">
 *     <a class="tag tag-type" rel="tag">人名</a>
 *     <a class="tag" rel="tag">汉朝</a>...
 *   </footer>
 *
 * 来源:
 *   - type (frontmatter.type 或 meta.type): 主分类, 显示为突出样式
 *   - tags[]: 自由标签
 *
 * rel="tag" 是 HTML5 microformats 的标签链接关系, 搜索引擎和
 * 阅读器可识别. href 指向 "#?tag=<name>"; 未来可加 tag 路由.
 */
function renderTagsFooter(front, meta) {
  const type = front.type || meta.type || '';
  const typeLabel = TYPE_LABELS[type] || type;
  const tags = front.tags || [];
  const hasType = !!typeLabel;
  const hasTags = tags.length > 0;
  if (!hasType && !hasTags) return '';

  let html = '<footer class="entity-tags" role="contentinfo">';
  if (hasType) {
    html += '<span class="tag-label">分类</span> ' +
      `<a class="tag tag-type" rel="tag" data-kind="type"` +
      ` href="#?type=${encodeURIComponent(type)}">${escapeHtml(typeLabel)}</a>`;
  }
  if (hasTags) {
    if (hasType) html += '<br>';
    html += '<span class="tag-label">标签</span> ' +
      tags.map(t =>
        `<a class="tag" rel="tag" data-kind="tag"` +
        ` href="#?tag=${encodeURIComponent(t)}">${escapeHtml(t)}</a>`
      ).join(' ');
  }
  html += '</footer>';
  return html;
}

function renderBookCard({ key, label, subtitle, min, max }, pages) {
  const chapNum = id => parseInt(id.replace(/\D/g,'')) || 0;
  const chapters = Object.entries(pages)
    .filter(([id, m]) => m.type === 'chapter' && chapNum(id) >= min && chapNum(id) <= max)
    .sort(([ia], [ib]) => chapNum(ia) - chapNum(ib));
  const firstId = chapters.length > 0 ? chapters[0][0] : null;
  const href = firstId ? `#${encodeURIComponent(firstId)}` : '#';
  const chapListHtml = chapters.slice(0, 30).map(([id, m]) => {
    const n = chapNum(id);
    const tip = m.description ? m.description.replace(/^第\d+卷：?/,'') : '';
    return `<a class="bc-chap" href="#${encodeURIComponent(id)}" title="${escapeHtml(tip)}">第${n}卷</a>`;
  }).join('');
  const moreHtml = chapters.length > 30
    ? `<span class="bc-more">+${chapters.length - 30}</span>` : '';
  const tocHref = '#' + encodeURIComponent('资治通鉴目录');
  return `<div class="featured-card book-card">
    <a class="bc-stretch-link" href="${tocHref}" aria-label="${escapeHtml(label)}目录"></a>
    <a class="bc-numeral" href="${tocHref}"><span>${key}</span></a>
    <div class="bc-body">
      <div class="bc-head">
        <a class="bc-title" href="${tocHref}">${escapeHtml(label)}</a>
        <span class="bc-sub">${escapeHtml(subtitle)}</span>
      </div>
      <div class="bc-chapters">${chapListHtml}${moreHtml}</div>
    </div>
  </div>`;
}

function renderFeaturedCard(p) {
  const typeLabel = TYPE_LABELS[p.type] || p.type || '';
  const qualityClass = p.quality ? ` card-q-${p.quality}` : '';
  const typeClass = p.type ? ` card-t-${p.type}` : '';
  const eyebrow = typeLabel
    ? `<div class="card-eyebrow">${escapeHtml(typeLabel)}</div>` : '';
  const descHtml = p.description
    ? `<div class="card-desc">${escapeHtml(p.description)}</div>` : '';
  const imgHtml = p.image
    ? `<div class="card-thumb"><img src="${escapeHtml(p.image)}" alt="${escapeHtml(p.label)}" loading="lazy"></div>` : '';
  const headerHtml = `<div class="card-header">
    <h3>${escapeHtml(p.label)}</h3>
    ${eyebrow}
  </div>`;
  return `<a class="featured-card entity-card${qualityClass}${typeClass}" href="#${encodeURIComponent(p.id)}">
    ${imgHtml}${headerHtml}${descHtml}
  </a>`;
}

function searchPages(q, registry) {
  const lower = q.toLowerCase();
  // type priority: core entities first, long-form content last
  const TYPE_PRIO = { person: 40, character: 40, civilization: 35,
    law: 35, concept: 30, technology: 25, weapon: 25,
    organization: 20, event: 20, time: 20, place: 15,
    animal: 15, plant: 15,
    book: 10, chapter: 8, quote: 7, overview: 5, list: 5,
    redirect: -20 };

  function matchScore(surface) {
    const s = surface.toLowerCase();
    if (s === lower)            return 100;
    if (s.startsWith(lower))   return 70;
    if (s.includes(lower))     return 30;
    return 0;
  }

  // pid → { surface, score }
  const best = new Map();
  function tryMatch(pid, surface) {
    const sc = matchScore(surface);
    if (!sc) return;
    const prev = best.get(pid);
    if (!prev || sc > prev.score) best.set(pid, { surface, score: sc });
  }

  for (const [pid, entry] of Object.entries(registry.pages)) {
    tryMatch(pid, pid);
    if (entry.label) tryMatch(pid, entry.label);
  }
  for (const [alias, pid] of Object.entries(registry.alias_index || {})) {
    tryMatch(pid, alias);
  }

  return [...best.entries()]
    .map(([pid, { surface, score }]) => {
      const entry = registry.pages[pid];
      const typePrio = TYPE_PRIO[entry?.type] ?? 10;
      const refs = entry?.total_refs ?? 0;
      return { pid, entry, matched: surface, _sort: score * 100 + typePrio * 10 + Math.min(refs, 9) };
    })
    .sort((a, b) => b._sort - a._sort)
    .slice(0, 15)
    .map(({ pid, entry, matched }) => ({ pid, entry, matched }));
}

/* ───── 全文检索 (FTS) ───── */

let ftsIndexPromise = null;
function loadFTSIndex() {
  if (!ftsIndexPromise) {
    ftsIndexPromise = fetch('data/fts-index.json').then(r => r.json());
  }
  return ftsIndexPromise;
}

function searchFTS(q, index) {
  const lower = q.toLowerCase();
  const terms = lower.split(/\s+/).filter(Boolean);
  if (!terms.length) return [];

  const results = [];
  for (const entry of index.entries) {
    const text = entry.x.toLowerCase();
    let allMatch = true;
    let firstPos = -1;
    for (const t of terms) {
      const pos = text.indexOf(t);
      if (pos === -1) { allMatch = false; break; }
      if (firstPos === -1 || pos < firstPos) firstPos = pos;
    }
    if (!allMatch) continue;

    const chap = index.chapters[entry.c];
    results.push({
      chapterN: chap.n,
      chapterId: chap.f,
      chapterTitle: chap.t,
      paraId: entry.p,
      text: entry.x,
      score: firstPos
    });
  }

  results.sort((a, b) => a.score - b.score);
  return results.slice(0, 30);
}

function makeFTSSnippet(text, query, radius) {
  if (radius === undefined) radius = 32;
  const lower = text.toLowerCase();
  const qLower = query.toLowerCase();
  const pos = lower.indexOf(qLower);
  if (pos === -1) {
    return escapeHtml(text.slice(0, 100)) + (text.length > 100 ? '…' : '');
  }
  const start = Math.max(0, pos - radius);
  const end = Math.min(text.length, pos + qLower.length + radius);
  let s = '';
  if (start > 0) s += '…';
  s += escapeHtml(text.slice(start, pos));
  s += '<mark class="fts-hl">' + escapeHtml(text.slice(pos, pos + qLower.length)) + '</mark>';
  s += escapeHtml(text.slice(pos + qLower.length, end));
  if (end < text.length) s += '…';
  return s;
}

/**
 * 分类页 (类 MediaWiki Category): 列出某 type/tag 下的所有页面.
 *   URL: #?type=<type>  或  #?tag=<tag>
 */
export function renderCategory(core, kind, value) {
  const pages = core.registry.pages;
  const matches = [];
  for (const [pid, entry] of Object.entries(pages)) {
    if (kind === 'type' && entry.type === value) {
      matches.push({ pid, ...entry });
    } else if (kind === 'tag' && (entry.tags || []).includes(value)) {
      matches.push({ pid, ...entry });
    }
  }
  // refs 降序, 无 refs 按 id
  matches.sort((a, b) => {
    const ra = a.total_refs || 0, rb = b.total_refs || 0;
    if (ra !== rb) return rb - ra;
    return a.pid.localeCompare(b.pid, 'zh');
  });

  const titleKind = kind === 'type' ? '类型' : '标签';
  const displayValue = kind === 'type'
    ? (TYPE_LABELS[value] || value) : value;

  const itemsHtml = matches.map((p) => {
    const firstChar = p.label ? p.label[0] : '';
    const life = p.lifespan;
    let lifeS = '';
    if (life && life.birth != null && life.death != null) {
      const b = life.birth < 0 ? `前 ${-life.birth}` : String(life.birth);
      const d = life.death < 0 ? `前 ${-life.death}` : String(life.death);
      lifeS = `<span class="cat-life">${b}—${d}</span>`;
    }
    const meta = p.total_refs != null
      ? `<span class="cat-meta">${p.total_refs} 次 / ${p.total_chapters} 篇</span>` : '';
    return `<li data-alpha="${getPinyinInitial(p.label)}">
      <a href="#${encodeURIComponent(p.pid)}" class="cat-link">${escapeHtml(p.label)}</a>
      ${lifeS}${meta}
    </li>`;
  }).join('');

  // 超过 100 项时附加 A-Z 过滤栏
  const filterBar = matches.length > 100
    ? buildFirstCharBarHtml(matches.map(p => p.label || p.pid))
    : '';

  const body = matches.length > 0
    ? `<div class="category-filterable">${filterBar}<ol class="category-list">${itemsHtml}</ol></div>`
    : '<p class="category-empty">此分类下暂无页面。</p>';

  document.getElementById('article').innerHTML =
    `<nav class="category-crumb"><a href="#">← 首页</a></nav>
     <h1>${escapeHtml(titleKind)}：${escapeHtml(displayValue)}</h1>
     <p class="category-summary">共 <strong>${matches.length}</strong> 个页面</p>
     ${body}`;

  // A: 绑定首字过滤
  const filterable = document.querySelector('.category-filterable');
  if (filterable) setupFirstCharFilter(filterable);

  document.body.classList.add('is-home');
  hideSidebar();
  document.getElementById('crumb').textContent = `${titleKind}：${displayValue}`;
  document.title = `${titleKind} ${displayValue} · 资治通鉴 Wiki`;
  document.getElementById('src-info').textContent =
    `pages.json (筛选: ${kind}=${value})`;
  document.getElementById('broken-info').textContent = '';
  window.scrollTo(0, 0);
}

/**
 * 最近修订页 (#?recent[&page=N]):
 * 读取 recent.lite.jsonl（不含 diff，轻量），无需加载庞大的 diff 数据。
 */
export async function renderRecent(core, pageNum = 1) {
  const DISPLAY_LIMIT = 500;
  const PAGE_SIZE = 50;

  const bust = `?v=${Math.floor(Date.now() / 60000)}`;
  const r = await fetch('recent.lite.jsonl' + bust);
  if (!r.ok) throw new Error('HTTP ' + r.status);
  const text = await r.text();

  // 解析 JSONL：过滤空行，每行一条修订记录
  const allEntries = text.split('\n')
    .filter(l => l.trim())
    .map(l => JSON.parse(l));

  // 取最新 DISPLAY_LIMIT 条，逆序显示（最新在前）
  const recent500 = allEntries.slice(-DISPLAY_LIMIT).reverse();

  const totalEntries = recent500.length;
  const totalPages = Math.max(1, Math.ceil(totalEntries / PAGE_SIZE));
  pageNum = Math.min(Math.max(1, pageNum), totalPages);

  const start = (pageNum - 1) * PAGE_SIZE;
  const entries = recent500.slice(start, start + PAGE_SIZE);

  const rows = entries.map((e) => {
    const pageLink = `<a href="#${encodeURIComponent(e.page)}">${escapeHtml(e.page)}</a>`;
    const histLink = `<a href="#?history=${encodeURIComponent(e.page)}">历史</a>`;
    const revLink = `<a href="#?revision=${encodeURIComponent(e.page)}&rev=${encodeURIComponent(e.rev_id)}">${escapeHtml(e.rev_id)}</a>`;
    const diffLink = `<a href="#?diff=${encodeURIComponent(e.page)}&rev=${encodeURIComponent(e.rev_id)}">diff</a>`;
    const added   = e.diff_add ?? null;
    const removed = e.diff_del ?? null;
    let sizeHtml;
    if (added === null) {
      sizeHtml = `<td class="rc-size rc-size-zero">—</td>`;
    } else if (added > 0 && removed === 0) {
      sizeHtml = `<td class="rc-size rc-size-plus">+${added}</td>`;
    } else if (added === 0 && removed > 0) {
      sizeHtml = `<td class="rc-size rc-size-minus">−${removed}</td>`;
    } else if (added > 0 && removed > 0) {
      sizeHtml = `<td class="rc-size rc-size-mixed"><span class="rc-plus">+${added}</span> <span class="rc-minus">−${removed}</span></td>`;
    } else {
      sizeHtml = `<td class="rc-size rc-size-zero">±0</td>`;
    }
    return `<tr>
      <td class="rc-time">${escapeHtml(fmtTimestamp(e.timestamp))}</td>
      <td class="rc-page">${pageLink}</td>
      <td class="rc-author">${escapeHtml(e.author)}</td>
      ${sizeHtml}
      <td class="rc-summary">${escapeHtml(e.summary || '')}</td>
      <td class="rc-rev">${revLink} · ${diffLink} · ${histLink}</td>
    </tr>`;
  }).join('');

  const pagerHtml = totalPages > 1 ? buildPager(pageNum, totalPages) : '';

  const uniquePages = new Set(recent500.map(e => e.page)).size;
  const logNote = allEntries.length > DISPLAY_LIMIT
    ? `（共 ${allEntries.length} 条，显示最新 ${DISPLAY_LIMIT} 条）` : '';

  const body = entries.length === 0
    ? '<p class="category-empty">暂无修订记录。</p>'
    : `<table class="recent-changes">
        <thead><tr><th>时间</th><th>页面</th><th>作者</th><th>大小</th><th>摘要</th><th>修订</th></tr></thead>
        <tbody>${rows}</tbody>
      </table>
      ${pagerHtml}`;

  document.getElementById('article').innerHTML =
    `<nav class="category-crumb"><a href="#">← 首页</a></nav>
     <h1>最近修订 <small class="muted">第 ${pageNum}/${totalPages} 页</small></h1>
     <p class="category-summary">显示 <strong>${totalEntries}</strong> 条修订 · <strong>${uniquePages}</strong> 个页面 ${escapeHtml(logNote)}</p>
     ${body}`;

  document.body.classList.add('is-home');
  hideSidebar();
  document.getElementById('crumb').textContent = '最近修订';
  document.title = '最近修订 · 资治通鉴 Wiki';
  document.getElementById('src-info').textContent = 'recent.lite.jsonl';
  document.getElementById('broken-info').textContent = '';
  window.scrollTo(0, 0);
}

/**
 * 单页修订历史 (#?history=<page>): 读 docs/wiki/history/<page>.jsonl.
 */
export async function renderHistory(core, page) {
  const r = await fetch(`history/${encodeURIComponent(page)}.jsonl`);
  if (!r.ok) throw new Error('HTTP ' + r.status);
  const text = await r.text();
  const revs = text.split('\n').filter(l => l.trim()).map(l => JSON.parse(l)).reverse(); // 反转：最新在前
  const latestRevId = revs.length ? revs[0].rev_id : '';
  const revisionCount = revs.length;

  const rows = revs.map((rev, idx) => {
    const isLatest = rev.rev_id === latestRevId;
    const tag = isLatest ? ' <span class="rev-badge">最新</span>' : '';
    const revLink = `<a href="#?revision=${encodeURIComponent(page)}&rev=${encodeURIComponent(rev.rev_id)}">${escapeHtml(rev.rev_id)}</a>`;
    const diffLink = rev.parent_rev
      ? `<a href="#?diff=${encodeURIComponent(page)}&rev=${encodeURIComponent(rev.rev_id)}">diff</a>`
      : '<span class="muted">diff</span>';
    const hLines = rev.content ? rev.content.split('\n').length : '—';
    const hadd = rev.diff ? rev.diff.filter(d => d[0] === '+').length : null;
    const hrem = rev.diff ? rev.diff.filter(d => d[0] === '-').length : null;
    let hChangeHtml;
    if (hadd === null) {
      hChangeHtml = `<td class="rc-size rc-size-zero">—</td>`;
    } else if (hadd > 0 && hrem === 0) {
      hChangeHtml = `<td class="rc-size rc-size-plus">+${hadd}</td>`;
    } else if (hadd === 0 && hrem > 0) {
      hChangeHtml = `<td class="rc-size rc-size-minus">−${hrem}</td>`;
    } else if (hadd > 0 && hrem > 0) {
      hChangeHtml = `<td class="rc-size rc-size-mixed"><span class="rc-plus">+${hadd}</span> <span class="rc-minus">−${hrem}</span></td>`;
    } else {
      hChangeHtml = `<td class="rc-size rc-size-zero">±0</td>`;
    }
    let hSizeHtml = `<td class="rc-size">${hLines}</td>`;
    return `<tr>
      <td class="rc-time">${escapeHtml(fmtTimestamp(rev.timestamp))}${tag}</td>
      <td class="rc-author">${escapeHtml(rev.author)}</td>
      <td class="rc-summary">${escapeHtml(rev.summary || '')}</td>
      ${hSizeHtml}
      ${hChangeHtml}
      <td class="rc-diff">${diffLink}</td>
      <td class="rc-rev">${revLink}${tag}</td>
    </tr>`;
  }).join('');

  document.getElementById('article').innerHTML =
    `<nav class="category-crumb">
       <a href="#">← 首页</a> ·
       <a href="#${encodeURIComponent(page)}">← ${escapeHtml(page)}</a>
     </nav>
     <h1>${escapeHtml(page)} · 修订历史</h1>
     <p class="category-summary">共 <strong>${revisionCount}</strong> 条修订</p>
     <table class="recent-changes">
       <thead><tr><th>时间</th><th>作者</th><th>摘要</th><th>行数</th><th>变化</th><th>diff</th><th>修订</th></tr></thead>
       <tbody>${rows}</tbody>
     </table>`;

  document.body.classList.add('is-home');
  hideSidebar();
  document.getElementById('crumb').textContent = `修订历史 / ${page}`;
  document.title = `${page} 修订历史 · 资治通鉴 Wiki`;
  document.getElementById('src-info').textContent = `history/${page}.jsonl`;
  document.getElementById('broken-info').textContent = '';
  window.scrollTo(0, 0);
}

/**
 * 单条历史版本 (#?revision=<page>&rev=<id>): 从 history/<page>.jsonl 的
 * 各行 content 中提取内容 (user-req-6 内联存储后). 历史数据在单文件里.
 */
export async function renderRevision(core, page, revId) {
  const r = await fetch(`history/${encodeURIComponent(page)}.jsonl`);
  if (!r.ok) throw new Error('HTTP ' + r.status);
  const text = await r.text();
  const revs = text.split('\n').filter(l => l.trim()).map(l => JSON.parse(l));
  const rev = revs.find((x) => x.rev_id === revId);
  if (!rev) throw new Error(`rev not found: ${revId}`);
  if (rev.content == null) throw new Error(`rev missing content: ${revId}`);
  const mdText = rev.content;

  const meta = (core.registry.pages[page]) || { type: 'meta', label: page, path: '' };
  const { html } = await parseMarkdown(core, mdText, { pid: page, meta });

  const banner = `<div class="rev-banner">
    <strong>历史版本</strong> · 修订 <code>${escapeHtml(revId)}</code> ·
    <a href="#${encodeURIComponent(page)}">→ 当前版本</a> ·
    <a href="#?history=${encodeURIComponent(page)}">→ 全部修订</a> ·
    <a href="#?diff=${encodeURIComponent(page)}&rev=${encodeURIComponent(revId)}">→ vs 上版 diff</a>
  </div>`;

  document.getElementById('article').innerHTML = banner + html;
  hideSidebar();
  document.body.classList.add('is-home');
  document.getElementById('crumb').textContent = `${page} @ ${revId}`;
  document.title = `${page} @ ${revId} · 资治通鉴 Wiki`;
  document.getElementById('src-info').textContent = `history/${page}/${revId}.md`;
  document.getElementById('broken-info').textContent = '';
  window.scrollTo(0, 0);
}

/**
/* 从 label 列表提取唯一首字，返回过滤栏 HTML（首字 ≤ 3 个时不生成）。*/
/* 拼音首字母映射表（覆盖史记人名常用首字） */
const PINYIN_INITIAL = {
  B: '伯卜扁比白百薄褒鲍',
  C: '城崔春晁曹曾楚樗淳程蔡触鉏陈',
  D: '丁东帝杜段澹窦翟董邓',
  E: '二',
  F: '冯夫扶樊肥范',
  G: '公勾灌甘盖管葛虢郭高',
  H: '侯后壶扈桓汉浑淮狐胡衡闳霍韩黄',
  J: '介剧姬季晋景汲箕荆贾蹇鞠',
  K: '孔括蒯',
  L: '乐刘卢吕娄嫪廉李栗栾梁老落蔺路郦酈里陆骊鲁龙',
  M: '冒孟枚毛缪蒙闵',
  N: '南宁聂',
  P: '平庞彭辟',
  Q: '屈戚秦骑齐',
  R: '任穰',
  S: '叔司商姒孙宋审慎桑申石示苏随',
  T: '唐太屠田缇',
  W: '伍卫吴文王魏',
  X: '侠信先夏宣弦徐新荀萧西许郤项须',
  Y: '严义伊优原夷尧晏杨燕由羊英虞袁豫颜',
  Z: '专中主仲召周子宰州庄张智朱章臧赵邹郅郑钟长',
};

function getPinyinInitial(label) {
  const ch = label && label[0];
  if (!ch) return '#';
  for (const [letter, chars] of Object.entries(PINYIN_INITIAL)) {
    if (chars.includes(ch)) return letter;
  }
  return '#';
}

function buildFirstCharBarHtml(labels) {
  const used = new Set(labels.map(l => getPinyinInitial(l)).filter(c => c !== '#'));
  const ordered = 'ABCDEFGHIJKLMNOPQRSTUVWXYZ'.split('').filter(l => used.has(l));
  if (ordered.length <= 2) return '';
  const btns = ['全', ...ordered].map((c, i) =>
    `<button class="firstchar-btn${i === 0 ? ' active' : ''}" data-char="${c}">${c}</button>`
  ).join('');
  return `<div class="firstchar-bar" role="group" aria-label="按拼音首字母过滤">${btns}</div>`;
}

function setupFirstCharFilter(container) {
  const bar = container.querySelector('.firstchar-bar');
  if (!bar) return;
  bar.addEventListener('click', e => {
    const btn = e.target.closest('.firstchar-btn');
    if (!btn) return;
    const ch = btn.dataset.char;
    bar.querySelectorAll('.firstchar-btn').forEach(b => b.classList.toggle('active', b === btn));
    container.querySelectorAll('li[data-alpha]').forEach(li => {
      li.hidden = ch !== '全' && li.dataset.alpha !== ch;
    });
  });
}

/**
 * Special:AllPages — 分面浏览器
 * 左侧分面（类型 / 出场书册 / 标签 / 质量），右侧分页结果列表，顶部文字搜索。
 */
export function renderAll(core) {
  const pages = core.registry.pages;

  // ── 构建全局分面数据 ─────────────────────────────────────────────
  const allEntries = Object.entries(pages)
    .filter(([id]) => !id.startsWith('Special:'))
    .map(([id, p]) => ({ id, ...p }));

  const typeCounts    = {};
  const tagCounts     = {};
  const bookCounts    = {};
  const qualityCounts = {};

  for (const p of allEntries) {
    const t = p.type || 'unknown';
    typeCounts[t] = (typeCounts[t] || 0) + 1;
    for (const tag of (p.tags || [])) tagCounts[tag] = (tagCounts[tag] || 0) + 1;
    for (const bk of (p.books || [])) bookCounts[bk] = (bookCounts[bk] || 0) + 1;
    const q = p.quality || 'stub';
    qualityCounts[q] = (qualityCounts[q] || 0) + 1;
  }

  // 出场书册：固定顺序
  const BOOK_ORDER = ['资治通鉴'];
  const orderedBooks = BOOK_ORDER.filter(b => bookCounts[b]);

  // 标签：出现 ≥ 3 次
  const topTags = Object.entries(tagCounts)
    .filter(([, c]) => c >= 3)
    .sort((a, b) => b[1] - a[1])
    .slice(0, 30)
    .map(([t]) => t);

  // 类型：按条数降序
  const orderedTypes = Object.keys(typeCounts).sort(
    (a, b) => typeCounts[b] - typeCounts[a]
  );

  // ── URL 状态 ──────────────────────────────────────────────────────
  function getState() {
    const hash = decodeURIComponent(location.hash.slice(1));
    const qi   = hash.indexOf('?');
    const p    = new URLSearchParams(qi >= 0 ? hash.slice(qi + 1) : '');
    return {
      types:  p.getAll('type'),
      books:  p.getAll('book'),
      tags:   p.getAll('tag'),
      qlevel: p.get('q') || '',
      search: p.get('s') || '',
      page:   Math.max(1, parseInt(p.get('page') || '1', 10)),
    };
  }

  function buildHash(s) {
    const p = new URLSearchParams();
    s.types.forEach(t  => p.append('type', t));
    s.books.forEach(b  => p.append('book', b));
    s.tags.forEach(t   => p.append('tag',  t));
    if (s.qlevel) p.set('q', s.qlevel);
    if (s.search) p.set('s', s.search);
    if (s.page > 1) p.set('page', String(s.page));
    const qs = p.toString();
    return '#' + encodeURIComponent('Special:AllPages') + (qs ? '?' + qs : '');
  }

  // ── 过滤 + 排序 ───────────────────────────────────────────────────
  const PAGE_SIZE = 50;

  function applyFilters(s) {
    let r = allEntries;
    if (s.types.length) r = r.filter(p => s.types.includes(p.type || 'unknown'));
    if (s.books.length) r = r.filter(p => s.books.some(b => (p.books || []).includes(b)));
    if (s.tags.length)  r = r.filter(p => s.tags.every(t => (p.tags || []).includes(t)));
    if (s.qlevel)       r = r.filter(p => (p.quality || 'stub') === s.qlevel);
    if (s.search) {
      const kw = s.search.toLowerCase();
      r = r.filter(p =>
        p.id.toLowerCase().includes(kw) ||
        (p.label || '').toLowerCase().includes(kw) ||
        (p.aliases || []).some(a => a.toLowerCase().includes(kw))
      );
    }
    return r.slice().sort((a, b) =>
      (b.quality_score || 0) - (a.quality_score || 0) ||
      (a.label || a.id).localeCompare(b.label || b.id, 'zh')
    );
  }

  // ── 分面栏 ────────────────────────────────────────────────────────
  function renderFacets(s) {
    const typeItems = orderedTypes.map(t => {
      const active = s.types.includes(t);
      return `<label class="facet-item${active ? ' active' : ''}">
        <input type="checkbox" data-facet="type" data-val="${escapeHtml(t)}"${active ? ' checked' : ''}>
        <span class="facet-label">${escapeHtml(TYPE_LABELS[t] || t)}</span>
        <span class="facet-count">${typeCounts[t]}</span>
      </label>`;
    }).join('');

    const bookItems = orderedBooks.map(b => {
      const active = s.books.includes(b);
      return `<label class="facet-item${active ? ' active' : ''}">
        <input type="checkbox" data-facet="book" data-val="${escapeHtml(b)}"${active ? ' checked' : ''}>
        <span class="facet-label">${escapeHtml(b)}</span>
        <span class="facet-count">${bookCounts[b]}</span>
      </label>`;
    }).join('');

    const tagItems = topTags.map(tag => {
      const active = s.tags.includes(tag);
      return `<label class="facet-item${active ? ' active' : ''}">
        <input type="checkbox" data-facet="tag" data-val="${escapeHtml(tag)}"${active ? ' checked' : ''}>
        <span class="facet-label">${escapeHtml(tag)}</span>
        <span class="facet-count">${tagCounts[tag]}</span>
      </label>`;
    }).join('');

    const QUALITY_LEVELS = [
      ['premium',  '旗舰'],
      ['featured', '精品'],
      ['standard', '标准'],
      ['basic',    '基础'],
      ['stub',     '存根'],
    ];
    const qItems = QUALITY_LEVELS.map(([val, lbl]) =>
      `<label class="facet-item${s.qlevel === val ? ' active' : ''}">
        <input type="radio" name="qlevel" data-facet="q" data-val="${val}"${s.qlevel === val ? ' checked' : ''}>
        <span class="facet-label">${lbl}</span>
        <span class="facet-count">${qualityCounts[val] || 0}</span>
      </label>`
    ).join('');

    const bookSection = orderedBooks.length ? `
      <details class="facet-group" open>
        <summary class="facet-group-title">出场书册</summary>
        <div class="facet-items">${bookItems}</div>
      </details>` : '';

    const tagSection = topTags.length ? `
      <details class="facet-group" open>
        <summary class="facet-group-title">标签</summary>
        <div class="facet-items facet-tags">${tagItems}</div>
      </details>` : '';

    return `<aside class="facet-panel">
      <div class="facet-reset-row">
        <strong>筛选</strong>
        <button class="facet-reset-btn" id="facet-reset">清除</button>
      </div>
      <details class="facet-group" open>
        <summary class="facet-group-title">类型</summary>
        <div class="facet-items">${typeItems}</div>
      </details>
      ${bookSection}${tagSection}
      <details class="facet-group">
        <summary class="facet-group-title">内容质量</summary>
        <div class="facet-items">${qItems}</div>
      </details>
    </aside>`;
  }

  // ── 结果列表 ──────────────────────────────────────────────────────
  function renderResults(results, s) {
    const total      = results.length;
    const totalPages = Math.max(1, Math.ceil(total / PAGE_SIZE));
    const page       = Math.min(s.page, totalPages);
    const slice      = results.slice((page - 1) * PAGE_SIZE, page * PAGE_SIZE);

    const items = slice.map(p => {
      const badge = QUALITY_BADGE[p.quality]
        ? `<span class="res-quality res-quality-${p.quality}">${QUALITY_BADGE[p.quality]}</span>` : '';
      const score = p.quality_score != null
        ? `<span class="res-score">Q=${p.quality_score}</span>` : '';
      const booksHtml = (p.books || []).map(b =>
        `<span class="res-tag">${escapeHtml(b)}</span>`).join('');
      const desc = p.description
        ? `<div class="res-desc">${escapeHtml(p.description)}</div>` : '';
      return `<li class="res-item">
        <a class="res-title" href="#${encodeURIComponent(p.id)}">${escapeHtml(p.label || p.id)}</a>
        ${desc}
        <div class="res-meta">
          <span class="res-type">${escapeHtml(TYPE_LABELS[p.type] || p.type || '')}</span>
          ${badge}${score}${booksHtml}
        </div>
      </li>`;
    }).join('');

    let pagerHtml = '';
    if (totalPages > 1) {
      const mkLink = (pg, label) =>
        `<a class="pager-btn${pg === page ? ' active' : ''}" href="${buildHash({ ...s, page: pg })}">${label}</a>`;
      const prev = page > 1 ? mkLink(page - 1, '←') : '';
      const next = page < totalPages ? mkLink(page + 1, '→') : '';
      const nums = Array.from({ length: totalPages }, (_, i) => i + 1)
        .filter(n => n <= 2 || n >= totalPages - 1 || Math.abs(n - page) <= 2)
        .reduce((acc, n, i, arr) => {
          if (i > 0 && n - arr[i - 1] > 1) acc.push('…');
          acc.push(n); return acc;
        }, [])
        .map(n => typeof n === 'string' ? `<span class="pager-ellipsis">…</span>` : mkLink(n, n))
        .join('');
      pagerHtml = `<div class="pager">${prev}${nums}${next}</div>`;
    }

    const activeFilters = [
      ...s.types.map(t => TYPE_LABELS[t] || t),
      ...s.books,
      ...s.tags,
      ...(s.qlevel ? [s.qlevel] : []),
      ...(s.search ? [`"${s.search}"`] : []),
    ].join(' · ');

    return `<div class="res-header">
        <span class="res-count">共 <strong>${total}</strong> 个页面${activeFilters ? ' · ' + activeFilters : ''}</span>
      </div>
      <ul class="res-list">${items || '<li class="res-empty">无匹配结果</li>'}</ul>
      ${pagerHtml}`;
  }

  // ── 移动端过滤栏 ─────────────────────────────────────────────────
  function renderMobileFilters(s) {
    const typeOptions = [`<option value="">全部类型</option>`]
      .concat(orderedTypes.map(t =>
        `<option value="${escapeHtml(t)}"${s.types[0] === t ? ' selected' : ''}>${escapeHtml(TYPE_LABELS[t] || t)} (${typeCounts[t]})</option>`
      )).join('');
    const bookOptions = [`<option value="">全部书册</option>`]
      .concat(orderedBooks.map(b =>
        `<option value="${escapeHtml(b)}"${s.books[0] === b ? ' selected' : ''}>${escapeHtml(b)} (${bookCounts[b]})</option>`
      )).join('');
    return `
      <div class="ap-mobile-filters">
        <input id="ap-search" class="allpages-search" type="search"
          placeholder="搜索页面名称或别名…" value="${escapeHtml(s.search)}">
        <select id="ap-type-select" class="ap-type-select">${typeOptions}</select>
        <select id="ap-book-select" class="ap-type-select">${bookOptions}</select>
      </div>`;
  }

  // ── 主渲染 ────────────────────────────────────────────────────────
  function render() {
    const s       = getState();
    const results = applyFilters(s);
    const article = document.getElementById('article');
    const isMobile = window.innerWidth < 700;

    if (isMobile) {
      article.innerHTML = `
        <nav class="category-crumb"><a href="#">← 首页</a></nav>
        <h1>全部页面</h1>
        <div class="allpages-mobile">
          ${renderMobileFilters(s)}
          <div id="ap-results">${renderResults(results, s)}</div>
        </div>`;
    } else {
      article.innerHTML = `
        <nav class="category-crumb"><a href="#">← 首页</a></nav>
        <h1>全部页面</h1>
        <div class="allpages-layout">
          ${renderFacets(s)}
          <div class="allpages-main">
            <div class="allpages-search-row">
              <input id="ap-search" class="allpages-search" type="search"
                placeholder="搜索页面名称或别名…" value="${escapeHtml(s.search)}">
            </div>
            <div id="ap-results">${renderResults(results, s)}</div>
          </div>
        </div>`;
    }

    document.body.classList.add('is-home');
    hideSidebar();
    document.getElementById('crumb').textContent = '全部页面';
    document.title = '全部页面 · 资治通鉴 Wiki';
    document.getElementById('src-info').textContent = `共 ${allEntries.length} 页`;
    document.getElementById('broken-info').textContent = '';
    window.scrollTo(0, 0);

    // 搜索框（防抖 200ms）
    let timer;
    article.querySelector('#ap-search').addEventListener('input', e => {
      clearTimeout(timer);
      timer = setTimeout(() => {
        const ns = getState();
        ns.search = e.target.value.trim();
        ns.page = 1;
        history.replaceState(null, '', buildHash(ns));
        document.getElementById('ap-results').innerHTML = renderResults(applyFilters(ns), ns);
      }, 200);
    });

    if (isMobile) {
      article.querySelector('#ap-type-select').addEventListener('change', e => {
        const ns = getState();
        ns.types = e.target.value ? [e.target.value] : [];
        ns.page = 1;
        history.replaceState(null, '', buildHash(ns));
        document.getElementById('ap-results').innerHTML = renderResults(applyFilters(ns), ns);
      });
      article.querySelector('#ap-book-select').addEventListener('change', e => {
        const ns = getState();
        ns.books = e.target.value ? [e.target.value] : [];
        ns.page = 1;
        history.replaceState(null, '', buildHash(ns));
        document.getElementById('ap-results').innerHTML = renderResults(applyFilters(ns), ns);
      });
    } else {
      // 桌面端：分面 checkbox / radio
      article.querySelectorAll('input[data-facet]').forEach(cb => {
        cb.addEventListener('change', () => {
          const ns = getState();
          const { facet, val } = cb.dataset;
          if (facet === 'type') {
            ns.types = cb.checked ? [...new Set([...ns.types, val])] : ns.types.filter(t => t !== val);
          } else if (facet === 'book') {
            ns.books = cb.checked ? [...new Set([...ns.books, val])] : ns.books.filter(b => b !== val);
          } else if (facet === 'tag') {
            ns.tags = cb.checked ? [...new Set([...ns.tags, val])] : ns.tags.filter(t => t !== val);
          } else if (facet === 'q') {
            ns.qlevel = cb.checked ? val : '';
          }
          ns.page = 1;
          history.replaceState(null, '', buildHash(ns));
          document.getElementById('ap-results').innerHTML = renderResults(applyFilters(ns), ns);
          article.querySelectorAll('.facet-item').forEach(lbl => {
            const inp = lbl.querySelector('input');
            lbl.classList.toggle('active', !!(inp && inp.checked));
          });
        });
      });

      article.querySelector('#facet-reset')?.addEventListener('click', () => {
        history.replaceState(null, '', buildHash({ types: [], books: [], tags: [], qlevel: '', search: '', page: 1 }));
        render();
      });
    }
  }

  render();
}


/**
 * 版本 diff 页 (#?diff=<page>&rev=<rev_id>): 显示该版 vs parent_rev 的行级 diff.
 * user-req-8: 每个版本应可看上一个版本的 diff.
 */
export async function renderDiff(core, page, revId) {
  // Try inline diff from recent.diff.jsonl first (lazy-loaded diff store)
  let chunks = null;
  let curMeta = null;
  let source = `recent.diff.jsonl`;
  try {
    const rr = await fetch('recent.diff.jsonl');
    if (rr.ok) {
      const lines = (await rr.text()).split('\n').filter((l) => l.trim());
      for (let i = lines.length - 1; i >= 0; i--) {
        const e = JSON.parse(lines[i]);
        if (e.page === page && e.rev_id === revId) {
          if (e.diff) {
            chunks = e.diff.map(([op, line]) => ({
              type: op === '+' ? 'add' : op === '-' ? 'del' : 'same',
              line,
            }));
          }
          curMeta = e;
          break;
        }
      }
    }
  } catch (_) {}

  // Fall back to history JSONL (older revisions or missing diff field)
  if (!chunks) {
    source = `history/${page}.jsonl`;
    const r = await fetch(`history/${encodeURIComponent(page)}.jsonl`);
    if (!r.ok) throw new Error('HTTP ' + r.status);
    const text = await r.text();
    const revs = text.split('\n').filter(l => l.trim()).map(l => JSON.parse(l));
    const cur = revs.find((x) => x.rev_id === revId);
    if (!cur) throw new Error(`rev not found: ${revId}`);
    curMeta = cur;
    let prevContent = '';
    if (cur.parent_rev) {
      const prevRev = revs.find((x) => x.rev_id === cur.parent_rev);
      if (prevRev) prevContent = prevRev.content || '';
    }
    chunks = computeLineDiff(prevContent, cur.content || '');
  }

  const diffHtml = renderDiffChunks(chunks);

  const header = `<nav class="category-crumb">
    <a href="#${encodeURIComponent(page)}">← ${escapeHtml(page)}</a>
    <span class="sep">·</span>
    <a href="#?history=${encodeURIComponent(page)}">所有修订</a>
    <span class="sep">·</span>
    <a href="#?revision=${encodeURIComponent(page)}&rev=${encodeURIComponent(revId)}">查看该版</a>
  </nav>`;

  const parentInfo = curMeta.parent_rev
    ? `<div><strong>上版:</strong> <code>${escapeHtml(curMeta.parent_rev)}</code></div>`
    : '<div><em>首个版本 (无上版), 全部显示为新增</em></div>';

  const meta = `<div class="diff-meta">
    <div><strong>本版:</strong> <code>${escapeHtml(revId)}</code> · ${escapeHtml(fmtTimestamp(curMeta.timestamp))} · ${escapeHtml(curMeta.author)}</div>
    ${parentInfo}
    <div class="diff-summary">
      <span class="diff-added">+${chunks.filter((c) => c.type === 'add').length}</span>
      ·
      <span class="diff-removed">-${chunks.filter((c) => c.type === 'del').length}</span>
      行 · 摘要: <em>${escapeHtml(curMeta.summary || '(无)')}</em>
    </div>
  </div>`;

  document.getElementById('article').innerHTML = header +
    `<h1>版本差异 <small class="muted">${escapeHtml(page)}</small></h1>` +
    meta + `<div class="diff-body">${diffHtml}</div>`;

  hideSidebar();
  document.body.classList.add('is-home');
  document.getElementById('crumb').textContent = `${page} diff ${revId}`;
  document.title = `${page} diff · 资治通鉴 Wiki`;
  document.getElementById('src-info').textContent = `${source} (diff ${revId} vs ${curMeta.parent_rev || 'null'})`;
  document.getElementById('broken-info').textContent = '';
  window.scrollTo(0, 0);
}

// 行级 LCS-based diff. 返回 [{type: 'same'|'add'|'del', line}, ...] 按新序.
function computeLineDiff(oldText, newText) {
  const o = oldText.split('\n');
  const n = newText.split('\n');
  const m = o.length, nn = n.length;
  // DP
  const dp = Array(m + 1).fill(null).map(() => new Int32Array(nn + 1));
  for (let i = 1; i <= m; i++) {
    for (let j = 1; j <= nn; j++) {
      dp[i][j] = o[i - 1] === n[j - 1]
        ? dp[i - 1][j - 1] + 1
        : Math.max(dp[i - 1][j], dp[i][j - 1]);
    }
  }
  const res = [];
  let i = m, j = nn;
  while (i > 0 && j > 0) {
    if (o[i - 1] === n[j - 1]) { res.push({ type: 'same', line: o[i - 1] }); i--; j--; }
    else if (dp[i - 1][j] >= dp[i][j - 1]) { res.push({ type: 'del', line: o[i - 1] }); i--; }
    else { res.push({ type: 'add', line: n[j - 1] }); j--; }
  }
  while (i > 0) { res.push({ type: 'del', line: o[i - 1] }); i--; }
  while (j > 0) { res.push({ type: 'add', line: n[j - 1] }); j--; }
  return res.reverse();
}

function renderDiffChunks(chunks) {
  return chunks.map((c) => {
    const cls = 'diff-line diff-' + c.type;
    const sign = { same: ' ', add: '+', del: '-' }[c.type];
    return `<div class="${cls}"><span class="diff-sign">${sign}</span><span class="diff-text">${escapeHtml(c.line)}</span></div>`;
  }).join('');
}

export function renderNotFound(core, target) {
  document.getElementById('article').innerHTML =
    `<h1>页面不存在</h1>
     <p>未找到页面 <code>${escapeHtml(target)}</code>。</p>
     <p><a href="#">回到首页</a></p>`;
  hideSidebar();
  document.body.classList.add('is-home');
  document.getElementById('crumb').textContent = '未找到';
  document.title = '未找到 · 资治通鉴 Wiki';
  document.getElementById('src-info').textContent = '';
  document.getElementById('broken-info').textContent = '';
  injectWantButton(target);
}
