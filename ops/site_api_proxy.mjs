import { timingSafeEqual } from 'node:crypto';
import { Readable, pipeline } from 'node:stream';
import http from 'node:http';
import { createUploadTickets, MAX_UPLOAD_BYTES, uploadByteLimit } from './upload_tickets.mjs';

const token = process.env.SCENE2REAL_SITE_TOKEN ?? '';
const upstream = new URL(process.env.SCENE2REAL_PROXY_UPSTREAM ?? 'http://127.0.0.1:8090');
const port = Number(process.env.SCENE2REAL_PROXY_PORT ?? 8091);
const host = process.env.SCENE2REAL_PROXY_HOST ?? '127.0.0.1';
const uploads = createUploadTickets(process.env.SCENE2REAL_PUBLIC_ORIGIN);

if (token.length < 32) {
  throw new Error('SCENE2REAL_SITE_TOKEN must be at least 32 characters.');
}
if (upstream.protocol !== 'http:' || !['127.0.0.1', 'localhost', '::1'].includes(upstream.hostname)) {
  throw new Error('The API proxy upstream must use HTTP on loopback.');
}
if (!['127.0.0.1', '0.0.0.0'].includes(host)) {
  throw new Error('The API proxy host must be 127.0.0.1 or 0.0.0.0.');
}

const expectedAuthorization = Buffer.from(`Bearer ${token}`);
const hopByHopHeaders = new Set([
  'connection', 'keep-alive', 'proxy-authenticate', 'proxy-authorization',
  'te', 'trailer', 'transfer-encoding', 'upgrade',
]);
const staticFiles = new Set([
  '/', '/index.html', '/favicon.svg', '/favicon.ico', '/scene2real-mark.svg',
  '/styles.css', '/app.js', '/startup.js', '/incident_report.js', '/irs_2012_worksheet.js',
  '/rehearsal.html', '/rehearsal.css', '/rehearsal.js',
]);

function isStaticAsset(pathname) {
  return staticFiles.has(pathname)
    || ['/vendor/', '/assets/', '/clips/'].some(prefix => pathname.startsWith(prefix));
}

function isAuthorized(value) {
  if (typeof value !== 'string') return false;
  const supplied = Buffer.from(value);
  return supplied.length === expectedAuthorization.length
    && timingSafeEqual(supplied, expectedAuthorization);
}

const server = http.createServer(async (request, response) => {
  const requestTarget = request.url ?? '';
  if (!requestTarget.startsWith('/') || requestTarget.startsWith('//') || requestTarget.includes('\\')) {
    response.writeHead(400, { 'content-type': 'text/plain; charset=utf-8' });
    response.end('Invalid request target');
    return;
  }

  let path;
  try {
    path = new URL(requestTarget, upstream);
  } catch {
    response.writeHead(400, { 'content-type': 'text/plain; charset=utf-8' });
    response.end('Invalid request target');
    return;
  }
  if (path.origin !== upstream.origin) {
    response.writeHead(400, { 'content-type': 'text/plain; charset=utf-8' });
    response.end('Invalid request target');
    return;
  }
  const directUpload = path.pathname === '/api/runs' && !path.search && uploads.enabled;
  const clientOrigin = request.headers.origin;
  if (directUpload && request.method === 'OPTIONS' && uploads.preflight(clientOrigin)) {
    response.writeHead(204, {
      'access-control-allow-origin': clientOrigin,
      'access-control-allow-methods': 'POST',
      'access-control-allow-headers': 'content-type, x-scene2real-upload-ticket',
      'cache-control': 'no-store', vary: 'Origin',
    }).end();
    return;
  }
  const ticketUpload = directUpload && request.method === 'POST'
    && /^multipart\/form-data; boundary=/i.test(request.headers['content-type'] || '')
    && uploads.consume(request.headers['x-scene2real-upload-ticket'], clientOrigin);
  if (ticketUpload) {
    response.setHeader('access-control-allow-origin', clientOrigin);
    response.setHeader('vary', 'Origin');
    response.setHeader('cache-control', 'no-store');
    if (Number(request.headers['content-length']) > MAX_UPLOAD_BYTES) {
      response.writeHead(413, { 'content-type': 'application/json' }).end('{"detail":"Upload exceeds maximum request size"}');
      return;
    }
  }
  if (path.pathname === '/healthz') {
    if (!['GET', 'HEAD'].includes(request.method)) {
      response.writeHead(405, { allow: 'GET, HEAD', 'cache-control': 'no-store' });
      response.end();
      return;
    }
    let healthy = false;
    try {
      const result = await fetch(new URL('/api/health', upstream), {
        signal: AbortSignal.timeout(2000),
      });
      healthy = result.ok;
      await result.body?.cancel();
    } catch {
      // A probe never exposes origin errors or credentials.
    }
    response.writeHead(healthy ? 200 : 503, {
      'cache-control': 'no-store',
      'content-type': 'application/json; charset=utf-8',
    });
    response.end(request.method === 'HEAD' ? undefined : JSON.stringify({ status: healthy ? 'ok' : 'unavailable' }));
    return;
  }
  const isApi = path.pathname.startsWith('/api/');
  const isStatic = isStaticAsset(path.pathname);
  if (!isApi && !isStatic) {
    response.writeHead(404, { 'content-type': 'text/plain; charset=utf-8' });
    response.end('Not found');
    return;
  }
  if (isStatic && !['GET', 'HEAD'].includes(request.method ?? 'GET')) {
    response.writeHead(405, { allow: 'GET, HEAD', 'cache-control': 'no-store' });
    response.end();
    return;
  }
  if (!ticketUpload && !isAuthorized(request.headers.authorization)) {
    response.writeHead(401, {
      'cache-control': 'no-store',
      'content-type': 'application/json; charset=utf-8',
      'www-authenticate': 'Bearer',
    });
    response.end('{"detail":"Unauthorized"}');
    return;
  }

  if (path.pathname === '/api/upload-ticket') {
    if (!uploads.enabled) { response.writeHead(404).end(); return; }
    if (request.method !== 'POST' || path.search) { response.writeHead(405, { allow: 'POST' }).end(); return; }
    let body = '', size = 0;
    try {
      for await (const chunk of request) {
        size += chunk.length;
        if (size > 4096) { response.writeHead(413).end(); return; }
        body += chunk;
      }
      const grant = uploads.issue(JSON.parse(body).origin);
      response.writeHead(grant ? 200 : 400, { 'content-type': 'application/json', 'cache-control': 'no-store' });
      response.end(JSON.stringify(grant || { detail: 'Upload origin unavailable' }));
    } catch { response.writeHead(400).end(); }
    return;
  }

  const headers = new Headers(request.headers);
  headers.delete('authorization');
  headers.delete('x-scene2real-upload-ticket');
  headers.delete('host');
  headers.delete('content-length');
  headers.delete('connection');
  headers.delete('transfer-encoding');
  // Node fetch transparently decompresses responses; request an uncompressed
  // response so forwarded metadata describes the bytes sent to the client.
  headers.set('accept-encoding', 'identity');

  const hasBody = !['GET', 'HEAD'].includes(request.method ?? 'GET');
  const controller = new AbortController();
  response.once('close', () => {
    if (!response.writableFinished) controller.abort();
  });
  try {
    const limited = ticketUpload ? uploadByteLimit() : null;
    if (limited) {
      limited.on('error', () => controller.abort());
      request.on('error', error => limited.destroy(error));
      request.pipe(limited);
    }
    const result = await fetch(path, {
      method: request.method,
      headers,
      signal: controller.signal,
      body: hasBody ? (limited || request) : undefined,
      ...(hasBody ? { duplex: 'half' } : {}),
    });
    const responseHeaders = {};
    for (const [name, value] of result.headers) {
      if (!hopByHopHeaders.has(name.toLowerCase())) responseHeaders[name] = value;
    }
    if (result.headers.has('content-encoding') && result.headers.get('content-encoding') !== 'identity') {
      delete responseHeaders['content-encoding'];
      delete responseHeaders['content-length'];
    }
    response.writeHead(result.status, responseHeaders);
    if (!result.body) {
      response.end();
    } else {
      // pipeline handles errors from the upstream body and tears down the
      // response on truncation or client disconnect without crashing Node.
      pipeline(Readable.fromWeb(result.body), response, () => {});
    }
  } catch {
    if (response.destroyed) return;
    if (!response.headersSent) {
      response.writeHead(502, {
        'cache-control': 'no-store',
        'content-type': 'application/json; charset=utf-8',
      });
    }
    response.end('{"detail":"API origin unavailable"}');
  }
});

server.listen(port, host, () => {
  console.log(`Scene2Real API auth proxy listening on ${host}:${port}`);
});

for (const signal of ['SIGINT', 'SIGTERM']) {
  process.on(signal, () => server.close(() => process.exit(0)));
}
