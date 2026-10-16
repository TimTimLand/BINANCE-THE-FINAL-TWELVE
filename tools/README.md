# tools/ —— 构建与部署工具（都不随站点上线）

| 脚本 | 用途 |
|---|---|
| `make_kindle.py` | 生成 Kindle 版 PDF（Kindle Voyage 1:1 版式，详见根 README） |
| `cf_deploy.py` | 构建 + 推送 Cloudflare Pages |
| `cfcli/` | 官方 wrangler 的本地安装目录 |

---

## 一键发布

```bash
./deploy.sh "本次改了什么"        # 构建 site/ → 直传 Cloudflare Pages
```

等价于：

```bash
python site/build.py                       # 生成 dist/
python tools/cf_deploy.py -m "说明"        # 上传 dist/
python tools/cf_deploy.py --no-build       # 只上传，不重建
```

线上地址：**https://www.cryptofinal12.xyz**（项目从属自有域名，已在 Cloudflare 绑定并生效）
Pages 自带地址：https://mian-12h.pages.dev

## 凭据

`.env.cloudflare`（已被 `.gitignore` 的 `**/.env*` 忽略，不会进仓库）：

```
CF_ACCOUNT_ID=...
CF_API_TOKEN=...
CF_PAGES_PROJECT=mian-12h
CF_PAGES_BRANCH=main
```

## 两部分依赖

| 组件 | 位置 | 说明 |
|---|---|---|
| Python | 系统 Python 3.13 | 只跑 `site/build.py` 与 `cf_deploy.py` 本身 |
| wrangler | `tools/cfcli/node_modules` | 官方 Cloudflare CLI，负责实际上传 |

若 `tools/cfcli/node_modules` 丢失：

```bash
cd tools/cfcli && npm install wrangler
```

## 两个坑（别踩）

1. **不要手写 Direct Upload 请求体。** 手写的 multipart 上传会返回 success、路径也看似注册成功，但
   所有资源一律 500（官方 manifest 的哈希算法与手写版不同）。一律走 wrangler。
2. **本机环境代理会让 `api.cloudflare.com` 的 TLS 握手失败。** 脚本里已自动清掉 `http(s)_proxy`；
   手工用 curl 排查时记得加 `--noproxy '*' -4`。

## 其他

- 换自有域名：改 `site/data/config.json` 的 `siteUrl` 一处，重跑 `./deploy.sh`；
  Cloudflare Dashboard → Pages → mian-12h → Custom domains 里绑定域名（当前已绑 `www.cryptofinal12.xyz`，
  裸域 `cryptofinal12.xyz` 还没绑，要的话加一条即可，zone 已在本账户）。
- 上传包（给不想用脚本的场景）：`dist/` 目录，或 `mian-12h-site-YYYYMMDD.zip`，在 Cloudflare Pages
  的 Direct Upload 界面拖进去即可。
