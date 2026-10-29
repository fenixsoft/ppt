/* ============================================================
 * ppt 站点统一门禁（纯静态可行版）
 * - 由 scripts/add-gate.py 注入到各 deck 壳层页（index/meeting1 等）
 * - slides/散页由 add-gate.py 注入内联守卫（重定向到所属 deck 首页）
 * - 口令轮换：python3 scripts/gate-set-auth.py <用户名> <新密码>
 * - 安全上限：防随意访问与搜索引擎收录，不防定向扒取（静态内容本质公开）
 * - 注意：站点是明文 HTTP（home.icyfenix.cn:28080），crypto.subtle 不可用，
 *   故内置纯 JS SHA-256；localStorage 异常时放行（fail-open，不锁死演示场景）
 * ============================================================ */
(function () {
  'use strict';
  var CFG = {
    salt: 'ppt-gate-v1',
    days: 7,                      // 记住天数
    storeKey: 'ppt_gate',
    accounts: [                   // 由 scripts/gate-set-auth.py 维护（add/remove/list）
      { u: 'icyfenix', h: 'd2d673301e52425d71ba8bdc59ba8882c0ee38374a805178ddd47c223d210a60' },
      { u: 'user', h: 'b8672c7ea80368e3f94a3ae2a48028a29b1a85c412a385a89a68e1fe2cd04be8' },
    ],
  };
  if (!CFG.accounts.length) return; // 未配置账号前不设防

  /* ---------- 存储（fail-open） ---------- */
  function readExp() {
    try {
      var v = JSON.parse(localStorage.getItem(CFG.storeKey) || 'null');
      return v && typeof v.exp === 'number' ? v.exp : 0;
    } catch (e) { return Infinity; } // 存储不可用 → 放行
  }
  function authed() { return readExp() > Date.now(); }

  /* ---------- 纯 JS SHA-256（无 secure context 依赖，多次调用安全） ---------- */
  function rightRotate(v, a) { return (v >>> a) | (v << (32 - a)); }
  function sha256(ascii) {
    var maxWord = Math.pow(2, 32), result = '';
    var words = [], asciiBitLength = ascii.length * 8;
    var hash = [], k = [], primeCounter = 0, isComposite = {}, i, j;
    for (var candidate = 2; primeCounter < 64; candidate++) {
      if (!isComposite[candidate]) {
        for (i = 0; i < 313; i += candidate) isComposite[i] = candidate;
        hash[primeCounter] = (Math.pow(candidate, .5) * maxWord) | 0;
        k[primeCounter++] = (Math.pow(candidate, 1 / 3) * maxWord) | 0;
      }
    }
    ascii += '\x80';
    while (ascii.length % 64 - 56) ascii += '\x00';
    for (i = 0; i < ascii.length; i++) {
      j = ascii.charCodeAt(i);
      if (j >> 8) return ''; // 非 ASCII 输入，调用方应先转 UTF-8
      words[i >> 2] |= j << ((3 - i) % 4) * 8;
    }
    words[words.length] = (asciiBitLength / maxWord) | 0;
    words[words.length] = asciiBitLength;
    for (j = 0; j < words.length;) {
      var w = words.slice(j, j += 16), oldHash = hash.slice(0, 8);
      for (i = 16; i < 64; i++) {
        var w15 = w[i - 15], w2 = w[i - 2];
        var s0 = rightRotate(w15, 7) ^ rightRotate(w15, 18) ^ (w15 >>> 3);
        var s1 = rightRotate(w2, 17) ^ rightRotate(w2, 19) ^ (w2 >>> 10);
        w[i] = (w[i - 16] + s0 + w[i - 7] + s1) | 0;
      }
      var a = oldHash[0], b = oldHash[1], c = oldHash[2], d = oldHash[3],
          e = oldHash[4], f = oldHash[5], g = oldHash[6], h = oldHash[7];
      for (i = 0; i < 64; i++) {
        var S1 = rightRotate(e, 6) ^ rightRotate(e, 11) ^ rightRotate(e, 25);
        var ch = (e & f) ^ (~e & g);
        var temp1 = (h + S1 + ch + k[i] + w[i]) | 0;
        var S0 = rightRotate(a, 2) ^ rightRotate(a, 13) ^ rightRotate(a, 22);
        var maj = (a & b) ^ (a & c) ^ (b & c);
        var temp2 = (S0 + maj) | 0;
        h = g; g = f; f = e; e = (d + temp1) | 0;
        d = c; c = b; b = a; a = (temp1 + temp2) | 0;
      }
      var work = [a, b, c, d, e, f, g, h];
      for (i = 0; i < 8; i++) hash[i] = (oldHash[i] + work[i]) | 0;
    }
    for (i = 0; i < 8; i++)
      for (j = 3; j + 1; j--) {
        var b2 = (hash[i] >> (j * 8)) & 255;
        result += (b2 >> 4).toString(16) + (b2 & 15).toString(16);
      }
    return result;
  }
  function sha256Utf8(s) {
    // 非 ASCII（如中文口令）先转 UTF-8 字节串，每 charCode ≤255
    var bytes = unescape(encodeURIComponent(s));
    return sha256(bytes);
  }

  /* ---------- 已认证：不作为 ---------- */
  if (authed()) return;

  /* ---------- 未认证：同步隐藏页面，杜绝内容闪现 ---------- */
  document.documentElement.className += ' ppt-gate-pending';
  var style = document.createElement('style');
  style.textContent =
    'html.ppt-gate-pending{visibility:hidden}' +
    '.ppt-gate-lock{position:fixed;inset:0;z-index:99999;display:flex;' +
    'align-items:center;justify-content:center;background:#f6f5f2;visibility:visible}' +
    '.ppt-gate-card{width:340px;background:#fff;border:1px solid #e6e2d8;border-radius:14px;' +
    'box-shadow:0 12px 40px rgba(36,64,122,.10);padding:30px 32px 26px;font-family:inherit}' +
    '.ppt-gate-kicker{font-size:12px;font-weight:700;letter-spacing:.12em;color:#24407a;margin:0 0 6px}' +
    '.ppt-gate-title{font-size:20px;font-weight:700;color:#1c2330;margin:0 0 18px}' +
    '.ppt-gate-card input{width:100%;box-sizing:border-box;font-size:15px;padding:10px 12px;' +
    'margin-bottom:10px;border:1px solid #d8d4c8;border-radius:8px;background:#fbfaf7;color:#1c2330}' +
    '.ppt-gate-card input:focus{outline:none;border-color:#24407a;background:#fff}' +
    '.ppt-gate-btn{width:100%;font-size:15px;font-weight:700;padding:10px 0;margin-top:4px;' +
    'border:none;border-radius:8px;background:#24407a;color:#fff;cursor:pointer}' +
    '.ppt-gate-btn:hover{background:#1b315d}' +
    '.ppt-gate-err{min-height:18px;font-size:13px;color:#c0392b;margin:2px 0 0}' +
    '.ppt-gate-hint{font-size:12px;color:#a49c88;text-align:center;margin:14px 0 0}' +
    '.ppt-gate-shake{animation:ppt-gate-shake .3s}' +
    '@keyframes ppt-gate-shake{25%{transform:translateX(-5px)}75%{transform:translateX(5px)}}';
  document.head.appendChild(style);

  function boot() {
    if (authed()) { // 竞态兜底：等 DOM 期间在别处完成了认证
      document.documentElement.className =
        document.documentElement.className.replace(' ppt-gate-pending', '');
      return;
    }
    var lock = document.createElement('div');
    lock.className = 'ppt-gate-lock';
    lock.innerHTML =
      '<form class="ppt-gate-card" autocomplete="off">' +
      '<p class="ppt-gate-kicker">PPT 站点 · 访问验证</p>' +
      '<p class="ppt-gate-title">内部资料，请登录后查看</p>' +
      '<input name="u" placeholder="用户名" autofocus>' +
      '<input name="p" type="password" placeholder="密码">' +
      '<button class="ppt-gate-btn" type="submit">进 入</button>' +
      '<p class="ppt-gate-err"></p>' +
      '<p class="ppt-gate-hint">本站内容仅限内部使用 · 请勿外传</p>' +
      '</form>';
    document.body.appendChild(lock);
    /* 键盘截停：表单按键在 lock 处（冒泡相）就地消化，runtime 等全局
     * 快捷键（f 全屏、Backspace 翻页并 preventDefault 等）一律收不到 */
    ['keydown', 'keyup', 'keypress'].forEach(function (t) {
      lock.addEventListener(t, function (e) { e.stopPropagation(); });
    });
    lock.querySelector('[name=u]').focus();

    lock.querySelector('form').addEventListener('submit', function (ev) {
      ev.preventDefault();
      var u = lock.querySelector('[name=u]').value.trim();
      var p = lock.querySelector('[name=p]').value;
      var card = lock.querySelector('.ppt-gate-card');
      var ok = CFG.accounts.some(function (a) {
        return a.u === u && sha256Utf8(CFG.salt + '|' + u + '|' + p) === a.h;
      });
      if (ok) {
        try {
          localStorage.setItem(CFG.storeKey,
            JSON.stringify({ exp: Date.now() + CFG.days * 864e5 }));
        } catch (e) { /* fail-open：无存储则本次会话放行 */ }
        /* 整页重载：以已认证状态重走启动流程。原位摘遮罩在部分真实环境
         * （缩放/扩展/全屏态）不可靠，reload 后 gate 直接放行，确定性最高 */
        location.reload();
      } else {
        lock.querySelector('.ppt-gate-err').textContent = '用户名或密码不正确';
        card.classList.remove('ppt-gate-shake');
        void card.offsetWidth; // 重触发抖动动画
        card.classList.add('ppt-gate-shake');
      }
    });
  }
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', boot);
  } else {
    boot();
  }
})();
