/* 《密安十二时辰》站点交互：复制地址 / 主题切换 / 背景音乐 / 正文词条浮层 */
(function () {
  function ready(fn) {
    if (document.readyState !== "loading") fn();
    else document.addEventListener("DOMContentLoaded", fn);
  }

  ready(function () {
    var doc = document.documentElement;

    /* ---- 捐助地址复制 ---- */
    document.addEventListener("click", function (e) {
      var el = e.target.closest(".cp");
      if (!el) return;
      var box = el.closest(".row");
      var ad = box ? box.querySelector(".ad") : null;
      if (!ad) return;
      var text = ad.textContent.trim();
      if (!text || text.indexOf("待") === 0) return;
      var done = function () {
        el.textContent = "已复制";
        setTimeout(function () { el.textContent = "复制"; }, 1400);
      };
      if (navigator.clipboard && navigator.clipboard.writeText) {
        navigator.clipboard.writeText(text).then(done, done);
      } else {
        var ta = document.createElement("textarea");
        ta.value = text;
        document.body.appendChild(ta);
        ta.select();
        try { document.execCommand("copy"); } catch (err) {}
        document.body.removeChild(ta);
        done();
      }
    });

    /* ---- 捐助：快捷金额浮层 / 金额步进 / 选链 / 唤起钱包转账 ---- */
    /* 链 → USDT 合约与小数位（2026-10-15 对照 Tether 官方页面核实）：
       以太坊 6 位；BNB Chain 的 BSC-USD 是 18 位（BSC 上的发行版，非 Tether 直发）；Polygon / Arbitrum 6 位 */
    var DM_CHAINS = {
      "1":     { token: "0xdAC17F958D2ee523a2206206994597C13D831ec7", dec: 6 },
      "56":    { token: "0x55d398326f99059fF775485246999027B3197955", dec: 18 },
      "137":   { token: "0xc2132D05D31c914a87C6611C10748AEb04B58e8F", dec: 6 },
      "42161": { token: "0xFd086bC7CD5C481DCC9C85ebE478A1C0b69FCbb9", dec: 6 }
    };
    function dmToUnits(str, dec) {
      var s = String(str || "").replace(/[^\d.]/g, "");
      if (!s) return "0";
      var p = s.split(".");
      var ip = (p[0] || "").replace(/^0+(?=\d)/, "") || "0";
      var fp = (p[1] || "").replace(/\D/g, "").slice(0, dec);
      while (fp.length < dec) fp += "0";
      return (ip + fp).replace(/^0+(?=\d)/, "") || "0";
    }
    function dmNum(str) {
      var f = parseFloat(String(str || "").replace(/[^\d.]/g, ""));
      return isFinite(f) ? f : 0;
    }
    function dmStr(n) { return String(Math.round(n * 1e6) / 1e6); }

    var dm = document.getElementById("donateModal");
    if (dm) {
      var dInput = document.getElementById("dmAmount");
      var dGo = document.getElementById("dmGo");
      var dmChainBtns = [].slice.call(dm.querySelectorAll("[data-dm-chain]"));
      var dmSetBtns = [].slice.call(dm.querySelectorAll("[data-dm-set]"));
      var addrEl = document.querySelector(".addr .ad");
      var dmAddr = addrEl ? addrEl.textContent.trim() : "";
      if (!dmAddr || dmAddr.indexOf("待") === 0) {
        dGo.setAttribute("aria-disabled", "true");
        dGo.setAttribute("title", "捐助地址尚未公布");
      }
      var dmChain = "1";

      function dmAmt() { var n = dmNum(dInput.value); return n < 1 ? 1 : n; }
      function dmSync() {
        var n = dmAmt();
        var c = DM_CHAINS[dmChain];
        if (c && dmAddr) {
          dGo.href = "ethereum:" + c.token + "@" + dmChain +
                     "/transfer?address=" + dmAddr + "&uint256=" + dmToUnits(dmStr(n), c.dec);
        }
        dmSetBtns.forEach(function (b) {
          b.classList.toggle("on", dmNum(b.getAttribute("data-dm-set")) === dmNum(dInput.value));
        });
      }
      function dmPick(id) {
        if (!DM_CHAINS[id]) return;
        dmChain = id;
        dmChainBtns.forEach(function (b) {
          b.classList.toggle("on", b.getAttribute("data-dm-chain") === id);
        });
        dmSync();
      }
      function dmOpen(amount) {
        if (amount != null) dInput.value = dmStr(amount);
        if (dmNum(dInput.value) < 1) dInput.value = "1";
        dm.hidden = false;
        document.documentElement.style.overflow = "hidden";
        dmPick(dmChain);
        dmSync();
        try { dInput.focus(); } catch (e) {}
      }
      function dmClose() {
        dm.hidden = true;
        document.documentElement.style.overflow = "";
      }

      [].slice.call(document.querySelectorAll("[data-donate]")).forEach(function (b) {
        b.addEventListener("click", function () {
          dmOpen(parseFloat(b.getAttribute("data-donate")) || 5);
        });
      });
      dmSetBtns.forEach(function (b) {
        b.addEventListener("click", function () {
          dInput.value = b.getAttribute("data-dm-set");
          dmSync();
        });
      });
      [].slice.call(dm.querySelectorAll("[data-dm-step]")).forEach(function (b) {
        b.addEventListener("click", function () {
          var n = dmAmt() + (parseFloat(b.getAttribute("data-dm-step")) || 0);
          if (n < 1) n = 1;
          dInput.value = dmStr(n);
          dmSync();
        });
      });
      dmChainBtns.forEach(function (b) {
        b.addEventListener("click", function () { dmPick(b.getAttribute("data-dm-chain")); });
      });
      [].slice.call(dm.querySelectorAll("[data-dm-close]")).forEach(function (b) {
        b.addEventListener("click", dmClose);
      });
      dInput.addEventListener("input", function () {
        var v = dInput.value.replace(/[^\d.]/g, "").replace(/(\..*)\./g, "$1").slice(0, 12);
        dInput.value = v;
        dmSync();
      });
      dInput.addEventListener("blur", function () {
        dInput.value = dmStr(dmAmt());
        dmSync();
      });
      dGo.addEventListener("click", function (e) { if (!dmAddr) e.preventDefault(); });
      document.addEventListener("keydown", function (e) {
        if (e.key === "Escape" && !dm.hidden) dmClose();
      });

      /* 若页面已装有钱包，默认选中它当前所在的链 */
      if (window.ethereum && window.ethereum.request) {
        window.ethereum.request({ method: "eth_chainId" }).then(function (hex) {
          var id = String(parseInt(hex, 16));
          if (DM_CHAINS[id]) dmPick(id);
        }).catch(function () {});
      }
      dmPick("1");
      dmSync();
    }

    /* ---- 主题切换（默认深色） ---- */
    var tBtn = document.getElementById("themeBtn");
    function curTheme() { return doc.getAttribute("data-theme") === "light" ? "light" : "dark"; }
    function applyTheme(t) {
      if (t === "light") doc.setAttribute("data-theme", "light");
      else doc.removeAttribute("data-theme");
      try { localStorage.setItem("b12h_theme", t); } catch (e) {}
      if (tBtn) {
        tBtn.textContent = t === "light" ? "☾" : "☀";
        tBtn.setAttribute("title", t === "light" ? "切换到深色主题" : "切换到浅色主题");
      }
    }
    if (tBtn) {
      applyTheme(curTheme());
      tBtn.addEventListener("click", function () {
        applyTheme(curTheme() === "light" ? "dark" : "light");
      });
    }

    /* ---- 背景音乐开关 ---- */
    var a = document.getElementById("bgm");
    var mBtn = document.getElementById("musicBtn");
    if (a && mBtn) {
      var pref = "on";
      try { if (localStorage.getItem("b12h_music") === "off") pref = "off"; } catch (e) {}
      function syncUI() {
        var playing = !a.paused && !a.ended;
        mBtn.classList.toggle("on", playing);
        mBtn.setAttribute("title", playing ? "关闭背景音乐" : "播放背景音乐");
      }
      a.addEventListener("play", syncUI);
      a.addEventListener("pause", syncUI);
      a.addEventListener("ended", syncUI);
      syncUI();
      function save(v) { try { localStorage.setItem("b12h_music", v); } catch (e) {} }
      function tryPlay() {
        var p = a.play();
        if (p && p.catch) p.catch(function () { syncUI(); });
      }
      if (pref === "on") tryPlay();
      mBtn.addEventListener("click", function () {
        if (!a.paused && !a.ended) { pref = "off"; save("off"); a.pause(); }
        else { pref = "on"; save("on"); tryPlay(); }
      });
    }

    /* ---- 0xTim 的低语：默认折叠，读者主动展开 ---- */
    var whisper = document.getElementById("whisper");
    if (whisper) {
      var wToggle = document.querySelector(".whisper-toggle");
      var wBtn = document.getElementById("whisperBtn");
      if (wBtn) wBtn.hidden = false;
      var setWhisper = function (open) {
        whisper.hidden = !open;
        if (wToggle) {
          wToggle.setAttribute("aria-expanded", open ? "true" : "false");
          wToggle.classList.toggle("open", open);
          var h = wToggle.querySelector(".wt-hint");
          if (h) h.textContent = open ? "收起" : "展开";
        }
        if (wBtn) {
          wBtn.classList.toggle("on", open);
          wBtn.setAttribute("aria-expanded", open ? "true" : "false");
        }
      };
      var toggleWhisper = function () {
        var open = whisper.hidden;
        setWhisper(open);
        if (open && whisper.scrollIntoView) {
          whisper.scrollIntoView({ behavior: "smooth", block: "center" });
        }
      };
      if (wToggle) wToggle.addEventListener("click", toggleWhisper);
      if (wBtn) wBtn.addEventListener("click", toggleWhisper);
    }

    /* ---- 关于页：页内导航高亮当前所在模块 ---- */
    var subnav = document.querySelector("nav.subnav");
    if (subnav) {
      var slinks = [].slice.call(subnav.querySelectorAll('a[href^="#"]'));
      var secs = slinks.map(function (a) {
        var id = a.getAttribute("href").slice(1);
        var el = document.getElementById(id);
        return el ? { a: a, el: el } : null;
      }).filter(Boolean);
      if (secs.length) {
        var spy = function () {
          var y = window.scrollY + 170;
          var cur = secs[0];
          for (var i = 0; i < secs.length; i++) {
            if (secs[i].el.offsetTop <= y) cur = secs[i];
          }
          /* 滚到底部时，强制高亮最后一个模块 */
          if (window.innerHeight + window.scrollY >= document.body.scrollHeight - 4) {
            cur = secs[secs.length - 1];
          }
          secs.forEach(function (s) { s.a.classList.toggle("on", s === cur); });
        };
        window.addEventListener("scroll", spy, { passive: true });
        window.addEventListener("resize", spy);
        spy();
      }
    }

    /* ---- 正文词条浮层：PC 悬浮 / 手机点击 ---- */
    var tip = document.createElement("div");
    tip.className = "tip";
    tip.setAttribute("role", "tooltip");
    tip.hidden = true;
    document.body.appendChild(tip);

    var curEl = null;
    function place(el) {
      var r = el.getBoundingClientRect();
      var w = tip.offsetWidth, h = tip.offsetHeight;
      var left = r.left + r.width / 2 - w / 2;
      left = Math.max(10, Math.min(left, window.innerWidth - w - 10));
      var top = r.top - h - 10;
      if (top < 8) top = r.bottom + 10;
      tip.style.left = Math.round(left) + "px";
      tip.style.top = Math.round(top) + "px";
    }
    function show(el) {
      var t = el.getAttribute("data-t") || "";
      var d = el.getAttribute("data-def") || "";
      var u = el.getAttribute("data-url") || "";
      var ul = el.getAttribute("data-url-label") || "了解更多";
      var fic = el.getAttribute("data-fic") === "1";
      var html = "";
      if (t) html += '<div class="tip-t">' + t + "</div>";
      if (d) html += '<div class="tip-d">' + d + "</div>";
      if (fic) html += '<div class="tip-fic">书中虚构，与任何真实主体无关</div>';
      if (u) html += '<a class="tip-l" href="' + u + '" target="_blank" rel="noopener">' + ul + ' ↗</a>';
      if (!html) return;
      tip.innerHTML = html;
      tip.hidden = false;
      place(el);
      curEl = el;
    }
    function hide() { tip.hidden = true; curEl = null; }

    var canHover = window.matchMedia &&
      window.matchMedia("(hover: hover) and (pointer: fine)").matches;

    function pick(e) { return e.target.closest ? e.target.closest("[data-def]") : null; }

    if (canHover) {
      document.addEventListener("mouseover", function (e) {
        var el = pick(e);
        if (el) show(el);
      });
      document.addEventListener("mouseout", function (e) {
        var el = pick(e);
        if (!el) return;
        var to = e.relatedTarget;
        if (to && (el.contains(to) || tip.contains(to))) return;
        hide();
      });
      tip.addEventListener("mouseleave", hide);
    }

    /* 点击（含触屏）切换；锚点交给浏览器自己跳转 */
    document.addEventListener("click", function (e) {
      var el = pick(e);
      if (!el) { hide(); return; }
      if (e.target.closest("a")) return;
      if (curEl === el && !tip.hidden) hide(); else show(el);
    });

    document.addEventListener("keydown", function (e) { if (e.key === "Escape") hide(); });
    window.addEventListener("scroll", function () {
      if (!tip.hidden && curEl) place(curEl);
    }, { passive: true });
    window.addEventListener("resize", hide);
  });
})();
