#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
《密安十二时辰》阅读站 —— 一键构建 + 部署到 Cloudflare Pages。

用法：
    python tools/cf_deploy.py                  # 重建 site/ -> dist/ 并部署
    python tools/cf_deploy.py --no-build       # 只部署现有 dist/
    python tools/cf_deploy.py -m "改了什么"     # 自定义本次提交说明

凭据：项目根目录 .env.cloudflare（已被 .gitignore 忽略）
      CF_ACCOUNT_ID / CF_API_TOKEN / CF_PAGES_PROJECT / CF_PAGES_BRANCH

实现说明（踩过的坑，别改）：
  1) 部署走官方 wrangler（tools/cfcli 里已装好），**不要**手写 Direct Upload 请求体：
     手写版 manifest 的哈希算法与官方不一致，部署会"成功"但资源全部 500。
  2) 本机环境代理会让 api.cloudflare.com 的 TLS 在代理隧道里握手失败，
     node/curl 都必须先清掉 http(s)_proxy 才能访问 Cloudflare。
"""
import argparse
import os
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BASE_PY = sys.executable
NODE = r"C:\Users\simon\.workbuddy\binaries\node\versions\24.21.0\node.exe"
WRANGLER = os.path.join(ROOT, "tools", "cfcli", "node_modules", "wrangler", "bin", "wrangler.js")


def load_env():
    env = {}
    path = os.path.join(ROOT, ".env.cloudflare")
    if os.path.exists(path):
        for line in open(path, encoding="utf-8"):
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, v = line.split("=", 1)
            env[k.strip()] = v.strip()
    for k in ("CF_ACCOUNT_ID", "CF_API_TOKEN", "CF_PAGES_PROJECT", "CF_PAGES_BRANCH"):
        if os.environ.get(k):
            env[k] = os.environ[k]
    return env


def run(cmd, cwd=None, env=None, label=""):
    if label:
        print("\n$ " + label)
    p = subprocess.run(cmd, cwd=cwd, env=env, shell=False)
    return p.returncode


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--no-build", action="store_true", help="跳过构建，直接部署现有 dist/")
    ap.add_argument("-m", "--message", default="", help="本次部署说明")
    args = ap.parse_args()

    env = load_env()
    acc = env.get("CF_ACCOUNT_ID")
    token = env.get("CF_API_TOKEN")
    project = env.get("CF_PAGES_PROJECT", "mian-12h")
    branch = env.get("CF_PAGES_BRANCH", "main")
    if not acc or not token:
        print("✗ 缺少 CF_ACCOUNT_ID / CF_API_TOKEN（写在 .env.cloudflare 里）")
        return 2

    # 1) 构建
    if not args.no_build:
        rc = run([BASE_PY, os.path.join(ROOT, "site", "build.py")], cwd=os.path.join(ROOT, "site"))
        if rc != 0:
            print("✗ 构建失败，已中止部署")
            return rc

    dist = os.path.join(ROOT, "dist")
    if not os.path.isdir(dist):
        print("✗ 找不到 dist/")
        return 2

    # 2) 部署（清掉代理，Cloudflare 必须直连）
    cenv = dict(os.environ)
    for k in ("http_proxy", "https_proxy", "HTTP_PROXY", "HTTPS_PROXY", "all_proxy", "ALL_PROXY"):
        cenv.pop(k, None)
    cenv["CLOUDFLARE_API_TOKEN"] = token
    cenv["CLOUDFLARE_ACCOUNT_ID"] = acc
    cenv["CI"] = "true"

    cmd = [NODE, WRANGLER, "pages", "deploy", dist,
           "--project-name=" + project, "--branch=" + branch, "--commit-dirty=true"]
    if args.message:
        cmd += ["--commit-message", args.message]
    rc = run(cmd, cwd=ROOT, env=cenv, label="node wrangler pages deploy")
    if rc != 0:
        print("✗ 部署失败")
        return rc

    print("\n✓ 已上线： https://%s.pages.dev" % project)
    return 0


if __name__ == "__main__":
    sys.exit(main())
