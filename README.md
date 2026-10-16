# 《密安十二时辰》官方网站（静态站）

> **CRYPTO LISTING: THE FINAL 12** —— 一部以上币前十二时辰为轴的长篇小说。
> 在线阅读：**https://www.cryptofinal12.xyz**

这是一份**纯静态**站点：没有后端、没有数据库、不需要 Node 运行时。
`build.py` 把小说正文渲染成 HTML，Cloudflare Pages 直接托管。

## 目录

```
site/
  build.py          构建脚本（Python 标准库，无第三方依赖）
  data/
    config.json     捐助地址、对外域名 siteUrl
    glossary.json   词条词典（释义 + 外链，构建时烘进 HTML 做内联浮层）
    episodes.json   分集元数据
  assets/           样式 / 脚本 / 图片 / 背景音乐
  index.html        首页（构建产物）
  about.html        关于（构建产物）
  episodes/01..26.html
deploy.sh           构建 + 推送 Cloudflare Pages 的一键脚本
tools/
  cf_deploy.py      部署脚本（内部调用官方 wrangler）
  README.md         部署细节与踩坑记录
  cfcli/            wrangler 的本地安装目录（node_modules 不入库）
```

## Kindle 版 PDF

作者用 Kindle Voyage 精读校订，所以另有一份**按 Kindle 屏 1:1 排版**的 PDF：

```bash
python tools/make_kindle.py                # 含【0xTim 的低语】，529 页
python tools/make_kindle.py --no-whisper   # 只要正文
python tools/make_kindle.py --font-size 11 # 调字号
```

产出 `dist-book/密安十二时辰-Kindle版-YYYYMMDD.pdf`（另复制一份 `-最新.pdf`）。

- 页面 91×123mm，正好等于 Voyage 的可视区，Kindle 上 1:1 显示、不被缩放
- 结构：封面 → 版权页 → 关于本书 → 人物 → 目录 → 26 集正文 → 关于作者 → 版权与合作 → 捐助 → 封底
- 有页码、有 26 个分集书签；PDF 元数据里写了作者、网址与"禁止转载"
- 正文里的站内词条/价格标记会自动转成纯文本（纸质化不需要链接）

## 本地构建

```bash
python site/build.py
```

产物输出到 `site/`（同时导出上传包 `dist/` 与 zip）。
构建脚本读取小说正文（`WB_*.md`）——**小说原稿不在这个仓库里**，由作者本地维护。

## 发布

```bash
./deploy.sh "本次改了什么"
```

需要先在项目根目录放一份 `.env.cloudflare`（不会入库）：

```
CF_ACCOUNT_ID=...
CF_API_TOKEN=...
CF_PAGES_PROJECT=mian-12h
CF_PAGES_BRANCH=main
```

托管在 Cloudflare Pages（项目 `mian-12h`），自定义域名 `www.cryptofinal12.xyz`。
详见 `tools/README.md`。

## 关于站上的数字

首页数据条、关于页的介绍、词条释义，都要求能回到正文逐条核实，**不放任何占位数字**。
官方网站不提前剧透：人物介绍只写身份与性格印象，不写结局。

## 版权

作品为虚构，不构成投资建议。转载全部或部分内容须事先联系作者取得授权。
作者 Tim —— X: https://x.com/T1MCode

本站不发行任何代币，也不承诺任何收益；仅有自愿捐赠。
