// Static workbench and same-origin API gateway for the isolated hosting trial.
import http from 'node:http';
import https from 'node:https';
import { createReadStream } from 'node:fs';
import { stat } from 'node:fs/promises';
import { dirname, resolve, sep, extname } from 'node:path';
import { fileURLToPath } from 'node:url';

const root = resolve(dirname(fileURLToPath(import.meta.url)), '../static');
const upstream = new URL(process.env.SCENE2REAL_BACKEND_URL);
const secret = process.env.SCENE2REAL_SITE_TOKEN || '';
if (upstream.protocol !== 'https:' && !(upstream.protocol === 'http:' && ['localhost', '127.0.0.1'].includes(upstream.hostname))) {
  throw new Error('Backend must use HTTPS or local HTTP.');
}
if (upstream.username || upstream.password || upstream.pathname !== '/' || secret.length < 32) {
  throw new Error('Configure a backend origin and private service token.');
}
const types = { '.html': 'text/html', '.js': 'text/javascript', '.mjs': 'text/javascript', '.css': 'text/css', '.json': 'application/json', '.svg': 'image/svg+xml', '.png': 'image/png', '.wasm': 'application/wasm', '.txt': 'text/plain' };
const allowedHeaders = ['content-type', 'content-length', 'accept', 'range', 'if-none-match', 'if-modified-since'];
const responseHeaders = ['content-type', 'content-length', 'content-range', 'content-encoding', 'accept-ranges', 'etag', 'last-modified', 'content-disposition'];
const server = http.createServer(async (req, res) => {
  let url;
  try {
    if (!req.url?.startsWith('/') || req.url.startsWith('//') || req.url.includes('\\')) throw new Error();
    url = new URL(req.url, 'http://workbench.invalid');
  } catch {
    res.writeHead(400).end(); return;
  }
  if (url.pathname.startsWith('/api/') || url.pathname === '/healthz') {
    const headers = { authorization: `Bearer ${secret}`, 'accept-encoding': 'identity' };
    for (const key of allowedHeaders) if (req.headers[key]) headers[key] = req.headers[key];
    const target = new URL(url.pathname + url.search, upstream);
    const transport = upstream.protocol === 'https:' ? https : http;
    const pending = transport.request(target, { method: req.method, headers, timeout: 900_000 }, origin => {
      const outgoing = { 'cache-control': 'no-store' };
      for (const key of responseHeaders) if (origin.headers[key]) outgoing[key] = origin.headers[key];
      res.writeHead(origin.statusCode || 502, outgoing);
      origin.on('error', () => res.destroy());
      origin.pipe(res);
    });
    pending.on('timeout', () => pending.destroy());
    pending.on('error', () => {
      if (res.destroyed) return;
      if (res.headersSent) { res.destroy(); return; }
      res.writeHead(502, { 'content-type': 'application/json', 'cache-control': 'no-store' });
      res.end('{"detail":"Backend unavailable"}');
    });
    req.on('aborted', () => pending.destroy());
    req.on('error', () => pending.destroy());
    res.on('close', () => { if (!res.writableFinished) pending.destroy(); });
    req.pipe(pending);
    return;
  }
  if (!['GET', 'HEAD'].includes(req.method)) { res.writeHead(405, { allow: 'GET, HEAD' }).end(); return; }
  try {
    const pathname = decodeURIComponent(url.pathname === '/' ? '/index.html' : url.pathname);
    const file = resolve(root, '.' + pathname);
    if (!file.startsWith(root + sep) || pathname.includes('\0')) { res.writeHead(404).end(); return; }
    const info = await stat(file);
    if (!info.isFile()) { res.writeHead(404).end(); return; }
    res.writeHead(200, { 'content-type': types[extname(file)] || 'application/octet-stream', 'content-length': info.size, 'cache-control': 'no-cache', 'x-content-type-options': 'nosniff' });
    if (req.method === 'HEAD') { res.end(); return; }
    const stream = createReadStream(file);
    stream.on('error', () => res.destroy());
    res.on('close', () => stream.destroy());
    stream.pipe(res);
  } catch { res.writeHead(404).end(); }
});
server.listen(Number(process.env.PORT || 8080), '0.0.0.0', () => console.log(`Workbench gateway listening on ${server.address().port}`));
for (const signal of ['SIGINT', 'SIGTERM']) process.on(signal, () => server.close(() => process.exit(0)));
