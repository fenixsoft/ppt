// 最终验证：先遍历所有页触发字体子集加载，等 fonts.ready 后再做裁切感知扫描 + 截图
async page => {
  const tabs = await page.$$('#tabs .tab');
  // 预热：走一遍所有页，让中文子集字体全部加载
  for (let i = 0; i < tabs.length; i++) {
    await tabs[i].click();
    await page.waitForTimeout(300);
  }
  await page.evaluate(() => document.fonts.ready);
  const results = [];
  for (let i = 0; i < tabs.length; i++) {
    await tabs[i].click();
    await page.waitForTimeout(600);
    const id = await tabs[i].getAttribute('data-page');
    await page.screenshot({ path: '/root/ppt/ioc/prototype/.shots/final-' + i + '-' + id + '.png' });
    const r = await page.evaluate(() => {
      const clippedBy = (el, root) => {
        for (let a = el.parentElement; a && a !== root.parentElement; a = a.parentElement) {
          const cs = getComputedStyle(a);
          if (/(hidden|clip)/.test(cs.overflow + cs.overflowX + cs.overflowY)) return a;
        }
        return null;
      };
      const res = [];
      document.querySelectorAll('.page.current > section.card').forEach(c => {
        const cr = c.getBoundingClientRect();
        const title = (c.querySelector('h2') || {}).textContent.trim().slice(0, 14);
        let worst = 0, who = '';
        c.querySelectorAll('*').forEach(e => {
          if (e.children.length > 0) return;
          const er = e.getBoundingClientRect();
          const beyond = er.bottom - cr.bottom;
          if (beyond > worst) {
            const clipper = clippedBy(e, c);
            if (clipper) {
              const kir = clipper.getBoundingClientRect();
              if (er.bottom > kir.bottom + 1) { worst = beyond; who = (e.textContent || '').trim().slice(0, 14) + ' [裁切]'; }
            } else { worst = beyond; who = (e.textContent || '').trim().slice(0, 14) + ' [可见溢出]'; }
          }
        });
        if (worst > 1) res.push(title + ' +' + Math.round(worst) + 'px ' + who);
      });
      // 横向溢出检查
      const st = document.querySelector('.stage').getBoundingClientRect();
      let hOver = 0;
      document.querySelectorAll('.page.current *').forEach(e => {
        if (e.children.length > 0) return;
        hOver = Math.max(hOver, e.getBoundingClientRect().right - st.right);
      });
      if (hOver > 1) res.push('横向超出舞台 +' + Math.round(hOver) + 'px');
      return res;
    });
    results.push(id + ': ' + (r.length ? JSON.stringify(r) : 'OK'));
  }
  return results;
}
