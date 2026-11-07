import http from 'node:http';
import fs from 'node:fs/promises';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const root = fileURLToPath(new URL('../dist/', import.meta.url));
const port = Number(process.env.PORT || 4173);
const types = { '.html':'text/html; charset=utf-8', '.css':'text/css; charset=utf-8', '.js':'text/javascript; charset=utf-8', '.jpg':'image/jpeg', '.jpeg':'image/jpeg', '.png':'image/png', '.svg':'image/svg+xml', '.ico':'image/x-icon' };
const server = http.createServer(async (request, response) => {
  if (!['GET', 'HEAD'].includes(request.method)) {
    response.writeHead(405, { Allow:'GET, HEAD' }); response.end('Method not allowed'); return;
  }
  let filename;
  try {
    const pathname = decodeURIComponent(new URL(request.url, 'http://localhost').pathname);
    filename = path.resolve(root, '.' + pathname);
    const relative = path.relative(root, filename);
    if (relative.startsWith('..') || path.isAbsolute(relative)) {
      response.writeHead(403); response.end('Forbidden'); return;
    }
    const stat = await fs.stat(filename);
    if (stat.isDirectory()) filename = path.join(filename, 'index.html');
    const content = await fs.readFile(filename);
    response.writeHead(200, { 'Content-Type':types[path.extname(filename)] || 'application/octet-stream', 'X-Content-Type-Options':'nosniff' });
    response.end(request.method === 'HEAD' ? undefined : content);
  } catch (error) {
    const status = error instanceof URIError ? 400 : 404;
    response.writeHead(status, { 'Content-Type':'text/plain; charset=utf-8' });
    response.end(status === 400 ? 'Bad request' : 'Page not found');
  }
});
server.listen(port, '127.0.0.1', () => console.log(`HM Diagnostics preview: http://127.0.0.1:${port}/`));
