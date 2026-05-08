/* 入口。 加载依赖 / 注册表 / 插件, 启动路由器。 */

import { createHooks } from './hooks.js';
import { loadRegistry, loadFullRegistry, extendRegistry } from './registry.js';
import { setupRouter } from './router.js';
import { createMarkdownIt } from './parser.js';
import { showFatal } from './util.js';
import { renderHeroShell } from './renderer.js';

const HOOK_NAMES = [
  'onBoot',          // (core)                              启动完成, 插件已加载
  'onRoute',         // (raw, core) → string | null | undef 自定义路由
  'onBeforeRender',  // (body, {pid,meta,front}) → body     MD 源预处理
  'onAfterRender',   // (html, {pid,meta,front}) → html     HTML 后处理
  'onInfobox',       // (rows, front, meta) → rows          Infobox 行定制
];

const SETTINGS_KEY = 'wiki_settings';
const SETTINGS_DEFAULTS = { autoWikilink: false };

function loadSettings() {
  try {
    return Object.assign({}, SETTINGS_DEFAULTS, JSON.parse(localStorage.getItem(SETTINGS_KEY) || '{}'));
  } catch { return { ...SETTINGS_DEFAULTS }; }
}

function saveSettings(settings) {
  try { localStorage.setItem(SETTINGS_KEY, JSON.stringify(settings)); } catch {}
}

async function boot() {
  const core = {
    hooks: createHooks(HOOK_NAMES),
    registry: null,
    md: null,
    plugins: [],
    specialPages: [],
    settings: loadSettings(),
  };
  core.setSetting = (key, val) => {
    core.settings[key] = val;
    saveSettings(core.settings);
  };
  core.registerSpecialPage = (def) => core.specialPages.push(def);
  window.__wiki = core;

  if (!window.markdownit || !window.jsyaml) {
    showFatal('依赖未加载 (markdown-it / js-yaml)');
    return;
  }
  core.md = createMarkdownIt();

  // URL 已有 hash 路由（如 /#贾宝玉）→ 不渲染首页英雄区，避免主页 SVG 闪烁
  const hasRoute = location.hash.length > 1;
  if (!hasRoute) renderHeroShell();

  try {
    // 1. 快速加载轻量注册表（仅 wikilink 解析所需字段）
    core.registry = await loadRegistry('pages.lite.json');
    console.log(`[boot] lite registry loaded: ${core.registry.page_count} pages`);

    // 2. 后台加载全量数据，合并后升级搜索/category 等特性
    core.fullRegistryReady = loadFullRegistry('pages.json').then(full => {
      extendRegistry(core.registry, full);
      console.log('[boot] full registry merged');
    }).catch(e => {
      console.warn('[boot] full registry load failed, using lite:', e.message);
    });
  } catch (e) {
    showFatal('无法加载 pages.lite.json：' + e.message);
    return;
  }

  await loadPlugins(core);
  await core.hooks.onBoot.run(core);
  setupRouter(core);
}

async function loadPlugins(core) {
  let manifest;
  try {
    const r = await fetch('plugins.json');
    if (!r.ok) return;
    manifest = await r.json();
  } catch (e) {
    return;
  }

  for (const entry of (manifest.plugins || [])) {
    try {
      const bust = entry.version ? '?v=' + entry.version : '';
      const mod = await import('../' + entry.entry + bust);
      const p = mod.default;
      if (!p || typeof p.init !== 'function') {
        console.warn(`[plugin] ${entry.id} 缺少 default.init`);
        continue;
      }
      await p.init(core);
      core.plugins.push({
        id:          entry.id,
        name:        entry.name        || entry.id,
        version:     entry.version     || '?',
        description: entry.description || '',
      });
      console.log(`[plugin] ${entry.id} v${entry.version || '?'} loaded`);
    } catch (e) {
      console.error(`[plugin] ${entry.id} 加载失败:`, e);
    }
  }
}

boot();
