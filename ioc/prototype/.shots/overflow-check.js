// 遍历 5 个页签，检测文字/内容溢出容器边界的元素
async page => {
  const results = {};
  const tabs = await page.$$('#tabs .tab');
  for (let i = 0; i < tabs.length; i++) {
    await tabs[i].click();
    await page.waitForTimeout(600); // 等 ECharts 渲染
    const pageId = await tabs[i].getAttribute('data-page');
    const found = await page.evaluate(() => {
      const out = [];
      const page = document.querySelector('.page.current');
      if (!page) return out;
      const els = page.querySelectorAll('*');
      for (const el of els) {
        const cs = getComputedStyle(el);
        if (cs.display === 'none') continue;
        // 跳过有意滚动的容器
        if (/(auto|scroll)/.test(cs.overflow + cs.overflowX + cs.overflowY)) continue;
        const hOver = el.scrollWidth - el.clientWidth;
        const vOver = el.scrollHeight - el.clientHeight;
        // 只有当溢出方向可见（visible）时才是"文字冒出边界"；hidden 则是被裁切，也算问题
        const hasText = el.textContent.trim().length > 0;
        if (!hasText) continue;
        // 排除 canvas/svg 内部
        if (['CANVAS','SVG','PATH'].includes(el.tagName)) continue;
        if (hOver > 2 || vOver > 2) {
          // 只报告"叶子或近似叶子"元素，避免每个祖先都报一遍
          const kidOver = [...el.children].some(c => {
            const kcs = getComputedStyle(c);
            if (kcs.display === 'none') return false;
            return (c.scrollWidth - c.clientWidth > 2) || (c.scrollHeight - c.clientHeight > 2);
          });
          if (kidOver) continue;
          const r = el.getBoundingClientRect();
          out.push({
            tag: el.tagName.toLowerCase(),
            cls: (el.className + '').slice(0, 60),
            text: el.textContent.trim().replace(/\s+/g, ' ').slice(0, 40),
            hOver, vOver,
            overflowX: cs.overflowX, overflowY: cs.overflowY,
            whiteSpace: cs.whiteSpace,
            box: `x=${Math.round(r.x)},y=${Math.round(r.y)},w=${Math.round(r.width)},h=${Math.round(r.height)}`
          });
        }
      }
      return out;
    });
    results[pageId] = found;
  }
  return results;
}
