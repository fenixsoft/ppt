#!/usr/bin/env python3
"""ppt 站点门禁账号管理（多账号，hash 入库不落明文）。

用法：
  python3 scripts/gate-set-auth.py add <用户名> <密码>    # 新增或更新账号
  python3 scripts/gate-set-auth.py remove <用户名>        # 移除账号
  python3 scripts/gate-set-auth.py list                   # 查看已配置账号

账号以 { u: '用户名', h: 'sha256(salt|用户名|密码)' } 形式存于
assets/gate.js 的 accounts 数组；salt 见脚本内 SALT。
"""
import hashlib
import pathlib
import re
import sys

GATE = pathlib.Path(__file__).resolve().parent.parent / 'assets' / 'gate.js'
SALT = 'ppt-gate-v1'
BLOCK_RE = re.compile(r"(accounts:\s*\[)(.*?)(\n\s*\],)", re.S)
ENTRY_RE = re.compile(r"\{ u: '([^']*)', h: '[0-9a-f]{64}' \}(,?)\s*(?://.*)?")


def digest(user: str, password: str) -> str:
    return hashlib.sha256(f'{SALT}|{user}|{password}'.encode()).hexdigest()


def load_entries(text: str):
    m = BLOCK_RE.search(text)
    if not m:
        sys.exit(f'错误：{GATE} 中未找到 accounts 配置块')
    entries = []
    for line in m.group(2).splitlines():
        em = ENTRY_RE.match(line.strip())
        if em:
            entries.append([em.group(1), em.group(0)])
    return m, entries


def main():
    argv = sys.argv[1:]
    if not argv:
        sys.exit(__doc__)
    cmd = argv[0]
    text = GATE.read_text(encoding='utf-8')
    m, entries = load_entries(text)

    if cmd == 'list':
        for u, _ in entries:
            print(u)
        print(f'共 {len(entries)} 个账号')
        return

    if cmd == 'add':
        if len(argv) != 3:
            sys.exit('用法: gate-set-auth.py add <用户名> <密码>')
        user, password = argv[1].strip(), argv[2]
        line = f"      {{ u: '{user}', h: '{digest(user, password)}' }},"
        new_block = m.group(2)
        replaced = False
        for i, (u, raw) in enumerate(entries):
            if u == user:  # 原地更新该账号行
                new_block = new_block.replace(raw, line.strip())
                replaced = True
        if not replaced:
            new_block = new_block.rstrip('\n') + '\n' + line if new_block.strip() \
                else '\n' + line
        text = text[:m.start(2)] + new_block + text[m.end(2):]
        action = '更新' if replaced else '新增'
    elif cmd == 'remove':
        if len(argv) != 2:
            sys.exit('用法: gate-set-auth.py remove <用户名>')
        user = argv[1].strip()
        new_lines = [l for l in m.group(2).splitlines()
                     if not (ENTRY_RE.match(l.strip()) and
                             ENTRY_RE.match(l.strip()).group(1) == user)]
        if len(new_lines) == len(m.group(2).splitlines()):
            sys.exit(f'账号不存在：{user}')
        text = text[:m.start(2)] + '\n'.join(new_lines) + text[m.end(2):]
        action = '移除'
    else:
        sys.exit(__doc__)

    GATE.write_text(text, encoding='utf-8')
    print(f'已{action}账号 {user}（{GATE}）')


if __name__ == '__main__':
    main()
