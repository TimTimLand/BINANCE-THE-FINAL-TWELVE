#!/usr/bin/env bash
# 《密安十二时辰》阅读站 —— 构建 + 推送 Cloudflare Pages
# 用法： ./deploy.sh  ["本次改动说明"]
set -e
cd "$(dirname "$0")"
exec "C:/Users/simon/.workbuddy/binaries/python/versions/3.13.12/python.exe" tools/cf_deploy.py ${1:+-m "$1"}
