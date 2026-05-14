/* 哈希路由。 */

import { resolvePageId } from './registry.js';
import {
  renderPage, renderHome, renderNotFound, renderCategory,
  renderRecent, renderHistory, renderRevision, renderAll, renderDiff,
  renderSource, renderSurname,
} from './renderer.js?v=20260430a';
import { renderSpecialSettings, renderSpecialPlugins, renderSpecialAll, renderSpecialStatistics } from './special.js';
import { setStatus, showFatal, escapeHtml } from './util.js';

export function setupRouter(core) {
  window.addEventListener('hashchange', () => route(core));
  route(core);
}

async function route(core) {
  // 先取原始 hash (未解码), 便于区分 '?query' 和普通 slug
  const rawHash = location.hash.slice(1) || '';

  // 提取 ?pn= 段落导航参数（如 #第074回?pn=074-007）
  let pendingPN = null;
  let cleanHash = rawHash;
  const pnIdx = rawHash.indexOf('?pn=');
  if (pnIdx > 0) {
    const pnVal = rawHash.slice(pnIdx + 4);
    if (/^\d{3}-\d{3}$/.test(pnVal)) {
      pendingPN = 'pn-' + pnVal;
      cleanHash = rawHash.slice(0, pnIdx);
    }
  }

  // 处理 #pageId#anchorId 格式（如 #大观园#主要景点）
  let pendingPageAnchor = null;
  if (cleanHash && !cleanHash.startsWith('?')) {
    const hashSep = cleanHash.indexOf('#');
    if (hashSep > 0) {
      pendingPageAnchor = cleanHash.slice(hashSep + 1);
      cleanHash = cleanHash.slice(0, hashSep);
    }
  }

  // 页内锚点（如脚注 #fn1 / #fnref1）：目标元素已在 DOM 中，直接滚动，不做页面路由
  if (cleanHash && !cleanHash.startsWith('?') && !pendingPageAnchor) {
    // PN 段落已在 DOM 中（同页直链），滚动并返回
    if (pendingPN) {
      const pnEl = document.getElementById(pendingPN);
      if (pnEl) {
        pnEl.scrollIntoView({ behavior: 'smooth', block: 'center' });
        pnEl.classList.add('pn-highlight');
        setTimeout(() => pnEl.classList.remove('pn-highlight'), 2000);
        setStatus('');
        return;
      }
    }
    const el = document.getElementById(decodeURIComponent(cleanHash));
    if (el) {
      const id = decodeURIComponent(cleanHash);
      const isBackref = id.startsWith('fnref');
      const navH = document.querySelector('.topnav')?.offsetHeight ?? 0;
      if (isBackref) {
        const BLOCK = new Set(['P','LI','TD','TH','H1','H2','H3','H4','H5','H6','BLOCKQUOTE','DIV','SECTION']);
        let block = el.parentElement;
        while (block && !BLOCK.has(block.tagName)) block = block.parentElement;
        const target = block || el;
        const top = target.getBoundingClientRect().top + window.scrollY - navH - 8;
        window.scrollTo({ top, behavior: 'smooth' });
      } else {
        el.scrollIntoView({ behavior: 'smooth', block: 'center' });
      }
      setStatus('');
      return;
    } else if (cleanHash.startsWith('§')) {
      setStatus('');
      return;
    }
  }

  setStatus('载入…');

  // 特殊页: #?type=<type> · #?tag=<tag> · #?surname=<surname> · #?recent · #?history=<page> · #?revision=<page>&rev=<id>
  if (rawHash.startsWith('?')) {
    const params = new URLSearchParams(rawHash.slice(1));
    const type = params.get('type');
    const tag = params.get('tag');
    const surname = params.get('surname');
    // 姓氏筛选 → 自定义姓氏列表页
    if (surname) {
      try { await renderSurname(core, surname); }
      catch (e) { showFatal(`姓氏列表渲染失败：${e.message}`); }
      setStatus(''); return;
    }
    // 姓氏索引 → 列所有姓氏及人数
    if (params.has('surnames')) {
      try { await renderSurname(core, null); }
      catch (e) { showFatal(`姓氏索引渲染失败：${e.message}`); }
      setStatus(''); return;
    }
    // 类型/标签筛选 → 分面浏览（#Special:AllPages?type=XX）
    if (type || tag) {
      const p = new URLSearchParams();
      if (type) p.set('type', type);
      if (tag) p.set('tag', tag);
      location.hash = '#' + encodeURIComponent('Special:AllPages') + (p.toString() ? '?' + p.toString() : '');
      setStatus(''); return;
    }
    if (params.has('all')) {
      location.hash = encodeURIComponent('Special:AllPages');
      setStatus(''); return;
    }
    if (params.has('recent')) {
      // 旧 URL 兼容：直接渲染，不做 redirect（避免 hashchange 不触发的问题）
      const pageNum = parseInt(params.get('page') || '1', 10);
      try { await renderRecent(core, pageNum); } catch (e) { showFatal(`recent.lite.jsonl 加载失败：${e.message}`); }
      setStatus(''); return;
    }
    if (params.has('history')) {
      const page = params.get('history');
      try { await renderHistory(core, page); }
      catch (e) { showFatal(`history/${page}.jsonl 加载失败：${e.message}`); }
      setStatus(''); return;
    }
    if (params.has('diff')) {
      const page = params.get('diff');
      const rev = params.get('rev');
      try { await renderDiff(core, page, rev); }
      catch (e) { showFatal(`diff ${page} @ ${rev} 失败：${e.message}`); }
      setStatus(''); return;
    }
    if (params.has('revision')) {
      const page = params.get('revision');
      const rev = params.get('rev');
      try { await renderRevision(core, page, rev); }
      catch (e) { showFatal(`history/${page}.jsonl#${rev} 加载失败：${e.message}`); }
      setStatus(''); return;
    }
    if (params.has('source')) {
      const page = params.get('source');
      const resolved = resolvePageId(page, core.registry);
      if (!resolved) { renderNotFound(core, page); setStatus(''); return; }
      const [pid, meta] = resolved;
      try { await renderSource(core, pid, meta); }
      catch (e) { showFatal(`源码加载失败：${e.message}`); }
      setStatus(''); return;
    }
  }

  let raw = decodeURIComponent(cleanHash);

  // Plugin hook: 自定义路由
  //   handler 返回 null  → 表示"已自行处理", 跳过默认路由
  //   handler 返回 string → 改写 raw
  //   handler 返回 undefined → 保持原值
  const mutated = await core.hooks.onRoute.run(raw, core);
  if (mutated === null) {
    setStatus('');
    return;
  }
  if (typeof mutated === 'string') raw = mutated;

  if (!raw) {
    await renderHome(core);
    setStatus('');
    return;
  }

  // Special: 系统页路由
  if (raw === 'Special:Random') {
    const pids = Object.keys(core.registry.pages).filter(
      p => !p.startsWith('Special:') && core.registry.pages[p].type !== '章节'
    );
    const randomPid = pids[Math.floor(Math.random() * pids.length)];
    location.hash = encodeURIComponent(randomPid);
    setStatus('');
    return;
  }
  if (raw === 'Special:Recent' || raw.startsWith('Special:Recent?')) {
    const qm = raw.indexOf('?');
    const pageNum = qm >= 0 ? parseInt(new URLSearchParams(raw.slice(qm + 1)).get('page') || '1', 10) : 1;
    try { await renderRecent(core, pageNum); } catch (e) { showFatal(`recent.lite.jsonl 加载失败：${e.message}`); }
    setStatus(''); return;
  }
  if (raw === 'Special:Settings') {
    renderSpecialSettings(core);
    setStatus(''); return;
  }
  if (raw === 'Special:Plugins') {
    renderSpecialPlugins(core);
    setStatus(''); return;
  }
  if (raw === 'Special:AllPages' || raw.startsWith('Special:AllPages?')) {
    renderAll(core);
    setStatus(''); return;
  }
  if (raw === 'Special:All') {
    renderSpecialAll(core);
    setStatus(''); return;
  }
  if (raw === 'Special:Statistics' || raw === 'Special:知识量') {
    renderSpecialStatistics(core);
    setStatus(''); return;
  }

  // 动态 Special 页：由插件通过 core.registerSpecialPage() 注册
  const dynPage = core.specialPages.find(
    p => raw === p.id || raw.startsWith(p.id + '?')
  );
  if (dynPage?.render) {
    const params = raw.includes('?') ? new URLSearchParams(raw.slice(raw.indexOf('?') + 1)) : new URLSearchParams();
    try { await dynPage.render(core, params); } catch (e) { showFatal(`${dynPage.id} 渲染失败：${e.message}`); }
    setStatus(''); return;
  }

  const resolved = resolvePageId(raw, core.registry);
  if (!resolved) {
    renderNotFound(core, raw);
    setStatus('');
    return;
  }

  const [pid, meta] = resolved;

  // 类型说明页 → 分面浏览（如 #人物 → #Special:AllPages?type=人物）
  if (meta && meta.tags && meta.tags.includes('页面类型')) {
    const p = new URLSearchParams();
    p.set('type', pid);
    location.hash = '#' + encodeURIComponent('Special:AllPages') + '?' + p.toString();
    setStatus('');
    return;
  }

  document.getElementById('article').innerHTML = '<p class="loading">载入中…</p>';
  document.getElementById('article').dataset.type = '';
  document.body.classList.remove('is-home');

  try {
    const r = await fetch(`pages/${pid}.md`);
    if (!r.ok) throw new Error('HTTP ' + r.status);
    const mdText = await r.text();

    // Frontmatter redirect: type: redirect with redirect: target_slug
    const fmMatch = mdText.match(/^---\n([\s\S]*?)\n---/);
    let fmRedirect = null;
    if (fmMatch) {
      const fm = fmMatch[1];
      if (/^type:\s*redirect\s*$/m.test(fm)) {
        const rd = fm.match(/^redirect:\s*(.+)$/m);
        if (rd) fmRedirect = rd[1].trim();
      }
    }
    if (fmRedirect) {
      const target = fmRedirect;
      const targetResolved = resolvePageId(target, core.registry);
      const label = meta.label || pid;
      const noticeBody = targetResolved
        ? `<a href="#${encodeURIComponent(targetResolved[0])}">${escapeHtml(targetResolved[1]?.label || target)}</a>`
        : `<span class="broken-link">${escapeHtml(target)}</span>`;
      document.getElementById('article').innerHTML =
        `<div class="redirect-notice"><span class="redirect-arrow">⇒</span> 重定向至 ${noticeBody}</div>`;
      document.getElementById('crumb').textContent = label;
      document.title = label + ' · 资治通鉴 Wiki';
      document.getElementById('src-info').innerHTML =
        `<a href="${escapeHtml(meta.path)}" class="src-link" target="_blank">源文件: ${escapeHtml(meta.path)}</a>`;
      document.getElementById('broken-info').textContent = '';
      setStatus('');
      return;
    }

    // Redirect syntax: "#REDIRECT [[目标]]" or "REDIRECT [[目标]]" in body (skip frontmatter)
    const bodyText = mdText.replace(/^---\n[\s\S]*?\n---\n?/, '');
    const firstBodyLine = bodyText.split('\n').find(l => l.trim());
    const redirectMatch = firstBodyLine && firstBodyLine.match(/^#?REDIRECT\s+\[\[([^\]|]+)(?:\|[^\]]+)?\]\]/);
    if (redirectMatch) {
      const target = redirectMatch[1].trim();
      const targetResolved = resolvePageId(target, core.registry);
      // 渲染重定向页（含修订历史），不自动跳转
      const label = meta.label || pid;
      const strippedMd = mdText.replace(/^#?REDIRECT\s+\[\[[^\]]+\]\]\s*/m, `# ${label}\n`);
      await renderPage(core, pid, meta, strippedMd);
      const targetLink = targetResolved
        ? `<a href="#${encodeURIComponent(targetResolved[0])}">${escapeHtml(target)}</a>`
        : `<span class="broken-link">${escapeHtml(target)}</span>`;
      const notice = document.createElement('div');
      notice.className = 'redirect-notice';
      notice.innerHTML = `<span class="redirect-arrow">⇒</span> 重定向至 ${targetLink}`;
      const article = document.getElementById('article');
      const h1 = article.querySelector('h1');
      if (h1) h1.after(notice); else article.prepend(notice);
      setStatus('');
      return;
    }

    await renderPage(core, pid, meta, mdText);
    setStatus('');
    if (pendingPN) tryScrollToPN(pendingPN);
    if (pendingPageAnchor) tryScrollToAnchor(pendingPageAnchor);
  } catch (e) {
    showFatal(`加载 pages/${pid}.md 失败：${e.message}`);
  }
}

// ?pn= 段落导航：等待 DOM 渲染后滚动到目标段落
function tryScrollToPN(pnId, attempts = 0) {
  const el = document.getElementById(pnId);
  if (el) {
    el.scrollIntoView({ behavior: 'smooth', block: 'center' });
    el.classList.add('pn-highlight');
    setTimeout(() => el.classList.remove('pn-highlight'), 2000);
  } else if (attempts < 25) {
    setTimeout(() => tryScrollToPN(pnId, attempts + 1), 80);
  }
}

// #pageId#anchorId 锚点导航：等待 DOM 渲染后滚动到目标标题
// 支持带 § 前缀的标题 ID（如 §烧酒），也兼容不带前缀的旧格式
function tryScrollToAnchor(anchorId, attempts = 0) {
  const el = document.getElementById(anchorId) || document.getElementById('§' + anchorId);
  if (el) {
    el.scrollIntoView({ behavior: 'smooth', block: 'center' });
    el.classList.add('pn-highlight');
    setTimeout(() => el.classList.remove('pn-highlight'), 2000);
  } else if (attempts < 25) {
    setTimeout(() => tryScrollToAnchor(anchorId, attempts + 1), 80);
  }
}
