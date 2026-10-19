#!/usr/bin/env bash
# html-ppt :: split-deck.sh — convert a legacy single-file deck to paginated mode
#
# Usage:
#   split-deck.sh <deck-dir>/index.html
#
# Turns one index.html holding every <section class="slide"> into:
#
#   index.html              deck shell: chrome + data-slides manifest
#   slides/NN.html          one standalone page per slide
#   index.html.single.bak   backup of the original single file
#
# Each page keeps the deck's <head> (fonts / base / theme / animations /
# deck css), the <body> attributes (minus data-logo*, which the shell owns)
# and its <section class="slide"> verbatim. References gain one more "../"
# so they resolve from slides/ — "../assets/x" becomes "../../assets/x",
# "style.css" becomes "../style.css".
#
# The original file is kept as index.html.single.bak; a deck that already
# carries a data-slides manifest is refused.

set -euo pipefail

FILE="${1:-}"
if [[ -z "$FILE" || ! -f "$FILE" ]]; then
  echo "usage: split-deck.sh <deck>/index.html" >&2
  exit 1
fi

DIR="$(cd "$(dirname "$FILE")" && pwd)"
BASE="$(basename "$FILE")"

python3 - "$DIR" "$BASE" <<'PY'
import html
import pathlib
import re
import sys

d = pathlib.Path(sys.argv[1]).resolve()
base = sys.argv[2]
f = d / base
src = f.read_text(encoding='utf-8')

if re.search(r'data-slides\s*=', src):
    sys.exit('error: %s already carries a data-slides manifest — nothing to split' % f)

bak = d / (base + '.single.bak')
if bak.exists():
    sys.exit('error: %s exists — refusing to overwrite a previous backup' % bak)

# ---------------------------------------------------------------- anatomy
def prefix(u):
    """One deck-root-relative reference, re-resolved from slides/."""
    if re.match(r'^([a-zA-Z][a-zA-Z0-9+.-]*:|/|#)', u):
        return u
    return '../' + u


def prefix_path_attrs(attrs):
    """Re-resolve path-bearing attributes from slides/ (one ../ deeper)."""
    attrs = re.sub(r'(data-theme-base=")([^"]*)(")',
                   lambda m: m.group(1) + prefix(m.group(2)) + m.group(3), attrs)
    return attrs


mh = re.search(r'<html\b([^>]*)>', src, re.I)
# Raw attrs go to the shell (paths unchanged); the pages sit one level deeper
# and get the prefixed copy.
html_attrs_raw = (mh.group(1).strip() if mh else 'lang="zh-CN"')
html_attrs = prefix_path_attrs(html_attrs_raw)

mb = re.search(r'<body\b([^>]*)>', src, re.I)
body_attrs = (mb.group(1).strip() if mb else '')
# The shell owns the logo (and overlays it on every page); a page that kept
# data-logo would draw a second one on top.
page_body_attrs = re.sub(r'\s*data-logo[-a-z]*="[^"]*"', '', body_attrs).strip()
page_body_attrs = prefix_path_attrs(page_body_attrs)

mh2 = re.search(r'<head\b[^>]*>(.*)</head>', src, re.I | re.S)
head_inner = mh2.group(1) if mh2 else ''

ms = re.search(r'<script\s+src="([^"]*runtime\.js)"[^>]*>\s*</script>', src, re.I)


def prefix_refs(s):
    return re.sub(r'\b(href|src)="([^"]*)"',
                  lambda m: '%s="%s"' % (m.group(1), prefix(m.group(2))),
                  s)


runtime_tag = ''
if ms:
    runtime_tag = '<script src="%s"></script>' % prefix(ms.group(1))

# ---------------------------------------------------------------- slides
def extract_slides(text):
    """Top-level <section class="slide ..."> blocks with their spans."""
    found = []
    i = 0
    while True:
        m = re.compile(r'<section\b[^>]*>', re.I).search(text, i)
        if not m:
            break
        start = m.start()
        depth = 1
        end = None
        for t in re.compile(r'<section\b|</section>', re.I).finditer(text, m.end()):
            depth += 1 if t.group(0).lower().startswith('<section') else -1
            if depth == 0:
                end = t.end()
                break
        if end is None:
            sys.exit('error: unbalanced <section> in %s' % f)
        block = text[start:end]
        if re.search(r'class="[^"]*\bslide\b[^"]*"', block[:block.find('>') + 1]):
            found.append((start, end, block))
        i = end
    return found


slides = extract_slides(src)
if not slides:
    sys.exit('error: no <section class="slide"> found in %s' % f)

# ------------------------------------------------------------- page files
slides_dir = d / 'slides'
slides_dir.mkdir(exist_ok=True)

manifest_lines = []
for n, (_, _, block) in enumerate(slides, 1):
    mt = re.search(r'data-title="([^"]*)"', block)
    title = html.unescape(mt.group(1)).strip() if mt else ''
    fname = '%02d.html' % n
    manifest_lines.append('    slides/%s | %s' % (fname, title))

    page_title = ('%02d · %s' % (n, title)) if title else ('%02d' % n)
    head = head_inner
    if re.search(r'<title[> ]', head, re.I):
        head = re.sub(r'<title>.*?</title>',
                      lambda _: '<title>%s</title>' % html.escape(page_title),
                      head, flags=re.S | re.I)
    else:
        head = '<title>%s</title>\n' % html.escape(page_title) + head

    page = ('<!DOCTYPE html>\n'
            '<html %s>\n'
            '<head>%s</head>\n'
            '<body%s>\n'
            '<div class="deck">\n\n'
            '%s\n\n'
            '</div>\n'
            '%s\n'
            '</body>\n'
            '</html>\n') % (html_attrs, prefix_refs(head),
                            (' ' + page_body_attrs) if page_body_attrs else '',
                            prefix_refs(block), ('\n' + runtime_tag) if runtime_tag else '')
    (slides_dir / fname).write_text(page, encoding='utf-8')

# ------------------------------------------------------------- the shell
body_mb = re.search(r'<body\b[^>]*>(.*)</body>', src, re.I | re.S)
body_inner = body_mb.group(1) if body_mb else ''
# Cut the slide blocks out of the body (spans relative to body_inner itself,
# recomputed after every cut).
while True:
    remaining = extract_slides(body_inner)
    if not remaining:
        break
    s0, e0, _ = remaining[0]
    body_inner = body_inner[:s0] + body_inner[e0:]

body_inner = re.sub(r'<!--.*?-->', '', body_inner, flags=re.S)      # slide banners
body_inner = re.sub(r'[ \t]*\n([ \t]*\n)+', '\n\n', body_inner)     # leftover gaps
body_inner = body_inner.strip('\n')

manifest = '\n' + '\n'.join(manifest_lines) + '\n  '
deck_re = re.compile(r'(<div\b[^>]*\bclass="[^"]*\bdeck\b[^"]*")([^>]*)(>)', re.I)
if not deck_re.search(body_inner):
    sys.exit('error: no <div class="deck"> found in %s' % f)
body_inner = deck_re.sub(
    lambda m: m.group(1) + (m.group(2) if 'data-slides' in m.group(2) else '') +
              ' data-slides="%s"%s' % (html.escape(manifest, quote=True), m.group(3)),
    body_inner, count=1)

shell = ('<!DOCTYPE html>\n<html %s>\n<head>%s</head>\n<body%s>\n%s\n</body>\n</html>\n'
         % (html_attrs_raw, head_inner, (' ' + body_attrs) if body_attrs else '', body_inner))

bak.write_text(src, encoding='utf-8')
f.write_text(shell, encoding='utf-8')

print('✔ split %s into %d page(s)' % (f, len(slides)))
print('  backup:  %s' % bak)
print('  pages:   %s' % slides_dir)
print('  manifest: %d entr(ies) in index.html data-slides' % len(slides))
PY
