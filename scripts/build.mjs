import { cp, mkdir, readFile, rm, writeFile } from 'node:fs/promises';
import { fileURLToPath } from 'node:url';
import { execFileSync } from 'node:child_process';
import path from 'node:path';

const root = fileURLToPath(new URL('../', import.meta.url));
const output = path.join(root, 'dist');
const sources = JSON.parse(await readFile(path.join(root, 'data/sources.json'), 'utf8'));
const escape = (text) => String(text).replace(/[&<>"']/g, (character) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' })[character]);
const ids = new Set();
for (const source of sources) {
  if (!/^[a-z]+$/.test(source.id) || ids.has(source.id)) throw new Error('Source IDs must be unique lowercase identifiers');
  ids.add(source.id);
  for (const field of ['name', 'organisation', 'region', 'label', 'description', 'checked']) {
    if (typeof source[field] !== 'string' || !source[field].trim()) throw new Error(`Missing ${field} for ${source.id}`);
  }
  if (new URL(source.url).protocol !== 'https:') throw new Error(`Source ${source.id} must use HTTPS`);
  if (!source.categories.length || source.categories.some((category) => !['research', 'business', 'public'].includes(category))) throw new Error(`Invalid categories for ${source.id}`);
}
const cards = sources.map((source) => `
    <article class="source-card" data-categories="${escape(source.categories.join(' '))}">
      <div class="source-meta"><span>${escape(source.organisation)}</span><span>${escape(source.region)}</span></div>
      <h3><a href="${escape(source.url)}" rel="external">${escape(source.name)}</a></h3>
      <p>${escape(source.description)}</p>
      <div class="source-bottom"><span>${escape(source.label)}</span><svg viewBox="0 0 24 24" aria-hidden="true"><path d="M10 13a5 5 0 0 0 7 .1l3-3a5 5 0 0 0-7-7l-2 2M14 11a5 5 0 0 0-7-.1l-3 3a5 5 0 0 0 7 7l2-2"/></svg></div>
    </article>`).join('\n');
await rm(output, { recursive: true, force: true });
await mkdir(output, { recursive: true });
await cp(path.join(root, 'public'), output, { recursive: true });
await cp(path.join(root, 'node_modules/@dobriy/interface-style/dist'), path.join(output, 'interface-style'), { recursive: true });
const template = await readFile(path.join(root, 'public/index.html'), 'utf8');
if (!template.includes('<!-- FUNDING_SOURCES -->')) throw new Error('Missing source-list placeholder');
await writeFile(path.join(output, 'index.html'), template.replace('<!-- FUNDING_SOURCES -->', cards));
let commit = 'local';
try { commit = execFileSync('git', ['rev-parse', 'HEAD'], { cwd: root, encoding: 'utf8' }).trim(); } catch {}
await writeFile(path.join(output, 'release.json'), JSON.stringify({ commit, builtAt: new Date().toISOString(), interfaceStyle: '0.1.4' }) + '\n');
console.log(`Built Shortlist with ${sources.length} funding sources and local company styles.`);
