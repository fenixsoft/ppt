#!/usr/bin/env python3
"""ppt 站点门禁口令设置。

用法：python3 scripts/gate-set-auth.py <用户名> <新密码>
把 sha256(salt|user|pass) 写入 assets/gate.js 的 hash 字段（仓库不落明文）。
"""
import hashlib
import pathlib
import re
import sys

GATE = pathlib.Path(__file__).resolve().parent.parent / 'assets' / 'gate.js'
SALT = 'ppt-gate-v1'


def main():
    if len(sys.argv) != 3:
        sys.exit('用法: gate-set-auth.py <用户名> <新密码>')
    user, password = sys.argv[1].strip(), sys.argv[2]
    digest = hashlib.sha256(f'{SALT}|{user}|{password}'.encode()).hexdigest()
    text = GATE.read_text(encoding='utf-8')
    updated, n = re.subn(r"hash: '(?:[0-9a-f]{64}|REPLACE_ME)'",
                         f"hash: '{digest}'", text)
    if n != 1:
        sys.exit(f'错误：{GATE} 中未找到唯一的 hash 字段，请人工检查')
    GATE.write_text(updated, encoding='utf-8')
    print(f'已更新 {GATE}')
    print(f'账号 {user} 生效（hash {digest[:12]}…）。')


if __name__ == '__main__':
    main()
