import fs from 'node:fs';
import path from 'node:path';
import assert from 'node:assert/strict';
import { fileURLToPath } from 'node:url';
import { spawnSync } from 'node:child_process';

const root = fileURLToPath(new URL('../dist/', import.meta.url));
const routes = ['', 'about', 'services', 'doctors', 'contact'];
const pages = new Map();
let references = 0;
for (const route of routes) {
  const file = path.join(root, route, 'index.html');
  const html = fs.readFileSync(file, 'utf8');
  const ids = [...html.matchAll(/\bid="([^"]+)"/g)].map(match => match[1]);
  assert.equal(new Set(ids).size, ids.length, `Duplicate IDs in ${route || 'home'}`);
  assert.equal([...html.matchAll(/<h1\b/g)].length, 1, `Expected one H1 in ${route || 'home'}`);
  assert(!html.includes('/v2/'), `Old /v2/ route in ${route || 'home'}`);
  assert(!html.includes('Landing page version 1'), `Old version link in ${route || 'home'}`);
  pages.set(path.resolve(file), { html, ids:new Set(ids) });
}
for (const [file, { html }] of pages) {
  for (const match of html.matchAll(/\b(?:href|src)="([^"]+)"/g)) {
    const reference = match[1];
    if (/^(?:[a-z]+:|\/\/)/i.test(reference)) continue;
    const url = new URL(reference, 'https://hm.example/' + path.relative(root, file).replaceAll('\\', '/'));
    let target = path.resolve(root, '.' + decodeURIComponent(url.pathname));
    if (fs.existsSync(target) && fs.statSync(target).isDirectory()) target = path.join(target, 'index.html');
    assert(fs.existsSync(target), `Missing target ${reference} in ${path.relative(root, file)}`);
    if (url.hash && pages.has(target)) assert(pages.get(target).ids.has(decodeURIComponent(url.hash.slice(1))), `Missing anchor ${reference}`);
    references++;
  }
}
const syntax = spawnSync(process.execPath, ['--check', path.join(root, 'script.js')], {encoding:'utf8'});
assert.equal(syntax.status, 0, syntax.stderr);
console.log(`PASS: ${pages.size} pages, ${references} internal references, anchors, route cleanup, and JavaScript syntax.`);
