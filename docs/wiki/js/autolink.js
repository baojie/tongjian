/* 自动 wikilink / 正文高亮。
 *
 * autoWikilink:   正文中已知词条（slug+别名）→ [[链接]]，由 protectWikilinks 统一处理。
 * boldPageTerms:  当前页名+别名 → **加粗**，在 autoWikilink 之前执行。
 *
 * 共同保护区域（不做任何处理）：
 *   - 代码块 ``` 与行内代码 `
 *   - 标题行 # H1~H6
 *   - 已有 [[wikilink]]
 *   - Markdown 链接与图片
 *
 * 单字 CJK wikilink 需两侧都不是 CJK 汉字才链接。
 */

// Unicode 私用区占位符
const PH_OPEN = '';
const PH_CLOSE = '';

// 保护区域正则：代码块、行内代码、标题、已有 wikilink、Markdown 链接/图片、PN 定义/引注
const PROTECTED_RE = /```[\s\S]*?```|`[^`]+`|^#{1,6} .*$|\[\[[^\[\]]+?\]\]|!?\[[^\[\]]*\]\([^)]+\)|（\d{3}-\d{3}）|\[\d{3}-\d{3}\]/gm;

const CJK_START = 0x4E00;
const CJK_END = 0x9FFF;

function isCJK(ch) {
  if (!ch) return false;
  const cp = ch.charCodeAt(0);
  return cp >= CJK_START && cp <= CJK_END;
}

let _trie = null;

/* 从 registry.alias_index 构建前缀树。
 * 每个节点若为某词条终点，其 $ 属性为 canonical slug。
 */
function buildTrie(aliasIndex) {
  const root = {};
  for (const [term, canonical] of Object.entries(aliasIndex)) {
    let node = root;
    for (const ch of term) {
      if (!node[ch]) node[ch] = {};
      node = node[ch];
    }
    node.$ = canonical;
  }
  return root;
}

/* 扫描一段纯文本（无保护区域），返回添加 [[wikilink]] 后的文本。 */
function scanAndLink(text) {
  const out = [];
  let i = 0;
  const trie = _trie;
  if (!trie) return text;

  while (i < text.length) {
    let node = trie;
    let bestMatch = null;

    // 从前缀树中查找从 i 开始的最长匹配
    for (let j = i; j < text.length; j++) {
      const ch = text[j];
      if (!node[ch]) break;
      node = node[ch];
      if (node.$) {
        bestMatch = { start: i, end: j + 1, target: node.$ };
      }
    }

    if (bestMatch) {
      const matchedText = text.slice(bestMatch.start, bestMatch.end);
      const isSingleCJK = matchedText.length === 1 && isCJK(matchedText);

      if (isSingleCJK) {
        // 单字 CJK：两侧都不能紧邻 CJK 汉字（避免扫入多字词内部）
        const prevCh = i > 0 ? text[i - 1] : null;
        const nextCh = bestMatch.end < text.length ? text[bestMatch.end] : null;
        if (isCJK(prevCh) || isCJK(nextCh)) {
          out.push(text[i]);
          i++;
          continue;
        }
      }

      // 产生 wikilink 语法
      if (matchedText === bestMatch.target) {
        out.push(`[[${matchedText}]]`);
      } else {
        out.push(`[[${bestMatch.target}|${matchedText}]]`);
      }
      i = bestMatch.end;
    } else {
      out.push(text[i]);
      i++;
    }
  }

  return out.join('');
}

/**
 * 自动为正文中出现的已知词条添加 wikilink。
 *
 * @param {string} body     前置处理后的 markdown 正文（已过 onBeforeRender hook）
 * @param {object} registry pages.json 注册表，含 pages / alias_index
 * @returns {string} 添加 [[wikilink]] 后的正文
 */
export function autoWikilink(body, registry) {
  if (!_trie) {
    _trie = buildTrie(registry.alias_index);
  }

  // 分割为保护段和可扫描段
  const segments = splitProtectedZones(body);

  return segments
    .map(seg => seg.type === 'text' ? scanAndLink(seg.content) : seg.content)
    .join('');
}

/**
 * 将正文中当前页面的名称和别名加粗。
 *
 * 使用 `<strong>` 而非 `**`，因为中文标点后紧跟 `**` 无法被 CommonMark
 * 正确识别为闭合标记（举例：`**宝玉**。` 中 `**` 后接 `。` 属非空白标点，
 * 按 CommonMark 规则该 `**` 不能闭合，导致整段不加粗）。
 *
 * @param {string} body         markdown 正文
 * @param {string[]} pageTerms  当前页面名 + 所有别名
 * @returns {string} 添加 <strong> 后的正文
 */
export function boldPageTerms(body, pageTerms) {
  const terms = [...new Set(pageTerms)].filter(Boolean);
  if (terms.length === 0) return body;

  // 按长度降序（最长匹配优先，避免"宝玉"被"宝"截胡）
  const sorted = terms.sort((a, b) => b.length - a.length);

  const segments = splitProtectedZones(body);
  const re = new RegExp(
    sorted.map(t => t.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')).join('|'),
    'g'
  );

  return segments
    .map(seg => seg.type === 'text' ? seg.content.replace(re, m => `<strong>${m}</strong>`) : seg.content)
    .join('');
}

/* 将正文分割为保护段（不做处理）和可扫描段。 */
function splitProtectedZones(body) {
  const segments = [];
  let lastEnd = 0;
  PROTECTED_RE.lastIndex = 0;
  let m;
  while ((m = PROTECTED_RE.exec(body)) !== null) {
    if (m.index > lastEnd) {
      segments.push({ type: 'text', content: body.slice(lastEnd, m.index) });
    }
    segments.push({ type: 'protected', content: m[0] });
    lastEnd = m.index + m[0].length;
  }
  if (lastEnd < body.length) {
    segments.push({ type: 'text', content: body.slice(lastEnd) });
  }
  return segments;
}
