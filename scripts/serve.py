#!/usr/bin/env python3
"""28080 静态文件服务：在 SimpleHTTP 基础上附加 Cache-Control: no-cache。

SimpleHTTP 原生不返回 Cache-Control，浏览器按 Last-Modified 启发式缓存，
导致文件更新后仍显示旧页面。加上 no-cache 后浏览器每次都 revalidate，
文件未变时仍返回 304，不浪费带宽。

用法: python3 serve.py [port] [root]
"""
import functools
import http.server
import socketserver
import sys

PORT = int(sys.argv[1]) if len(sys.argv) > 1 else 28080
ROOT = sys.argv[2] if len(sys.argv) > 2 else "/root/ppt"


class NoCacheHandler(http.server.SimpleHTTPRequestHandler):
    def end_headers(self):
        self.send_header("Cache-Control", "no-cache")
        super().end_headers()


class ThreadingTCPServer(socketserver.ThreadingMixIn, socketserver.TCPServer):
    daemon_threads = True
    allow_reuse_address = True


if __name__ == "__main__":
    handler = functools.partial(NoCacheHandler, directory=ROOT)
    with ThreadingTCPServer(("0.0.0.0", PORT), handler) as httpd:
        print(f"serving {ROOT} at 0.0.0.0:{PORT} (Cache-Control: no-cache)", flush=True)
        httpd.serve_forever()
