#!/usr/bin/env python3
"""28080 静态文件服务：SimpleHTTP + no-cache + gzip + HTTP/1.1 keep-alive。

- Cache-Control: no-cache：浏览器每次 revalidate，文件未变时返回 304，
  避免"文件更新后仍显示旧页面"。
- Accept-Encoding: gzip 时对文本类响应透明压缩（fonts.css 1.2MB -> ~100KB）。
- protocol_version 1.1：keep-alive 复用连接。deck 首开 300+ 请求，
  HTTP/1.0 下每个请求都要新建 TCP 连接，公网上每连接多 1~2 个 RTT。

用法: python3 serve.py [port] [root]
"""
import gzip
import re
import functools
import http.server
import socketserver
import sys
import urllib.parse

PORT = int(sys.argv[1]) if len(sys.argv) > 1 else 28080
ROOT = sys.argv[2] if len(sys.argv) > 2 else "/root/ppt"

# 只压文本；woff2/图片本身已压缩，压了不赚还耗 CPU
COMPRESSIBLE = ('.html', '.css', '.js', '.json', '.svg', '.txt', '.xml')
GZIP_MIN, GZIP_MAX = 1024, 8 * 1024 * 1024   # 太小不赚，太大占内存


class NoCacheHandler(http.server.SimpleHTTPRequestHandler):
    protocol_version = "HTTP/1.1"   # keep-alive
    timeout = 60                    # 空闲连接超时回收，避免线程滞留

    def end_headers(self):
        self.send_header("Cache-Control", "no-cache")
        super().end_headers()

    def do_GET(self):
        path = urllib.parse.urlsplit(self.path).path
        wants_gzip = (
            'gzip' in (self.headers.get('Accept-Encoding') or '')
            and path.lower().endswith(COMPRESSIBLE)
        )
        if not wants_gzip:
            super().do_GET()
            return
        # 透明捕获 SimpleHTTP 的原始响应，改写为 gzip 后回发
        chunks = []
        real_wfile = self.wfile

        class _Capture:
            def write(self, b):
                chunks.append(b)
                return len(b)
            def flush(self):
                real_wfile.flush()

        self.wfile = _Capture()
        try:
            super().do_GET()
        finally:
            self.wfile = real_wfile

        raw = b''.join(chunks)
        head, sep, body = raw.partition(b'\r\n\r\n')
        status_line, _, headers = head.partition(b'\r\n')
        # 仅压缩 200 且有实体的响应；304/重定向/错误页原样透传
        if not sep or not status_line.endswith(b' 200 OK') \
                or not (GZIP_MIN <= len(body) <= GZIP_MAX):
            real_wfile.write(raw)
            return
        body = gzip.compress(body, compresslevel=6, mtime=0)
        headers = re.sub(rb'(?mi)^Content-Length: \d+\r\n',
                         b'Content-Length: %d\r\n' % len(body), headers)
        # headers 末行无 \r\n（被分区吃掉），先补齐再追加新头；最后单独的
        # \r\n 是头块结束的空行，之后紧跟 body，多一个少一个都会错帧。
        headers += b'\r\nContent-Encoding: gzip\r\nVary: Accept-Encoding\r\n'
        real_wfile.write(status_line + b'\r\n' + headers + b'\r\n' + body)


class ThreadingTCPServer(socketserver.ThreadingMixIn, socketserver.TCPServer):
    daemon_threads = True
    allow_reuse_address = True


if __name__ == "__main__":
    handler = functools.partial(NoCacheHandler, directory=ROOT)
    with ThreadingTCPServer(("0.0.0.0", PORT), handler) as httpd:
        print(f"serving {ROOT} at 0.0.0.0:{PORT} (no-cache + gzip + HTTP/1.1)", flush=True)
        httpd.serve_forever()
