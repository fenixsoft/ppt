#!/usr/bin/env python3
"""html-ppt :: export-pdf.py — deck 导出矢量 PDF（文字可选中，非截图拼合）

原理：Chromium page.pdf() 命中 assets/base.css 内置的 @media print 样式
（一张 .slide = 一页 PDF），分页 deck 逐页导出后用 pypdf 合并。

用法:
  ./scripts/export-pdf.py <deck-name>          # 如 ioc → 生成 ioc/ioc-deck.pdf
  ./scripts/export-pdf.py <deck-dir>           # 传目录亦可
  ./scripts/export-pdf.py <deck> -o 自定.pdf   # 自定义输出路径

支持两种 deck 形态：
  分页 deck（index.html data-slides 清单 + slides/NN.html）：逐页导出合并，
    并把单页文件里被 runtime 写成 1/1 的页码修正为真实 N/总页数；
  legacy 单文件 deck（全部 <section class="slide"> 内联在 index.html）：
    整份一次导出，页码用文件内烘焙值。

依赖：python3 -m pip install playwright pypdf && python3 -m playwright install chromium
"""
import asyncio
import re
import sys
from pathlib import Path

try:
    from playwright.async_api import async_playwright
    from pypdf import PdfWriter
except ImportError as e:
    sys.exit(f"缺少依赖: {e}\n请先: python3 -m pip install playwright pypdf && python3 -m playwright install chromium")

WORKSPACE = Path(__file__).resolve().parent.parent
PAGE_W, PAGE_H = 1920, 1080  # 16:9，1440x810 pt
SETTLE_MS = 2500             # 入场动画 + canvas 图表落定

PDF_KWARGS = dict(
    width=f"{PAGE_W}px", height=f"{PAGE_H}px",
    print_background=True, scale=1,
    margin={"top": "0", "bottom": "0", "left": "0", "right": "0"},
)


def resolve_deck(arg: str) -> Path:
    p = Path(arg)
    if not p.is_absolute():
        p = WORKSPACE / arg
    if p.is_dir():
        return p
    sys.exit(f"error: deck 目录不存在: {p}")


def manifest_slides(deck: Path) -> list[str]:
    """解析 index.html 的 data-slides 清单，返回相对 slides 文件列表。"""
    html = (deck / "index.html").read_text(encoding="utf-8")
    m = re.search(r'data-slides="(.*?)"', html, re.S)
    if not m:
        sys.exit(f"error: {deck}/index.html 无 data-slides 清单，也不是 legacy 单文件 deck")
    files = []
    for line in m.group(1).splitlines():
        line = line.strip()
        if line and not line.startswith("//"):
            files.append(line.split("|")[0].strip())
    return files


async def settle(page):
    """等 webfont 与内嵌 iframe（原型页等）的字体就绪，再留动画落定时间。"""
    await page.evaluate("document.fonts.ready")
    for frame in page.frames[1:]:
        try:
            await frame.evaluate("document.fonts.ready")
        except Exception:
            pass
    await page.wait_for_timeout(SETTLE_MS)


async def export_paginated(browser, deck: Path, files: list[str], parts: list[Path]):
    total = len(files)
    for i, rel in enumerate(files, 1):
        src = deck / rel
        if not src.exists():
            sys.exit(f"error: 清单中的页面文件不存在: {src}")
        page = await browser.new_page(viewport={"width": PAGE_W, "height": PAGE_H})
        try:
            await page.goto(src.as_uri(), wait_until="networkidle")
            await settle(page)
            # 修正页码：单页文件里 runtime 写成 1/1，源文件还可能有陈旧烘焙值
            await page.evaluate(
                """([cur, total]) => {
                    document.querySelectorAll('.slide-number').forEach(el => {
                        el.setAttribute('data-current', cur);
                        el.setAttribute('data-total', total);
                    });
                    // base.css 打印样式隐藏 deck-footer（页码本由 runtime 动态写，
                    // 静态打印会失真）；导出时页码已修正，保留页脚。
                    const st = document.createElement('style');
                    st.textContent = '@media print{.deck-footer{display:flex!important}}';
                    document.head.appendChild(st);
                }""",
                [i, total],
            )
            await page.pdf(path=str(parts[i - 1]), page_ranges="1", **PDF_KWARGS)
        finally:
            await page.close()
        print(f"  ✔ {rel}", flush=True)


def count_legacy_slides(deck: Path) -> int:
    html = (deck / "index.html").read_text(encoding="utf-8")
    return len(re.findall(r'<section[^>]*class="[^"]*\bslide\b[^"]*"', html))


async def export_legacy(browser, deck: Path, out: Path):
    page = await browser.new_page(viewport={"width": PAGE_W, "height": PAGE_H})
    try:
        await page.goto((deck / "index.html").as_uri(), wait_until="networkidle")
        await settle(page)
        # 整份打印，print 样式按 break-after:page 一页一张 slide
        await page.pdf(path=str(out), **PDF_KWARGS)
        print(f"  ✔ index.html（{count_legacy_slides(deck)} 张 slide 一次导出）", flush=True)
    finally:
        await page.close()


async def main():
    import argparse

    ap = argparse.ArgumentParser(description="html-ppt deck → 矢量 PDF")
    ap.add_argument("deck", help="deck 名（工作区下）或 deck 目录路径")
    ap.add_argument("-o", "--output", help="输出 PDF 路径（默认 <deck>/<deck名>-deck.pdf）")
    args = ap.parse_args()

    deck = resolve_deck(args.deck)
    out = Path(args.output) if args.output else deck / f"{deck.name}-deck.pdf"
    if not out.is_absolute():
        out = Path.cwd() / out
    work = WORKSPACE / ".playwright-cli" / f"pdf-{deck.name}"
    work.mkdir(parents=True, exist_ok=True)

    slides_dir = deck / "slides"
    paginated = slides_dir.is_dir() and any(slides_dir.glob("*.html"))
    parts = []
    async with async_playwright() as p:
        browser = await p.chromium.launch()
        if paginated:
            files = manifest_slides(deck)
            parts = [work / f"{i:02d}.pdf" for i in range(1, len(files) + 1)]
            await export_paginated(browser, deck, files, parts)
        else:
            await export_legacy(browser, deck, out)
        await browser.close()

    if parts:
        merger = PdfWriter()
        for part in parts:
            merger.append(str(part))
        with open(out, "wb") as f:
            merger.write(f)
    print(f"done: {out} ({out.stat().st_size / 1048576:.1f} MB)")


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
