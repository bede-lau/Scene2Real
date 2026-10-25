// Short-lived, single-use upload grants. Service credentials never leave the servers.
import { randomBytes } from 'node:crypto';
import { Transform } from 'node:stream';

export const MAX_UPLOAD_BYTES = 3 * 200 * 1024 * 1024 + 64 * 1024;
const TTL_MS = 120_000;

export function createUploadTickets(publicOrigin, now = Date.now) {
  const grants = new Map();
  const origin = publicOrigin ? new URL(publicOrigin) : null;
  if (origin && (origin.protocol !== 'https:' || origin.pathname !== '/' || origin.username || origin.password || origin.search || origin.hash)) {
    throw new Error('SCENE2REAL_PUBLIC_ORIGIN must be an HTTPS origin.');
  }
  const validOrigin = value => {
    try {
      const parsed = new URL(value);
      return parsed.origin === value && (parsed.protocol === 'https:' ||
        (parsed.protocol === 'http:' && ['localhost', '127.0.0.1'].includes(parsed.hostname)));
    } catch { return false; }
  };
  const prune = () => { for (const [key, grant] of grants) if (grant.expires <= now()) grants.delete(key); };
  return {
    enabled: !!origin,
    issue(clientOrigin) {
      prune();
      if (!origin || !validOrigin(clientOrigin)) return null;
      if (grants.size >= 128) return null;
      const token = randomBytes(32).toString('base64url');
      const expires = now() + TTL_MS;
      grants.set(token, { origin: clientOrigin, expires });
      return { token, url: new URL('/api/runs', origin).href, expires_at: new Date(expires).toISOString(), max_bytes: MAX_UPLOAD_BYTES };
    },
    consume(token, clientOrigin) {
      prune();
      const grant = grants.get(token);
      if (!grant || grant.origin !== clientOrigin) return false;
      grants.delete(token);
      return true;
    },
    preflight(clientOrigin) { return !!origin && validOrigin(clientOrigin); },
  };
}

export function uploadByteLimit() {
  let bytes = 0;
  return new Transform({ transform(chunk, encoding, callback) {
    bytes += chunk.length;
    callback(bytes > MAX_UPLOAD_BYTES ? new Error('Upload exceeds maximum request size') : null, chunk);
  } });
}
