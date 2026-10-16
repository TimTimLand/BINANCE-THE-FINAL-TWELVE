# -*- coding: utf-8 -*-
"""
《密安十二时辰》静态站点生成器 v1
读源稿 WB_*.md（D:\\work\\AINovel\\长篇《密安十二时辰》），
生成静态站到 site/（index / episodes / wiki / rights / donate / about）。
纯静态，无依赖。
"""
import os, re, json, html, glob, shutil, time

SRC = r"D:\work\AINovel\长篇《密安十二时辰》"
OUT = os.path.dirname(os.path.abspath(__file__))

# ---------------- 工具 ----------------
def esc(t):
    return html.escape(t, quote=False)

def attr_esc(t):
    return html.escape(str(t), quote=True)

# 内联浮层词典（site/data/glossary.json）；构建时烘进 HTML，站点仍是纯静态、无需运行时请求
GLOSS = {}
def load_glossary():
    global GLOSS
    try:
        with open(os.path.join(OUT, "data", "glossary.json"), encoding="utf-8") as f:
            g = json.load(f)
        GLOSS = {k.lower(): v for k, v in g.items() if not k.startswith("_")}
    except Exception as e:
        print("glossary load failed:", e)
        GLOSS = {}

def _tip_attrs(g):
    a = []
    if g.get("t"):         a.append('data-t="%s"' % attr_esc(g["t"]))
    if g.get("d"):         a.append('data-def="%s"' % attr_esc(g["d"]))
    if g.get("url"):       a.append('data-url="%s"' % attr_esc(g["url"]))
    if g.get("urlLabel"):  a.append('data-url-label="%s"' % attr_esc(g["urlLabel"]))
    if g.get("fic"):       a.append('data-fic="1"')
    return (" " + " ".join(a)) if a else ""

def _link(m, root):
    text, url = m.group(1), m.group(2)
    # 概念/标的：浮层解释（真实标的在浮层里给外链）
    if url.startswith("#wiki/"):
        g = GLOSS.get(url[6:].strip("/").lower(), {})
        cls = "term has-tip" if g else "term"
        return '<span class="%s"%s tabindex="0">%s</span>' % (cls, _tip_attrs(g), text)
    # 真实世界的公链 / 交易所：直接连官网，同时悬浮给一句解释
    if url.startswith("#link/"):
        g = GLOSS.get(url[6:].strip("/").lower(), {})
        href = g.get("url") or "#"
        return '<a class="wl has-tip" href="%s" target="_blank" rel="noopener"%s>%s</a>' % (esc(href), _tip_attrs(g), text)
    # 价格 / 交易对 / 项目：角标样式 + 浮层
    if url.startswith("#price/"):
        g = GLOSS.get(url[7:].strip("/").lower(), {})
        return '<span class="chip chip-price has-tip"%s>%s</span>' % (_tip_attrs(g), text)
    if url.startswith("#trade/"):
        g = GLOSS.get(url[7:].strip("/").lower(), {})
        return '<span class="chip chip-trade has-tip"%s>%s</span>' % (_tip_attrs(g), text)
    if url.startswith("#project/"):
        g = GLOSS.get(url[9:].strip("/").lower(), {})
        if not g:
            g = {"t": text, "d": "书中虚构的项目，现实中并不存在。", "fic": True}
        return '<span class="chip chip-project has-tip"%s>%s</span>' % (_tip_attrs(g), text)
    return '<a href="%s">%s</a>' % (url, text)

def inline(t, root=""):
    t = esc(t)
    t = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", t)
    t = re.sub(r"(?<!\*)\*([^*]+?)\*(?!\*)", r"<em>\1</em>", t)
    t = re.sub(r"\[([^\]]+)\]\(([^)]+)\)", lambda m: _link(m, root), t)
    t = t.replace("`", "")
    return t

def md_to_blocks(md, root=""):
    """极简 md -> blocks；块类型：h2 / p / quote / hr"""
    lines = md.split("\n")
    blocks, buf, qbuf = [], [], []
    def flush_p():
        if buf:
            blocks.append(("p", inline(" ".join(buf).strip(), root)))
            buf.clear()
    def flush_q():
        if qbuf:
            blocks.append(("quote", "\n".join(qbuf)))
            qbuf.clear()
    for raw in lines:
        ln = raw.rstrip()
        s = ln.strip()
        if not s:
            flush_p(); flush_q(); continue
        if s.startswith("## "):
            flush_p(); flush_q(); blocks.append(("h2", s[3:].strip())); continue
        if s.startswith("# "):
            flush_p(); flush_q(); continue  # 标题由模板渲染
        if set(s) <= set("-—") and len(s) >= 3:
            flush_p(); flush_q(); blocks.append(("hr", "")); continue
        if s.startswith(">"):
            flush_p()
            qbuf.append(s[1:].strip())
            continue
        flush_q()
        buf.append(s)
    flush_p(); flush_q()
    return blocks

def render_blocks(blocks, root=""):
    out, first_quote = [], True
    for kind, val in blocks:
        if kind == "h2":
            out.append('<h2>%s</h2>' % inline(val, root))
        elif kind == "hr":
            out.append("<hr/>")
        elif kind == "p":
            out.append("<p>%s</p>" % val)
        elif kind == "quote":
            cls = ""
            if first_quote and "时辰牌" in val:
                cls = ' class="shichen"'
            first_quote = False
            body = "".join("<p>%s</p>" % inline(x, root) for x in val.split("\n"))
            out.append("<blockquote%s>%s</blockquote>" % (cls, body))
    return "\n".join(out)

def split_whisper(blocks):
    """把【0xTim 的低语】及其之后的块从正文里拆出来（供折叠展示）。"""
    main, whisper = [], []
    for kind, val in blocks:
        if kind == "h2" and "低语" in val:
            whisper.append((kind, val))
            continue
        (whisper if whisper else main).append((kind, val))
    return main, whisper

# 低语模块开关（2026-10-14 用户要求先在网站下线，源稿内容保留不动）
# 置 True 即可恢复：正文末尾重新出现折叠条 + 右侧 ✦ 按钮
SHOW_WHISPER = False

WHISPER_BTN = ('<button class="utt-btn" id="whisperBtn" type="button" '
               'aria-label="0xTim 的低语" title="0xTim 的低语" '
               'aria-expanded="false" hidden>✦</button>')

def render_whisper(blocks, root=""):
    """低语折叠块：默认隐藏，读者主动点击才展开。"""
    if not blocks:
        return ""
    inner = render_blocks(blocks, root)
    return """
<div class="whisper-wrap">
  <button class="whisper-toggle" type="button" aria-expanded="false" aria-controls="whisper">
    <span class="wt-mark" aria-hidden="true">✦</span>
    <span class="wt-text">0xTim 的低语</span>
    <span class="wt-hint">展开</span>
  </button>
  <section class="whisper" id="whisper" hidden>
    <div class="whisper-inner">%s</div>
  </section>
</div>""" % inner

# ---------------- 读取源稿 ----------------
CN = ["零","一","二","三","四","五","六","七","八","九","十"]
def cn_num(n):
    if n <= 10: return CN[n]
    if n < 20: return "十" + CN[n-10]
    return CN[n//10] + "十" + (CN[n%10] if n % 10 else "")

def load_episodes():
    eps = {}
    for path in glob.glob(os.path.join(SRC, "WB_*.md")):
        base = os.path.basename(path)
        if not re.match(r"WB_\d+_第\d+集", base):
            continue
        with open(path, encoding="utf-8") as f:
            md = f.read()
        m = re.search(r"^#\s*第\s*0*(\d+)\s*集\s*[·•．.]\s*(.+)$", md.split("\n")[0].strip())
        if not m:
            m2 = re.search(r"第\s*0*(\d+)\s*集\s*[·•．.]\s*([^\n\r]+)", md)
            if not m2: continue
            num, title = int(m2.group(1)), m2.group(2).strip()
        else:
            num, title = int(m.group(1)), m.group(2).strip()
        title = re.sub(r"\s+", "", title)
        sc = re.search(r"第\s*\d+\s*集\s*[·•．.]\s*([子丑寅卯辰巳午未申酉戌亥])\s*时", md)
        shichen = (sc.group(1) + "时") if sc else ""
        cd = re.search(r"距\s*GCT\s*上币[：:]\s*([0-9]{2}\s*小时[^\n]*)", md)
        countdown = cd.group(1).strip() if cd else ""
        eps[num] = {"n": num, "title": title, "shichen": shichen,
                    "countdown": countdown, "blocks": md_to_blocks(md, "../")}
    return eps

# ---------------- 站点配置 ----------------
CFG_PATH = os.path.join(OUT, "data", "config.json")
CUR_CFG = {"channels": []}   # main() 里装载 config.json 后写入，供 render_page 生成捐助浮层
def load_cfg():
    try:
        with open(CFG_PATH, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {"channels": []}

def addr_html(cfg, compact=False):
    ch = [c for c in cfg.get("channels", []) if c.get("address")]
    if not ch:
        return ('<p class="pending">捐赠地址正在整理中，不日公布。本网站不发行任何代币，'
                '也不接受任何以“投资/返利”为名的转账。</p>')
    rows = []
    for c in ch:
        lab = c.get("label")
        lab_html = '<div class="lb">%s</div>' % esc(lab) if lab else ""
        rows.append(
            '<div class="row"><span class="ch">%s</span><span class="ad">%s</span>'
            '<span class="cp">复制</span></div>%s' % (esc(c.get("chain", "")), esc(c["address"]), lab_html))
    return '<div class="addr">%s</div>' % "".join(rows)

# ---- 捐助：快捷金额（页面只占一行）+ 浮层（金额可调 / 选链 / 唤起钱包转账）----
# 「U」= USDT。浮层里的链与合约地址（2026-10-15 已对 Tether 官方页面核实）：
#   以太坊  0xdAC17F958D2ee523a2206206994597C13D831ec7  6 位小数（Tether 官方发行）
#   BNB    0x55d398326f99059fF775485246999027B3197955  18 位小数（BSC 上的发行版，非 Tether 直发，小数位不同！）
#   Polygon 0xc2132D05D31c914a87C6611C10748AEb04B58e8F  6 位小数
#   Arbitrum 0xFd086bC7CD5C481DCC9C85ebE478A1C0b69FCbb9 6 位小数
DONATE_CHIPS = """<div class="dchips">
  <button type="button" class="dchip" data-donate="5">5U</button>
  <button type="button" class="dchip" data-donate="10">10U</button>
  <button type="button" class="dchip" data-donate="20">20U</button>
  <button type="button" class="dchip" data-donate="100">100U</button>
</div>"""

DONATE_MODAL = """<div class="dmodal" id="donateModal" hidden>
  <div class="dm-veil" data-dm-close></div>
  <div class="dm-box" role="dialog" aria-modal="true" aria-label="捐助">
    <button class="dm-x" type="button" data-dm-close aria-label="关闭">✕</button>
    <h3 class="dm-h">捐 助</h3>
    <p class="dm-sub">本站不发行代币，不做任何投资承诺。选好金额与网络，点下方按钮唤起钱包转账。</p>

    <div class="dm-lb">金额</div>
    <div class="dm-amt">
      <input id="dmAmount" type="text" inputmode="decimal" autocomplete="off" value="5" aria-label="捐助金额（USDT）"/>
      <span class="dm-unit">USDT</span>
      <span class="dm-step">
        <button type="button" data-dm-step="1" aria-label="增加 1U">▲</button>
        <button type="button" data-dm-step="-1" aria-label="减少 1U">▼</button>
      </span>
    </div>
    <div class="dm-quick">
      <button type="button" data-dm-set="5">5U</button>
      <button type="button" data-dm-set="10">10U</button>
      <button type="button" data-dm-set="20">20U</button>
      <button type="button" data-dm-set="100">100U</button>
    </div>

    <div class="dm-lb">转账网络</div>
    <div class="dm-chains">
      <button type="button" data-dm-chain="1">以太坊</button>
      <button type="button" data-dm-chain="56">BNB Chain</button>
      <button type="button" data-dm-chain="137">Polygon</button>
      <button type="button" data-dm-chain="42161">Arbitrum</button>
    </div>

    <div class="addr dm-addr">%s</div>
    <p class="dm-tip">仅支持 EVM 网络。请勿从波场（TRC-20）等非 EVM 网络转入，地址不通用。若钱包未自动弹出，可复制上方地址手动转账。</p>
    <div class="dm-acts">
      <button type="button" class="btn ghost" data-dm-close>取消</button>
      <a class="btn" id="dmGo" href="#" rel="noopener">打开钱包转账</a>
    </div>
  </div>
</div>"""

def donate_modal(cfg):
    ch = [c for c in cfg.get("channels", []) if c.get("address")]
    if ch:
        c = ch[0]
        row = ('<div class="row"><span class="ch">%s</span><span class="ad">%s</span>'
               '<span class="cp">复制</span></div>') % (esc(c.get("chain", "EVM")), esc(c["address"]))
    else:
        row = '<p class="pending">捐助地址正在整理中。</p>'
    return DONATE_MODAL % row

def donate_box(root, cfg):
    return """
<div class="donate">
  <h3>捐助 · 让这个故事被更多人读到的成本，由愿意的人一起扛</h3>
  %s
  <p>本站不发行代币、不做任何投资承诺。若你愿意为这部作品的写作与运营出一份力，可向下方地址捐助。</p>
  %s
  <p style="margin-top:14px"><a href="%sabout.html#donate">捐助方式与说明 →</a></p>
</div>""" % (DONATE_CHIPS, addr_html(cfg), root)

NAV = [("index.html", "首页"), ("index.html#toc", "阅读"), ("about.html", "关于")]

def header(root, active=""):
    items = []
    for href, label in NAV:
        cls = ' class="on"' if active and href.startswith(active) else ""
        items.append('<a href="%s%s"%s>%s</a>' % (root, href, cls, label))
    return """<header class="site"><div class="hd">
  <a class="logo" href="%sindex.html"><img class="logo-img" src="%sassets/images/logo.png" alt="密安十二时辰"/><b>密安十二时辰</b><span>CRYPTO LISTING · THE FINAL 12</span></a>
  <nav class="main">%s</nav>
</div></header>""" % (root, root, "".join(items))

def footer(root, cfg):
    return """<footer class="site"><div class="wrap">
  <div class="fgrid">
    <div>
      <h4>关于这部作品</h4>
      <p>《密安十二时辰》是一部以加密货币行业为背景的虚构小说。故事、人物、机构、项目与代币均为虚构，如有雷同纯属巧合。</p>
      <p>全书不构成任何投资建议。文中出现的价格与行情为情节设定，请勿据此决策。</p>
    </div>
    <div>
      <h4>阅读</h4>
      <ul>
        <li><a href="%sindex.html#toc">全部 26 集</a></li>
        <li><a href="%sabout.html">关于本书与作者</a></li>
        <li><a href="%sabout.html#rights">版权与合作</a></li>
      </ul>
    </div>
    <div>
      <h4>捐助与共建</h4>
      <p>本站仅接受自愿捐助，不发行任何代币、不做任何收益承诺。</p>
      <p><a href="%sabout.html#donate">查看捐助方式 →</a></p>
    </div>
  </div>
  <div class="copy">
    <span>© 2026 《密安十二时辰》CRYPTO LISTING: THE FINAL 12. 保留所有权利。</span>
    <span>本作品禁止转载（转载需先获授权）；欢迎共建与各类正式合作，详见 <a href="%sabout.html#rights">版权与合作说明</a>。</span>
  </div>
</div></footer>
<script src="%sassets/app.js"></script>""" % (root, root, root, root, root, root)

PAGE = """<!DOCTYPE html>
<html lang="zh-CN"><head>
<meta charset="utf-8"/>
<meta name="viewport" content="width=device-width,initial-scale=1"/>
<title>{title}</title>
<meta name="description" content="{desc}"/>
<link rel="icon" type="image/png" sizes="64x64" href="{root}assets/images/favicon.png"/>
<link rel="apple-touch-icon" sizes="180x180" href="{root}assets/images/apple-touch-icon.png"/>
<meta property="og:type" content="book"/>
<meta property="og:site_name" content="密安十二时辰"/>
<meta property="og:title" content="{title}"/>
<meta property="og:description" content="{desc}"/>
<meta property="og:image" content="{og}"/>
<meta name="twitter:card" content="summary_large_image"/>
<meta name="twitter:image" content="{og}"/>
<script src="{root}assets/theme-init.js"></script>
<link rel="stylesheet" href="{root}assets/style.css"/>
</head><body>
{header}
{body}
{footer}
{donateModal}
<div class="utt" id="utt">
  <button class="utt-btn" id="themeBtn" type="button" aria-label="切换主题" title="切换深浅主题">☀</button>
  <button class="utt-btn" id="musicBtn" type="button" aria-label="背景音乐" title="背景音乐"><span class="eq"><i></i><i></i><i></i></span></button>
  {whisperBtn}
</div>
<audio id="bgm" loop preload="auto" src="{root}assets/music/b12hbgmusic.mp3"></audio>
</body></html>"""

# 站点对外域名（用于 og:image / sitemap 的绝对地址）。
# 优先读 data/config.json 里的 siteUrl；未配置时才用下面的默认值。
# 目标托管：Cloudflare Pages 项目 mian-12h → https://mian-12h.pages.dev
# 将来绑定自有域名（如 mian12h.xyz）时，只改 config.json 的 siteUrl 一处即可。
SITE_URL = "https://mian-12h.pages.dev"
OG_IMAGE = SITE_URL + "/assets/images/og.jpg"

def render_page(**kw):
    kw.setdefault("og", OG_IMAGE)
    kw.setdefault("whisperBtn", WHISPER_BTN if SHOW_WHISPER else "")
    kw.setdefault("donateModal", donate_modal(CUR_CFG))
    return PAGE.format(**kw)

# ---------------- 词条（已取消独立词典页；正文改为内联浮层，词典见 site/data/glossary.json）----------------

# ---------------- 关于页（合并：关于本书 / 五条线与人物 / 作者 / 版权与合作 / 捐助）----------------

# 版权、转载与合作（含“共建”意图）
RIGHTS_SECTION = """<section class="blk" id="rights"><div class="wrap" style="max-width:820px">
  <h3 class="h3">版 权 、 转 载 与 合 作</h3>
  <div class="rule"></div>
  <div class="prose" style="font-size:17px">
  <p><strong>一、本作品禁止转载。</strong>如需转载全部或部分内容，请先联系作者 Tim 取得授权：<a href="https://x.com/T1MCode" target="_blank" rel="noopener">x.com/T1MCode</a>。未获授权，请勿以任何形式转载、搬运或二次发布。</p>
  <p><strong>二、欢迎各类正式合作。</strong>无论是出版、有声、漫画、广播剧，还是电视剧、电影、游戏、动画、剧本杀、舞台剧等改编，我们都持开放态度，愿意坐下来谈。</p>
  <p><strong>三、也欢迎你来一起共建。</strong>如果你被这个故事打动，愿意参与进来把它做得更好——无论参与的是<strong>小说本身</strong>（续写、番外、修订、考据），还是<strong>插图与视觉</strong>（人物设定、场景插画、封面与海报），或是<strong>视频与声音</strong>（短片、动画、配音、配乐、播客）以及翻译——都欢迎通过下方联系渠道找到我们。我们想先认识你，再一起商量怎么合作；共建同样遵循下一条，以正式约定为准。</p>
  <p><strong>四、但我们本身不免费提供版权。</strong>任何以商业为目的的使用（包括但不限于出版发行、影视与游戏改编、付费内容分发、商业品牌联动、AI 训练语料的商业化使用等），均须在事前与我们签署正式商务合作协议后方可进行。</p>
  <p><strong>五、所有合作都走正式的商务流程。</strong>我们不接受口头授权、默认授权、或“先用后补”的方式。合作意向、分成结构、署名方式与授权范围，以双方正式签署的合同为准。</p>
  <p><strong>六、联系方式。</strong>转载授权、合作与共建的意向，请通过作者的 X（Twitter）账号发起：<a href="https://x.com/T1MCode" target="_blank" rel="noopener">x.com/T1MCode</a>。我们会在收到意向后的合理时间内回复。</p>
  </div>
  <div class="donate">
    <h3>关于这部作品的立场</h3>
    <p>本书为虚构作品。书中出现的公司、机构、项目、代币、人物与事件均为虚构，或为叙事需要而进行的艺术加工，不代表任何真实主体。若与现实中的人、事、机构存在雷同，纯属巧合。</p>
  </div>
</div></section>"""

# 作者介绍
AUTHOR_SECTION = """<section class="blk" id="author" style="background:var(--bg-2);border-top:1px solid var(--line);border-bottom:1px solid var(--line)"><div class="wrap" style="max-width:820px">
  <h3 class="h3">关 于 作 者</h3>
  <div class="rule"></div>
  <div class="prose" style="font-size:17px">
  <p>作者笔名 <strong>Tim</strong>（在加密社区也写作 <strong>0xTim</strong>），85 后华人，目前常住马来西亚。</p>
  <p>在区块链技术、区块链行业安全、数字币投资等板块，他都积累了多年的经验，也做出过一系列扎实的成绩；近些年，他把更多的精力放在区块链行业与文学创作的交界处。多年的加密货币行业风控从业经历，让他熟悉这个行业真实的运作逻辑，也清楚它潜在的风险都在哪里、又是如何被一句“不要紧”轻轻地盖过去的。</p>
  <p>他的创作初衷很简单：<strong>用文学作品揭露加密货币行业的真实风险</strong>，写出风控从业者守护用户资产安全的那份责任与担当，为普通投资者留下一点风险警示；同时，也希望能以紧凑的剧情与经得起推敲的专业细节，做出一个既有可读性、又有行业深度的作品。</p>
  </div>
</div></section>"""

# 捐助
DONATE_SECTION = """<section class="blk" id="donate"><div class="wrap" style="max-width:820px">
  <h3 class="h3">捐 助</h3>
  <div class="rule"></div>
  %s
  <div class="prose" style="font-size:17px">
  <p><strong>本站不发行任何代币。</strong>过去我们想过要不要发一个，后来决定不发了。这里没有投资标的，没有认购，没有返利，也没有路线图。</p>
  <p>写作、校对、建站、运营都要成本。如果你喜欢这个故事，愿意让它被更多人读到，可以通过下方的地址捐助我们。不计多少，都记在心里。</p>
  <p>我们不会因为捐助给你任何承诺，也不会用任何形式暗示“早参与有回报”。若将来这部作品真的做起来了，我们会<strong>依据捐赠记录，用“认领（claim）”的方式，回赠一份属于参与者的纪念</strong>——不是空投，不是投资，只是把这份一起走过的记录，还给你。</p>
  <p>请务必注意：<strong>除了本页公布的地址，任何声称能带你“参与本项目、获得回报”的人，都与我们无关。</strong>这个故事写的就是这种事，我们不会自己去做。</p>
  </div>
  <div class="donate">
    <h3>捐助地址</h3>
    <p>下方是一个 <strong>EVM 地址</strong>，在以太坊、BNB Chain、Polygon、Arbitrum、Base 等任意 EVM 链上都可以转入。请务必核对地址后再操作。</p>
    %s
  </div>
</div></section>"""

ABOUT_INTRO = """<div class="read reader" id="story">
<div class="crumb"><a href="index.html">首页</a> / 关于</div>
<h2 class="h">关于《密安十二时辰》</h2>
<div class="rule"></div>
<div class="prose" style="font-size:17px">
<p>这是一个关于“看不见的手”的故事。</p>
<p>故事发生在 2026 年 9 月 17 日早八点，到 9 月 18 日上午十点，前后共二十六个小时——十二个时辰走完，项目上了币；再过两个钟头，才是这一程真正的收尾。一个项目要上币，一群人在等着那个盘口，一个孩子被关在异国的一栋旧楼里。而有些事，在很早以前就已经开始了。</p>
<p>没有人是纯粹的坏人，也没有人是纯粹的好人。做局的人比谁都讲风控，卖货的人有营业执照，改勾的人只改了一个字。而每一个环节，手续都齐全。</p>
<p>这本书想问的，其实只有一件事：<strong>当你处在一个你无法验证任何环节的行业里，“谨慎”到底还剩下多少意义。</strong></p>
</div>
<div class="spoiler-note"><strong>下面还有一点人物说明。</strong>如果你是第一次读这个故事，建议先翻开正文，读完再回来看——有些东西，自己发现，比被人告诉你有意思得多。</div>
</div>"""

# 关于页页内导航（锚点：既方便页内定位，也方便站内外精准跳转到具体模块）
ABOUT_SUBNAV = """<nav class="subnav" aria-label="本页导航"><div class="wrap">
  <span class="sn-lead">本 页</span>
  <a href="#story">关于本书</a>
  <a href="#people">人物</a>
  <a href="#author">作者</a>
  <a href="#rights">版权与合作</a>
  <a href="#donate">捐助</a>
</div></nav>"""

def about_page(cfg):
    people = "".join(
        '<div class="person"><div class="n">%s<em>%s</em></div><div class="d">%s</div></div>' % (n, en, d)
        for n, en, d in PEOPLE)
    body = ABOUT_SUBNAV + ABOUT_INTRO + """
<section class="blk" id="people"><div class="wrap">
  <h3 class="h3">人 物</h3>
  <div class="rule"></div>
  <p class="sub">没有纯粹的坏人，也没有纯粹的好人。只有各自认为自己做得对的人。</p>
  <div class="grid g3">%s</div>
</div></section>""" % people + AUTHOR_SECTION + RIGHTS_SECTION + (DONATE_SECTION % (DONATE_CHIPS, addr_html(cfg)))
    return render_page(title="关于 · 《密安十二时辰》",
                       desc="《密安十二时辰》：故事、人物、作者、版权与合作、捐助方式。",
                       root="", header=header("", "about"),
                       body=body, footer=footer("", cfg))

# ---------------- 404 页（Cloudflare Pages 等静态托管会自动使用根目录的 404.html） ----------------
def notfound_page(cfg):
    body = """<div class="read reader" style="text-align:center;padding-top:64px">
<h2 class="h" style="font-size:52px;letter-spacing:.1em">4 0 4</h2>
<div class="rule" style="margin:16px auto 26px"></div>
<div class="prose" style="font-size:17px">
<p>这个页面不存在。也许它从来没存在过，也许它已经被人搬走了。</p>
<p>链上记录干干净净，签名有效，时间正常，Gas 正常——那笔跳转走得像是你自己点的。这种事，我们这本书里写过不少。</p>
</div>
<div class="cta" style="margin-top:34px">
  <a class="btn" href="/index.html">回到首页</a>
  <a class="btn ghost" href="/index.html#toc">查看全部 26 集</a>
</div>
</div>"""
    return render_page(title="404 · 《密安十二时辰》",
                       desc="页面不存在。",
                       root="/", header=header("/", ""),
                       body=body, footer=footer("/", cfg))

# ---------------- 部署辅助文件（Cloudflare Pages / 通用静态托管） ----------------
# _headers：Cloudflare Pages 自定义响应头（语法错误会被忽略，不会导致构建失败）
# robots.txt / sitemap.xml：搜索引擎收录用；域名统一取 SITE_URL
HEADERS_FILE = """/*
  X-Content-Type-Options: nosniff
  Referrer-Policy: strict-origin-when-cross-origin

/assets/*
  Cache-Control: public, max-age=3600

/assets/images/*
  Cache-Control: public, max-age=604800

/assets/music/*
  Cache-Control: public, max-age=604800

/*.html
  Cache-Control: public, max-age=300
"""

def robots_txt():
    return "User-agent: *\nAllow: /\n\nSitemap: %s/sitemap.xml\n" % SITE_URL

def sitemap_xml(eps, today):
    urls = ['<url><loc>%s/</loc><lastmod>%s</lastmod><priority>1.0</priority></url>' % (SITE_URL, today),
            '<url><loc>%s/about.html</loc><lastmod>%s</lastmod><priority>0.5</priority></url>' % (SITE_URL, today)]
    for i in sorted(eps):
        urls.append('<url><loc>%s/episodes/%02d.html</loc><lastmod>%s</lastmod><priority>0.8</priority></url>'
                    % (SITE_URL, i, today))
    return ('<?xml version="1.0" encoding="UTF-8"?>\n'
            '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n  '
            + "\n  ".join(urls) + "\n</urlset>\n")

# ---------------- 首页 ----------------
PEOPLE = [
 ("凌策","Frank","做风险控制。履历上有一段空白，他不解释，也没人敢多问。真出了事，他是那种先把灯打开、再慢慢数屋子里有几个人的人。"),
 ("周铭","Jason","在这一行摸爬了十二年，只信一件事：别贪。他把这句话写进每一笔操作里，也拿这句话要求身边每一个人。"),
 ("苏婉","Selina","被周铭带进这一行，如今比他更懂这里的水温。她学会了所有人的说话方式，也学会了在每句话后面留一条退路。"),
 ("陈锋","Daniel","星核项目方的运营总监，话不多。他做的每件事都有理由，只是那些理由，他只讲给愿意听的人。"),
 ("老猫","Kevin","吉隆坡的渠道商，这一行他做了十四年。他做的每笔生意都名正言顺——手续齐全，白纸黑字，见了人先笑。"),
 ("冯敬堂","—","第一批矿工，人们叫他“老矿长”。他挖出来的币从没动过，把它们当成年迈之后唯一的底气。"),
 ("罗萍","Ping","前保险代理，人们叫她“萍姐”。她信人，也善于让人信她；为了让客户别亏，她把自己也押了进去。"),
 ("周杰","Jay","刚毕业，算过一笔账：靠工资攒钱，要攒很久很久。他不喜欢赌，只是想快一点，让家里松一口气。"),
 ("沙米尔","Sam","迪拜风控中心的硬件工程师，手稳，话少。他习惯把东西拆开来看——电路、外壳、说明书，一样一样地。"),
 ("曾凯","Neo","赛城的技术负责人，相信代码可以不骗人。他写下的每一行都留了注释，也留了后路。"),
]

def home_page(eps, cfg):
    toc = []
    for i in range(1, 27):
        e = eps.get(i)
        if e:
            toc.append('<a class="ep" href="episodes/%02d.html"><span class="no">%02d</span>'
                       '<span class="tt">%s</span><span class="sc">%s</span></a>' % (i, i, e["title"], e["shichen"]))
        else:
            toc.append('<span class="ep soon"><span class="no">%02d</span><span class="tt">待续</span><span class="sc"></span></span>' % i)
    body = """<div class="hero"><div class="hero-bg" aria-hidden="true"></div><div class="hero-veil" aria-hidden="true"></div><div class="wrap">
  <div class="kicker">一部关于“看不见的手”的行业小说</div>
  <h1>密安十二时辰</h1>
  <div class="en">CRYPTO LISTING : THE FINAL 12</div>
  <p class="tag">2026 年 9 月 17 日早八点，到 9 月 18 日上午十点。<br/>同一口钟下面，有人等一个开盘，有人等一个电话，有人等一扇门打开。</p>
  <div class="cta"><a class="btn" href="episodes/01.html">开始阅读</a>
  <a class="btn ghost" href="#toc">查看全部 26 集</a></div>
</div></div>

<div class="strip"><div class="in">
  <div class="cell"><div class="v">26</div><div class="k">集 · 全书</div></div>
  <div class="cell"><div class="v">12</div><div class="k">时辰</div></div>
  <div class="cell"><div class="v">23</div><div class="k">位人物</div></div>
  <div class="cell"><div class="v">6</div><div class="k">座城市</div></div>
</div></div>

<section class="blk"><div class="wrap" style="max-width:780px">
  <h2 class="h">题 记</h2>
  <div class="rule"></div>
  <p class="lede">没有人是纯粹的坏人，也没有人是纯粹的好人。做局的人比谁都讲风控，卖货的人有营业执照，改勾的人只改了一个字——而每一个环节，手续都齐全。</p>
  <p class="lede">这本书想问的其实只有一件事：当你处在一个你无法验证任何环节的行业里，<strong>“谨慎”到底还剩下多少意义。</strong></p>
</div></section>

<section class="blk" id="toc" style="background:var(--bg-2);border-top:1px solid var(--line);border-bottom:1px solid var(--line)"><div class="wrap">
  <h2 class="h">全 文</h2>
  <div class="rule"></div>
  <p class="sub">共 26 集。从辰时起，到上币之后两个钟头止。</p>
  <div class="toc">%s</div>
  %s
</div></section>""" % ("".join(toc), donate_box("", cfg))
    return render_page(title="密安十二时辰 · CRYPTO LISTING: THE FINAL 12",
                       desc="《密安十二时辰》：一部发生在十二个时辰里的加密货币行业小说。26 集全文在线阅读。",
                       root="", header=header("", ""), body=body, footer=footer("", cfg))

# ---------------- 主流程 ----------------
def main():
    global CUR_CFG, SITE_URL, OG_IMAGE
    load_glossary()
    eps = load_episodes()
    cfg = load_cfg()
    CUR_CFG = cfg
    if cfg.get("siteUrl"):
        SITE_URL = str(cfg["siteUrl"]).rstrip("/")
        OG_IMAGE = SITE_URL + "/assets/images/og.jpg"
    epdir = os.path.join(OUT, "episodes")
    os.makedirs(epdir, exist_ok=True)

    # 清理已合并/取消的旧页面，避免被带进上传包
    for stale in ("rights.html", "donate.html", "wiki.html"):
        p = os.path.join(OUT, stale)
        if os.path.exists(p):
            os.remove(p)

    for i in range(1, 27):
        e = eps.get(i)
        if not e:
            continue
        prev_l = ('<a href="%02d.html"><div class="lab">上一集</div><div class="tt">%s</div></a>'
                  % (i-1, eps[i-1]["title"])) if (i-1) in eps else '<span></span>'
        next_l = ('<a class="next" href="%02d.html"><div class="lab">下一集</div><div class="tt">%s</div></a>'
                  % (i+1, eps[i+1]["title"])) if (i+1) in eps else '<span></span>'
        main_blocks, whisper_blocks = split_whisper(e["blocks"])
        if not SHOW_WHISPER:
            # 低语模块暂不在网站展示；原文仍完整保留在源稿 WB_*.md 里
            whisper_blocks = []
        body = """<div class="read reader">
<div class="crumb"><a href="../index.html">首页</a> / <a href="../index.html#toc">阅读</a> / 第 %d 集</div>
<div class="prose">
%s
%s
<div class="endnote">本集完</div>
</div>
<div class="pager">%s%s</div>
%s
</div>""" % (i, render_blocks(main_blocks, "../"), render_whisper(whisper_blocks, "../"), prev_l, next_l, donate_box("../", cfg))
        page = render_page(title="第 %d 集 · %s · 《密安十二时辰》" % (i, e["title"]),
                           desc="《密安十二时辰》第 %d 集《%s》在线阅读。" % (i, e["title"]),
                           root="../", header=header("../", ""), body=body, footer=footer("../", cfg))
        with open(os.path.join(epdir, "%02d.html" % i), "w", encoding="utf-8") as f:
            f.write(page)

    with open(os.path.join(OUT, "index.html"), "w", encoding="utf-8") as f:
        f.write(home_page(eps, cfg))
    with open(os.path.join(OUT, "about.html"), "w", encoding="utf-8") as f:
        f.write(about_page(cfg))
    with open(os.path.join(OUT, "404.html"), "w", encoding="utf-8") as f:
        f.write(notfound_page(cfg))

    # 部署辅助文件（随站点一起进上传包）
    today = time.strftime("%Y-%m-%d")
    with open(os.path.join(OUT, "_headers"), "w", encoding="utf-8") as f:
        f.write(HEADERS_FILE)
    with open(os.path.join(OUT, "robots.txt"), "w", encoding="utf-8") as f:
        f.write(robots_txt())
    with open(os.path.join(OUT, "sitemap.xml"), "w", encoding="utf-8") as f:
        f.write(sitemap_xml(eps, today))

    # 旧页面跳转壳（页面已并入“关于”；保留壳页避免旧链接/书签 404）
    for old, anchor, name in (("rights.html", "rights", "版权与合作"),
                              ("donate.html", "donate", "捐助")):
        stub = ('<!DOCTYPE html>\n<meta charset="utf-8"/>\n'
                '<meta http-equiv="refresh" content="0;url=about.html#%s"/>\n'
                '<title>%s · 《密安十二时辰》</title>\n'
                '<p>页面已并入 <a href="about.html#%s">关于</a> 页，正在跳转……</p>'
                % (anchor, name, anchor))
        with open(os.path.join(OUT, old), "w", encoding="utf-8") as f:
            f.write(stub)

    meta = [{"n": eps[i]["n"], "title": eps[i]["title"], "shichen": eps[i]["shichen"],
             "countdown": eps[i]["countdown"]} for i in sorted(eps)]
    with open(os.path.join(OUT, "data", "episodes.json"), "w", encoding="utf-8") as f:
        json.dump(meta, f, ensure_ascii=False, indent=1)
    print("built episodes:", sorted(eps))
    print("out:", OUT)

    # ---- 导出上传包 dist/（纯静态；不含生成脚本与源数据）----
    dist = os.path.join(os.path.dirname(OUT), "dist")
    if os.path.isdir(dist):
        # 逐个删除（不使用 shutil.rmtree，避免部分环境下被删除保护拦截）
        for _r, _ds, _fs in os.walk(dist, topdown=False):
            for _f in _fs:
                try:
                    os.remove(os.path.join(_r, _f))
                except OSError:
                    pass
            for _d in _ds:
                try:
                    os.rmdir(os.path.join(_r, _d))
                except OSError:
                    pass
    shutil.copytree(OUT, dist, dirs_exist_ok=True,
                    ignore=shutil.ignore_patterns("build.py", "data", "__pycache__", "*.pyc"))
    print("dist:", dist)

    # ---- 打包 zip（解压后即为站点根目录内容）----
    zipbase = os.path.join(os.path.dirname(OUT), "mian-12h-site-" + time.strftime("%Y%m%d"))
    shutil.make_archive(zipbase, "zip", root_dir=dist, base_dir=".")
    print("zip:", zipbase + ".zip")

if __name__ == "__main__":
    main()
