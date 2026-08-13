const currentImports = {};
const exportSet = new Set(['Module', '__esModule', 'default', '_export_sfc']);
let moduleMap = {
  "./Config":()=>{dynamicLoadingCss(["__federation_expose_Config-weiyuncookie.css"], false, './Config');return __federation_import('./__federation_expose_Config-weiyuncookie.js').then(module =>Object.keys(module).every(item => exportSet.has(item)) ? () => module.default : () => module)},
  "./Page":()=>{dynamicLoadingCss(["__federation_expose_Page-weiyuncookie.css"], false, './Page');return __federation_import('./__federation_expose_Page-weiyuncookie.js').then(module =>Object.keys(module).every(item => exportSet.has(item)) ? () => module.default : () => module)},
};
const seen = {};
const dynamicLoadingCss = (cssFilePaths, dontAppendStylesToHead, exposeItemName) => {const metaUrl = import.meta.url;if (typeof metaUrl === 'undefined') return;const curUrl = metaUrl.substring(0, metaUrl.lastIndexOf('remoteEntry.js'));cssFilePaths.forEach(cssPath => {const href = curUrl + cssPath;if (dontAppendStylesToHead) { const key = 'css__weiyuncookie__' + exposeItemName; window[key] = window[key] || []; window[key].push(href); return; }if (href in seen) return; seen[href] = true;const element = document.createElement('link'); element.rel = 'stylesheet'; element.href = href; document.head.appendChild(element);});};
async function __federation_import(name) { currentImports[name] ??= import(name); return currentImports[name] }
const get =(module) => { if(!moduleMap[module]) throw new Error('Can not find remote module ' + module); return moduleMap[module](); };
const init =(shareScope) => { globalThis.__federation_shared__= globalThis.__federation_shared__|| {}; Object.entries(shareScope || {}).forEach(([key, value]) => { for (const [versionKey, versionValue] of Object.entries(value)) { const scope = versionValue.scope || 'default'; globalThis.__federation_shared__[scope] = globalThis.__federation_shared__[scope] || {}; const shared= globalThis.__federation_shared__[scope]; (shared[key] = shared[key]||{})[versionKey] = versionValue; } }); };
export { dynamicLoadingCss, get, init };
