# ~/ppt — PPT 工作区

基于 [html-ppt-skill](https://github.com/lewislulu/html-ppt-skill) 的自包含静态 HTML 演示文稿工作区。
纯静态 HTML/CSS/JS，无构建步骤，离线可渲染（仅 webfont 走 CDN，失败时回退系统字体）。

## 目录结构

```
~/ppt/
├── assets/            共享框架（所有 deck 通过相对路径引用，勿在 deck 内复制）
│   ├── base.css       设计令牌 + 基础组件（.slide / .img-frame / chrome 槽位）
│   ├── fonts.css      webfont 引入
│   ├── runtime.js     键盘/触摸/滚轮导航 + 演讲者模式 + 概览网格
│   ├── themes/        36 个主题（每主题一个 CSS 令牌覆盖文件）
│   ├── animations/    27 个 CSS 入场动画 + 20 个 canvas 特效（fx/）
│   └── demo-images/   离线占位图（SVG）
├── templates/
│   ├── deck.html                最小 6 页骨架
│   ├── single-page/             36 个单页布局（带示例数据，复制即用）
│   ├── full-decks/              15 个整套模板（pitch-deck / tech-sharing / 周报 / 小红书…）
│   └── *-showcase.html          主题/布局/动画/模板 浏览器（打开按 ← → 翻阅）
├── scripts/
│   ├── new-deck.sh              新建 deck 脚手架（自动重写 assets 相对路径并自检引用）
│   └── render.sh                headless Chrome 截图导出 PNG
└── <deck-name>/                 每个 deck 一个目录，index.html 为入口
    └── demo/                    工作区自带示例 deck，可随时删除
```

## 新建一份 PPT

```bash
cd ~/ppt
./scripts/new-deck.sh <deck-name>              # 从最小骨架创建
./scripts/new-deck.sh <deck-name> -t tech-sharing   # 从整套模板创建（15 选 1）
./scripts/new-deck.sh <deck-name> -t kpi-grid  # 从单个布局创建（36 选 1）
```

生成的 deck 位于 `~/ppt/<deck-name>/index.html`，引用 `../assets/`。
**直接用浏览器打开即可演示。**

## 快捷键

```
← → / 空格 / PgUp PgDn    翻页（触摸滑动、鼠标滚轮同样可用）
T                         循环切换主题
F                         全屏
O                         概览网格
S                         演讲者模式（当前页/下一页预览 + 逐字稿 + 计时器）
N                         备注抽屉
#/N                       URL 深链到第 N 页（如 index.html#/3）
```

演讲稿写在每页的 `<aside class="notes">` 内（display:none，仅 S 模式可见）。

## 导出 PNG

```bash
cd ~/ppt
./scripts/render.sh <deck-name>/index.html all     # 自动检测页数，逐页导出到 <deck-name>/png/
```

依赖本机 Chrome/Chromium（自动探测，或用 `CHROME_BIN=...` 指定）。

## 约定

- **颜色一律用令牌**（`var(--text-1)` / `var(--accent)`），不写死十六进制值；
  强调色上的文字用 `var(--accent-ink)`。
- **写新页先抄布局**：从 `templates/single-page/` 找最接近的复制改造，不从零手写。
- **图片必须套 `.img-frame`**，截图/架构图加 `contain` 类避免裁切。
- **主题试戴**：浏览器打开 `templates/theme-showcase.html` 可一次看全 36 个主题。
- 改 `assets/runtime.js` 里的定制（滚轮翻页等）会影响所有 deck，改动前先确认。
