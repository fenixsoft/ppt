#!/usr/bin/env python3
"""为 ppt deck 内容页接入统一门禁（幂等，可反复运行）。

- 壳层页（含 data-slides 清单的 index/meeting1 等）：注入 <script src=…/assets/gate.js>
  —— gate.js 渲染全屏登录遮罩，认证通过后 7 天内不再询问。
- 内容页（slides/、散页 briefing 等）：注入内联守卫——未认证时隐藏并重定向到
  所属 deck 首页（就近向上找 index.html），杜绝直达 URL 绕过壳层门禁。
- 同时注入 <meta name="robots" content="noindex,nofollow">。

用法：python3 scripts/add-gate.py [--dry] [目录…]   # 默认 ioc ipd
新 deck 落成后重跑本脚本即可补接线。
"""
import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
MARK = 'ppt-gate'          # 注入标记，幂等判据
NOINDEX = '<meta name="robots" content="noindex,nofollow">'


def rel(path: pathlib.Path, start: pathlib.Path) -> str:
    r = pathlib.os.path.relpath(path, start)
    return r if r.startswith('.') else './' + r


def find_deck_index(directory: pathlib.Path):
    """从 directory 逐级向上找最近的 index.html 所在目录。"""
    for d in [directory, *directory.parents]:
        if (d / 'index.html').is_file() and d != ROOT:
            return d
    return None


def inject(text: str, snippet: str) -> str:
    """插到 viewport meta 之后；没有则插到 <head> 之后。"""
    m = re.search(r'(<meta\s+name="viewport"[^>]*>)', text)
    if m:
        return text[:m.end()] + '\n' + snippet + text[m.end():]
    m = re.search(r'(<head[^>]*>)', text)
    if m:
        return text[:m.end()] + '\n' + snippet + text[m.end():]
    raise ValueError('找不到 <head> 或 viewport meta 注入点')


def process(path: pathlib.Path, dry: bool, stats: dict) -> None:
    text = path.read_text(encoding='utf-8')
    if MARK in text:
        stats['skip'] += 1
        return
    if find_deck_index(path.parent) is None and not (path.parent == ROOT):
        print(f'  !! 跳过（找不到所属 deck index）：{path.relative_to(ROOT)}')
        stats['warn'] += 1
        return

    is_shell = ('data-slides="' in text or "data-slides='" in text
                or path.name == 'index.html')  # 入口页一律挂遮罩，防自我重定向
    if is_shell:
        gate_src = rel(ROOT / 'assets' / 'gate.js', path.parent)
        snippet = (NOINDEX +
                   f'\n<script src="{gate_src}"></script><!-- {MARK} 壳层门禁 -->')
    else:
        deck = find_deck_index(path.parent)
        target = rel(deck / 'index.html', path.parent)
        snippet = (NOINDEX +
                   '\n<script>/* ' + MARK +
                   ' 内容页守卫 */try{var g=JSON.parse(localStorage.getItem("ppt_gate"));'
                   f'if(!(g&&g.exp>Date.now())){{document.documentElement.style.visibility="hidden";'
                   f'location.replace("{target}?auth=1")}}}}catch(e){{}}</script>')

    try:
        new_text = inject(text, snippet)
    except ValueError as e:
        print(f'  !! 跳过（{e}）：{path.relative_to(ROOT)}')
        stats['warn'] += 1
        return

    kind = '壳层' if is_shell else '内容'
    print(f'  + {kind}门禁 → {path.relative_to(ROOT)}'
          + ('' if not is_shell else ''))
    stats['shell' if is_shell else 'page'] += 1
    if not dry:
        path.write_text(new_text, encoding='utf-8')


def main():
    argv = [a for a in sys.argv[1:]]
    dry = '--dry' in argv
    dirs = [a for a in argv if not a.startswith('--')] or ['ioc', 'ipd']
    stats = {'shell': 0, 'page': 0, 'skip': 0, 'warn': 0}
    print(f'模式：{"DRY-RUN 预演" if dry else "写入"}，范围：{dirs}')
    for d in dirs:
        base = ROOT / d
        if not base.is_dir():
            sys.exit(f'目录不存在：{base}')
        for path in sorted(base.rglob('*.html')):
            if '.playwright-cli' in path.parts:
                continue
            process(path, dry, stats)
    print(f"完成：壳层 {stats['shell']}，内容页 {stats['page']}，"
          f"已接线跳过 {stats['skip']}，警告 {stats['warn']}")


if __name__ == '__main__':
    main()
