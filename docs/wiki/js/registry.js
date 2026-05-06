/* 页面注册表加载与 id 解析。
 *
 * 启动时序:
 *   1. loadRegistry('pages.lite.json')  → 快速返回轻量注册表
 *   2. 页面渲染、路由、wikilink 解析立即可用
 *   3. loadFullRegistry()  → 后台拉取 pages.json，合并入 registry.pages
 *      — 搜索索引/category 浏览等依赖全量字段的操作在合并后自动升级
 */

export async function loadRegistry(url = 'pages.lite.json') {
  const bust = `?v=${Math.floor(Date.now() / 60000)}`;
  const r = await fetch(url + bust);
  if (!r.ok) throw new Error(`${url} HTTP ${r.status}`);
  return r.json();
}

export async function loadFullRegistry(url = 'pages.json') {
  const bust = `?v=${Math.floor(Date.now() / 60000)}`;
  const r = await fetch(url + bust);
  if (!r.ok) throw new Error(`${url} HTTP ${r.status}`);
  return r.json();
}

/**
 * 将全量注册表合并到已加载的 lite registry 中。
 * lite 中的 {type, label, aliases} 会被全量版的完整字段覆盖。
 */
export function extendRegistry(lite, full) {
  for (const [pid, entry] of Object.entries(full.pages || {})) {
    lite.pages[pid] = entry;
  }
  lite._fullLoaded = true;
  return lite;
}

/**
 * 路由/wikilink 的 id 解析:
 *   1. 精确匹配 pages[raw]
 *   2. 别名 alias_index[raw]
 *   3. 若 raw 带 "type/slug" 前缀, 取 slug 再按别名查 (兼容旧 slug 式)
 * @returns {[string, object] | null}  [pid, pageEntry] 或 null
 */
export function resolvePageId(raw, registry) {
  if (!raw) return null;
  if (raw in registry.pages) return [raw, registry.pages[raw]];
  if (raw in registry.alias_index) {
    const pid = registry.alias_index[raw];
    return [pid, registry.pages[pid]];
  }
  if (raw.includes('/')) {
    const tail = raw.split('/', 2)[1];
    if (tail in registry.pages) return [tail, registry.pages[tail]];
    if (tail in registry.alias_index) {
      const pid = registry.alias_index[tail];
      return [pid, registry.pages[pid]];
    }
  }
  return null;
}
