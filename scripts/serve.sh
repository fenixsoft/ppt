#!/usr/bin/env bash
# html-ppt :: serve.sh — cache-friendly static server for deck development
#
# Usage:
#   serve.sh [port] [root-dir]        # defaults: 8000, current directory
#
# Why not `python3 -m http.server`? It sends no Cache-Control, so the browser
# revalidates every asset on every load — with a paginated deck (one iframe
# per page, all sharing the same fonts/base/theme/runtime) that means the
# same half-dozen files requested once per page on every refresh.
# This server sends strong cache headers, so every page's shared assets are
# fetched from the network exactly once and then served from cache.

set -euo pipefail

PORT="${1:-8000}"
ROOT="${2:-$PWD}"

if [[ ! -d "$ROOT" ]]; then
  echo "error: $ROOT is not a directory" >&2
  exit 1
fi
ROOT="$(cd "$ROOT" && pwd)"

python3 - "$PORT" "$ROOT" <<'PY'
import http.server
import os
import sys

port = int(sys.argv[1])
root = sys.argv[2]
os.chdir(root)

CACHE = {
    '.woff2': 'public, max-age=31536000, immutable',
    '.woff':  'public, max-age=31536000, immutable',
    '.css':   'public, max-age=86400',
    '.js':    'public, max-age=86400',
    '.png':   'public, max-age=86400',
    '.jpg':   'public, max-age=86400',
    '.jpeg':  'public, max-age=86400',
    '.gif':   'public, max-age=86400',
    '.svg':   'public, max-age=86400',
    '.html':  'no-cache',   # always revalidate the deck pages themselves
}


class Handler(http.server.SimpleHTTPRequestHandler):
    def end_headers(self):
        # strip query/hash before the extension check — deck pages are always
        # requested as slides/NN.html?preview=1, and splitext on the raw path
        # yields '.html?preview=1', silently falling into the 1h bucket.
        clean = self.path.split('?', 1)[0].split('#', 1)[0]
        ext = os.path.splitext(clean)[1].lower()
        self.send_header('Cache-Control', CACHE.get(ext, 'public, max-age=3600'))
        super().end_headers()

    def log_message(self, fmt, *args):
        sys.stderr.write('%s - %s\n' % (self.address_string(), fmt % args))


http.server.ThreadingHTTPServer(('0.0.0.0', port), Handler).serve_forever()
PY
