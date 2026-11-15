// Minimal static server for the Eds Hair rebuild preview.
// Mirrors what a real host (Shopify / nginx / Cloudflare) does:
// gzip + brotli-ish compression, long cache for static assets, no-cache for HTML.
//
//   node serve.js [port] [root]
//
const http = require('http');
const fs = require('fs');
const path = require('path');
const zlib = require('zlib');

const port = Number(process.argv[2] || 8899);
const root = path.resolve(process.argv[3] || path.join(__dirname, 'site'));

const TYPES = {
  '.html': 'text/html; charset=utf-8',
  '.css': 'text/css; charset=utf-8',
  '.js': 'text/javascript; charset=utf-8',
  '.json': 'application/json; charset=utf-8',
  '.webp': 'image/webp',
  '.png': 'image/png',
  '.jpg': 'image/jpeg',
  '.svg': 'image/svg+xml',
  '.webmanifest': 'application/manifest+json',
  '.xml': 'application/xml; charset=utf-8',
  '.txt': 'text/plain; charset=utf-8',
};

const COMPRESSIBLE = new Set(['.html', '.css', '.js', '.json', '.webmanifest', '.xml', '.txt', '.svg']);

function send(res, code, headers, body) {
  res.writeHead(code, headers);
  if (body) res.end(body);
  else res.end();
}

const server = http.createServer((req, res) => {
  let urlPath;
  try {
    urlPath = decodeURIComponent(new URL(req.url, 'http://localhost').pathname);
  } catch {
    return send(res, 400, { 'Content-Type': 'text/plain' }, 'Bad request');
  }
  if (urlPath.endsWith('/')) urlPath += 'index.html';

  const filePath = path.join(root, urlPath);
  // Prevent path traversal outside the site root.
  if (!filePath.startsWith(root)) {
    return send(res, 403, { 'Content-Type': 'text/plain' }, 'Forbidden');
  }

  fs.stat(filePath, (err, stat) => {
    if (err || !stat.isFile()) {
      return send(res, 404, { 'Content-Type': 'text/plain; charset=utf-8' }, 'Not found');
    }

    const ext = path.extname(filePath).toLowerCase();
    const type = TYPES[ext] || 'application/octet-stream';
    const isHTML = ext === '.html';
    const cache = isHTML ? 'public, max-age=0, must-revalidate' : 'public, max-age=31536000, immutable';

    const headers = {
      'Content-Type': type,
      'Cache-Control': cache,
      'X-Content-Type-Options': 'nosniff',
      'Vary': 'Accept-Encoding',
    };

    const accepts = String(req.headers['accept-encoding'] || '');
    if (COMPRESSIBLE.has(ext) && /\bgzip\b/.test(accepts)) {
      headers['Content-Encoding'] = 'gzip';
      res.writeHead(200, headers);
      fs.createReadStream(filePath)
        .pipe(zlib.createGzip({ level: 9 }))
        .pipe(res);
      return;
    }

    headers['Content-Length'] = stat.size;
    res.writeHead(200, headers);
    fs.createReadStream(filePath).pipe(res);
  });
});

server.listen(port, '127.0.0.1', () => {
  console.log(`Eds Hair rebuild preview: http://localhost:${port}/`);
  console.log(`Serving: ${root}`);
});
