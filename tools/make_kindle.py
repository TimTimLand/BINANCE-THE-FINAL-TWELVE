#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
《密安十二时辰》→ Kindle 版 PDF 生成器

用法：
    python tools/make_kindle.py                 # 生成带日期的 PDF + 一份最新.pdf
    python tools/make_kindle.py --no-whisper    # 不含【0xTim 的低语】
    python tools/make_kindle.py --no-numbers    # 不加盖页码
    python tools/make_kindle.py --font-size 11  # 改正文字号（默认 10pt）

产出： dist-book/密安十二时辰-Kindle版-YYYYMMDD.pdf

实现路线（别改成别的）：
  生成"印刷向"单页 HTML → 无头 Chrome --print-to-pdf 打印。
  这样中文排版、标点是浏览器排版引擎做的，比手写 PDF 坐标可靠得多，
  而且字体直接用系统宋体，矢量文本在 Kindle 上缩放不发虚。
  页码是 Chrome 之后用 reportlab 逐页加盖的（Chrome 不支持 @page 边距盒）。

版式针对 **Kindle Voyage / Paperwhite 3**：6 吋、1448×1072、300ppi，
屏幕可视区约 90.7mm × 122.6mm。这里把页面设成 91×123mm，1:1 不被缩放，
正文区约 74mm × 104mm，每行约 20 字。

防扩散处理（作者要求）：正文之外带封面、版权页、虚构声明、官方网址与作者 X，
PDF 元数据也写了版权与来源网址。
"""
import argparse
import datetime
import glob
import html as html_mod
import os
import re
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
NOVEL_DIR = r"D:\work\AINovel\长篇《密安十二时辰》"
SITE_DIR = os.path.join(ROOT, "site")
OUT_DIR = os.path.join(ROOT, "dist-book")
CHROME = r"C:\Users\simon\AppData\Local\ms-playwright\chromium-1228\chrome-win64\chrome.exe"

SITE_URL = "https://www.cryptofinal12.xyz"
AUTHOR_X = "https://x.com/T1MCode"
AUTHOR = "Tim（0xTim）"

# ---- 版式参数 ----
PAGE_W, PAGE_H = "91mm", "123mm"   # Kindle Voyage 6 吋屏 1:1
FONT_SIZE = 10.0                    # pt，正文
LINE_HEIGHT = 1.75


# ---------------- 读取正文 ----------------
def chapter_files():
    """返回 [(集号, 文件路径)] —— 注意文件号与集数错开 4 位（WB_15=第12集）"""
    out = []
    for i in range(1, 27):
        code = "WB_01" if i == 1 else "WB_%02d" % (i + 3)
        fs = glob.glob(os.path.join(NOVEL_DIR, code + "_第%02d集*" % i + ".md"))
        if fs:
            out.append((i, fs[0]))
        else:
            print("  ⚠ 缺第 %d 集" % i)
    return out


def inline(s):
    """行内：去站内标记/外链 → 文本；**粗** → strong；*斜* → em"""
    s = html_mod.escape(s)
    s = re.sub(r"\[([^\]]*)\]\(#[a-z]+/[^)]*\)", r"\1", s)     # #wiki/ #price/ ...
    s = re.sub(r"\[([^\]]*)\]\((https?://[^)]*)\)", r"\1", s)  # 外链
    s = re.sub(r"\*\*([^*]+)\*\*", r"<strong>\1</strong>", s)
    s = re.sub(r"(?<!\*)\*([^*]+)\*(?!\*)", r"<em>\1</em>", s)
    return s


def parse_chapter(path):
    """把一集 md 解析成块列表：('title'|'shichen'|'sec'|'p'|'quote'|'coda'|'whisper-h'|'whisper-p', html)"""
    text = open(path, encoding="utf-8").read()
    lines = text.split("\n")
    # 去掉可能的 YAML front-matter
    if lines and lines[0].strip() == "---":
        for k in range(1, len(lines)):
            if lines[k].strip() == "---":
                lines = lines[k + 1:]
                break

    blocks = []
    title = ""
    para = []
    quote = []
    in_whisper = False

    def flush_para():
        if para:
            blocks.append(("p", inline("".join(para))))
            para.clear()

    def flush_quote():
        if not quote:
            return
        joined = [inline(x) for x in quote]
        first = " ".join(joined[:2])
        if "时辰牌" in first:
            blocks.append(("shichen", joined))
        elif "本集楔" in first or "更筹" in first:
            blocks.append(("coda", joined))
        elif in_whisper:
            blocks.append(("whisper-p", joined))
        else:
            blocks.append(("quote", joined))
        quote.clear()

    for ln in lines:
        s = ln.rstrip()
        st = s.strip()
        if not st:
            flush_para()
            flush_quote()
            continue
        if st.startswith("# "):
            title = st[2:].strip()
            continue
        if st.startswith("## "):
            flush_para(); flush_quote()
            h = st[3:].strip()
            if "低语" in h:
                in_whisper = True
                blocks.append(("whisper-h", inline(h)))
            else:
                in_whisper = False
                blocks.append(("sec", inline(h)))
            continue
        if st.startswith(">"):
            flush_para()
            quote.append(re.sub(r"^\s*>\s?", "", s))
            continue
        if set(st) <= {"-"} and len(st) >= 3:
            flush_para(); flush_quote()
            continue
        flush_quote()
        para.append(st)
    flush_para(); flush_quote()
    return title, blocks


# ---------------- 取网站「关于」各段文字（单一来源，站书一致） ----------------
def site_text():
    sys.path.insert(0, SITE_DIR)
    import build as site_build  # 有 __main__ 保护，导入不会触发构建
    from bs4 import BeautifulSoup

    def parts(htmlsrc):
        soup = BeautifulSoup(htmlsrc.replace("%s", ""), "html.parser")
        for sel in [".crumb", ".rule", "script", "style"]:
            for e in soup.select(sel):
                e.decompose()
        out = []
        for el in soup.find_all(["p", "h2", "h3", "h4"]):
            t = el.get_text(" ", strip=True)
            if t:
                out.append((el.name, t))
        return out

    cfg = {}
    try:
        import json
        cfg = json.load(open(os.path.join(SITE_DIR, "data", "config.json"), encoding="utf-8"))
    except Exception:
        pass
    return {
        "story": parts(site_build.ABOUT_INTRO),
        "author": parts(site_build.AUTHOR_SECTION),
        "rights": parts(site_build.RIGHTS_SECTION),
        "donate": parts(site_build.DONATE_SECTION),
        "people": site_build.PEOPLE,
        "addr": (cfg.get("channels") or [{}])[0].get("address", ""),
    }


# ---------------- HTML ----------------
CSS = """
@page{ size:%(pw)s %(ph)s; margin:10mm 8.5mm 9mm; }
*{box-sizing:border-box}
html,body{margin:0;padding:0}
body{font-family:"宋体",SimSun,"Songti SC","Source Han Serif SC",serif;
     font-size:%(fs)spt;line-height:%(lh)s;color:#000;background:#fff;
     text-align:justify;text-justify:inter-ideograph;}
.wrap{max-width:100%%}
/* 封面 */
.cover{page-break-after:always;height:%(cover)s;text-align:center;
       border:0.6pt solid #000;padding:6mm 4mm;display:flex;flex-direction:column;
       justify-content:space-between}
.cover .mark{font-size:8pt;letter-spacing:.3em}
.cover .zh{font-family:"黑体",SimHei,"Heiti SC",sans-serif;font-size:26pt;font-weight:700;
           letter-spacing:.12em;line-height:1.35}
.cover .en{font-size:9pt;letter-spacing:.12em;margin-top:3mm;line-height:1.6}
.cover .by{font-size:10.5pt;margin-top:8mm}
.cover .foot{font-size:8pt;letter-spacing:.08em}
/* 通用 */
h2.sec-h{font-family:"黑体",SimHei,sans-serif;font-size:12pt;text-align:center;
         margin:0 0 5mm;font-weight:700;letter-spacing:.1em}
.rule{border-top:0.5pt solid #000;margin:3mm 0 4mm}
p{margin:0;text-indent:2em}
p.noindent{text-indent:0}
.pblock{margin-bottom:2.2mm}
/* 时辰牌 */
.shichen{text-align:center;font-size:8.6pt;line-height:1.85;margin:0 auto 6mm;
         border-top:0.5pt solid #000;border-bottom:0.5pt solid #000;padding:2.2mm 0;
         max-width:88%%}
.shichen div{text-indent:0}
/* 章节 */
.chapter{page-break-before:always}
.chapter .cn{font-family:"黑体",SimHei,sans-serif;font-size:15pt;font-weight:700;
             text-align:center;letter-spacing:.1em;line-height:1.5;margin-bottom:4mm}
.chapter .num{font-size:9pt;text-align:center;letter-spacing:.2em;margin-bottom:2mm}
/* 小节 */
.sec{font-family:"黑体",SimHei,sans-serif;font-size:11pt;text-align:center;
     margin:6mm 0 3mm;letter-spacing:.1em;font-weight:700;text-indent:0}
/* 引文 */
.quote{margin:3mm 0 3mm 6mm;font-size:9.4pt;line-height:1.8;text-indent:0}
/* 低语 */
.whisper-h{font-size:9pt;text-align:center;margin:7mm 0 2mm;letter-spacing:.14em;
           font-family:"黑体",SimHei,sans-serif}
.whisper{margin:0 3mm 2mm;font-size:9pt;line-height:1.8;text-indent:0;
         border-left:0.8pt solid #000;padding-left:3mm}
/* 集尾 */
.coda{text-align:center;font-size:8.6pt;margin:7mm 0 0;text-indent:0}
.coda div{text-indent:0}
/* 目录 */
.toc div.t{font-size:9.4pt;line-height:2.05;text-indent:0;display:flex;
           justify-content:space-between}
/* 版权页 */
.colophon{font-size:8.6pt;line-height:1.8}
.colophon p{text-indent:0;margin-bottom:2.2mm}
.meta{font-size:8.4pt;line-height:1.9;text-indent:0}
.people div.p{font-size:9pt;line-height:1.75;text-indent:0;margin-bottom:2.4mm}
.people b{font-family:"黑体",SimHei,sans-serif}
.addr{font-family:"Courier New",monospace;font-size:8pt;word-break:break-all;
      border:0.5pt solid #000;padding:1.5mm;margin:2mm 0;text-indent:0}
.end{text-align:center;font-size:9pt;line-height:2;margin-top:12mm;text-indent:0}
"""


def esc_parts(parts):
    """[(tag,text)] → HTML 段落串"""
    out = []
    for tag, t in parts:
        t = html_mod.escape(t)
        t = re.sub(r"\*\*([^*]+)\*\*", r"<strong>\1</strong>", t)
        if tag == "p":
            out.append('<p class="pblock">%s</p>' % t)
        else:
            out.append('<h2 class="sec-h">%s</h2>' % t)
    return "\n".join(out)


def build_html(chapters, meta, include_whisper, fs, lh):
    """chapters: [(集号, 文件路径, 标题)]"""
    css = CSS % {"pw": PAGE_W, "ph": PAGE_H, "fs": fs, "lh": lh,
                 "cover": "104mm"}

    def shichen(lines):
        return '<div class="shichen">%s</div>' % "".join("<div>%s</div>" % x for x in lines)

    body = []

    # ---- 封面 ----
    body.append("""<div class="cover">
  <div class="mark">长 篇 小 说</div>
  <div>
    <div class="zh">密安十二时辰</div>
    <div class="en">CRYPTO LISTING: THE FINAL 12<br/>A Novel of the Twenty-Four Hours<br/>Before a Token Goes Live</div>
  </div>
  <div>
    <div class="by">%s　著</div>
    <div class="foot">%s</div>
  </div>
</div>""" % (AUTHOR, SITE_URL))

    # ---- 版权页 ----
    today = datetime.date.today().strftime("%Y 年 %m 月 %d 日")
    body.append("""<div class="colophon">
<h2 class="sec-h">版 权 页</h2>
<div class="rule"></div>
<p><strong>《密安十二时辰》</strong>　%s　著</p>
<p>英文名 CRYPTO LISTING: THE FINAL 12｜本版次 %s 电子版（作者校订用）</p>
<p>本书为虚构作品。书中出现的公司、机构、项目、代币、人物与事件均为虚构，
或为叙事需要而进行的艺术加工，不代表任何真实主体；若与现实中的人、事、机构存在雷同，纯属巧合。
本书内容不构成任何投资建议。</p>
<p><strong>本作品禁止转载。</strong>如需转载全部或部分内容，请先联系作者取得授权：%s。
未获授权，请勿以任何形式转载、搬运或二次发布；任何商业使用须事前签署正式商务合作协议。</p>
<div class="rule"></div>
<p class="meta">官方网站　%s<br/>作者 X（Twitter）　%s<br/>本文件为不对外分发的校订版本，请勿转发。</p>
</div>""" % (AUTHOR, today, AUTHOR_X, SITE_URL, AUTHOR_X))

    # ---- 关于本书 ----
    body.append('<div class="chapter"><h2 class="sec-h">关 于 本 书</h2><div class="rule"></div>'
                + esc_parts(meta["story"]) + "</div>")

    # ---- 人物 ----
    pp = []
    for name, en, desc in meta["people"]:
        nm = ("%s　%s" % (name, en)) if en and en != "—" else name
        pp.append('<div class="p"><b>%s</b>　%s</div>' % (html_mod.escape(nm), html_mod.escape(desc)))
    body.append('<div class="chapter people"><h2 class="sec-h">人 物</h2><div class="rule"></div>'
                + "\n".join(pp) + "</div>")

    # ---- 目录 ----
    toc = []
    for num, _path, title in chapters:
        t = title.split("·")[-1].strip() if "·" in title else title
        toc.append('<div class="t"><span>第 %d 集　%s</span><span>%d</span></div>' % (num, html_mod.escape(t), num))
    body.append('<div class="chapter toc"><h2 class="sec-h">目 录</h2><div class="rule"></div>'
                + "\n".join(toc) + "</div>")

    # ---- 正文 ----
    for num, path, title in chapters:
        title, blocks = parse_chapter(path)
        sub = title.split("·")[-1].strip() if "·" in title else title
        b = ['<div class="chapter">']
        b.append('<div class="num">第 %d 集</div>' % num)
        b.append('<div class="cn">%s</div>' % html_mod.escape(sub))
        for kind, val in blocks:
            if kind == "shichen":
                b.append(shichen(val))
            elif kind == "sec":
                b.append('<div class="sec">%s</div>' % val)
            elif kind == "p":
                b.append('<p class="pblock">%s</p>' % val)
            elif kind == "quote":
                b.append('<div class="quote">%s</div>' % "<br/>".join(val))
            elif kind == "coda":
                b.append('<div class="coda">%s</div>' % "".join("<div>%s</div>" % x for x in val))
            elif kind == "whisper-h":
                if include_whisper:
                    b.append('<div class="whisper-h">%s</div>' % val)
            elif kind == "whisper-p":
                if include_whisper:
                    b.append('<div class="whisper">%s</div>' % "<br/>".join(val))
        b.append("</div>")
        body.append("\n".join(b))

    # ---- 关于作者 ----
    body.append('<div class="chapter">' + esc_parts(meta["author"]) + "</div>")
    # ---- 版权与合作 ----
    body.append('<div class="chapter">' + esc_parts(meta["rights"]) + "</div>")
    # ---- 捐助 ----
    body.append('<div class="chapter">' + esc_parts(meta["donate"])
                + ('<div class="addr">%s</div>' % meta["addr"] if meta["addr"] else "") + "</div>")
    # ---- 封底 ----
    body.append("""<div class="chapter end">
<div class="rule"></div>
在本书里，更筹是夜间报时的签。<br/>
有人投下它，是为了叫醒别人；<br/>
有人投下它，只是为了确认夜还很长。
<div class="rule"></div>
官方网站　%s<br/>
作者 X（Twitter）　%s
</div>""" % (SITE_URL, AUTHOR_X))

    return """<!DOCTYPE html><html lang="zh-CN"><head><meta charset="utf-8"/>
<title>密安十二时辰 · Kindle 版</title>
<meta name="author" content="%s"/>
<style>%s</style></head><body>
%s
</body></html>""" % (AUTHOR, css, "\n".join(body))


# ---------------- 打印与页码 ----------------
def print_pdf(html_path, pdf_path):
    cmd = [CHROME, "--headless=new", "--disable-gpu", "--no-sandbox",
           "--no-pdf-header-footer", "--disable-extensions",
           "--print-to-pdf=" + pdf_path,
           "file:///" + html_path.replace("\\", "/")]
    p = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=600)
    if p.returncode != 0 or not os.path.exists(pdf_path):
        print(p.stdout.decode("utf-8", "replace")[:800])
        raise RuntimeError("Chrome 打印失败")
    return os.path.getsize(pdf_path)


def stamp_numbers(pdf_path, out_path, chapters):
    """加盖页码 + 章节书签（需要 pypdf / reportlab）"""
    try:
        from pypdf import PdfReader, PdfWriter
        from reportlab.pdfgen import canvas as rl_canvas
        from reportlab.lib.units import mm
    except Exception as e:
        print("  ⚠ 缺少 pypdf/reportlab，跳过页码：", e)
        return pdf_path

    rd = PdfReader(pdf_path)
    n = len(rd.pages)
    pw = float(rd.pages[0].mediabox.width)
    ph = float(rd.pages[0].mediabox.height)

    # 页码层
    tmp = out_path + ".num.pdf"
    c = rl_canvas.Canvas(tmp, pagesize=(pw, ph))
    for i in range(n):
        if i >= 3:  # 封面/版权/关于本书不加页码
            c.setFont("Helvetica", 7.2)
            c.drawCentredString(pw / 2.0, 5.2 * mm, str(i + 1))
        c.showPage()
    c.save()

    wr = PdfWriter()
    numrd = PdfReader(tmp)
    # 定位每集起始页（用页面文本特征）
    marks = {}
    for i, pg in enumerate(rd.pages):
        try:
            t = pg.extract_text() or ""
        except Exception:
            t = ""
        m = re.search(r"第\s*(\d+)\s*集", t)
        if m and t.strip().startswith("第"):
            k = int(m.group(1))
            if k not in marks and i > 3:
                marks[k] = i
    for i, pg in enumerate(rd.pages):
        pg.merge_page(numrd.pages[i])
        wr.add_page(pg)
    for num in sorted(marks):
        wr.add_outline_item("第 %d 集" % num, marks[num])
    # 溯源元数据：文件流出后也能查到出处与作者
    wr.add_metadata({
        "/Title": "密安十二时辰（CRYPTO LISTING: THE FINAL 12）",
        "/Author": AUTHOR,
        "/Subject": "长篇小说 · 作者校订用 PDF（禁止转载）",
        "/Keywords": "%s | %s | 禁止转载" % (SITE_URL, AUTHOR_X),
        "/Creator": "mian-12h-website/tools/make_kindle.py",
    })
    with open(out_path, "wb") as f:
        wr.write(f)
    os.remove(tmp)
    return out_path


# ---------------- 主流程 ----------------
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--no-whisper", action="store_true", help="不含【0xTim 的低语】")
    ap.add_argument("--no-numbers", action="store_true", help="不加盖页码")
    ap.add_argument("--font-size", type=float, default=FONT_SIZE)
    ap.add_argument("--line-height", type=float, default=LINE_HEIGHT)
    args = ap.parse_args()

    os.makedirs(OUT_DIR, exist_ok=True)
    print("读取正文…")
    files = chapter_files()
    chapters = []
    for num, path in files:
        title, _ = parse_chapter(path)
        chapters.append((num, path, title))
    print("  共 %d 集" % len(chapters))

    print("读取网站「关于」内容…")
    meta = site_text()

    html = build_html(chapters, meta,
                      include_whisper=not args.no_whisper,
                      fs=args.font_size, lh=args.line_height)
    tmp_html = os.path.join(OUT_DIR, "_kindle_src.html")
    open(tmp_html, "w", encoding="utf-8").write(html)
    print("  排版 HTML：%s（%.1f MB）" % (tmp_html, len(html) / 1048576))

    today = datetime.date.today().strftime("%Y%m%d")
    raw = os.path.join(OUT_DIR, "_raw.pdf")
    print("打印 PDF…")
    sz = print_pdf(tmp_html, raw)
    print("  原始 %.2f MB" % (sz / 1048576))

    dated = os.path.join(OUT_DIR, "密安十二时辰-Kindle版-%s.pdf" % today)
    final = os.path.join(OUT_DIR, "密安十二时辰-Kindle版-最新.pdf")
    if args.no_numbers:
        os.replace(raw, dated)
    else:
        stamp_numbers(raw, dated, chapters)
        if os.path.exists(raw):
            os.remove(raw)

    import shutil
    shutil.copyfile(dated, final)
    print("\n✓ 完成：")
    for p in (dated, final):
        print("  %s  (%.2f MB)" % (p, os.path.getsize(p) / 1048576))
    try:
        from pypdf import PdfReader
        r = PdfReader(dated)
        print("  页数：%d　页面尺寸：%.1f × %.1f pt（= %.1f × %.1f mm）"
              % (len(r.pages), float(r.pages[0].mediabox.width), float(r.pages[0].mediabox.height),
                 float(r.pages[0].mediabox.width) / 72 * 25.4, float(r.pages[0].mediabox.height) / 72 * 25.4))
    except Exception:
        pass


if __name__ == "__main__":
    main()
