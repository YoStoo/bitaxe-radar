// Floating "Ask Bitaxe Radar" chat bubble on every page. Uses window.RadarAsk (ask-api.js).
// Chips (example questions) show once per browser; dismissal is stored in localStorage.
(function () {
  "use strict";
  if (!window.RadarAsk || document.getElementById("radar-ask-root")) return;

  var LS_CHIPS = "radarAskChipsDismissed";
  var LS_HIST = "radarAskHistory"; // sessionStorage: follows you around this tab
  var CHIP_DELAY_MS = 2200;
  var CHIP_CYCLE_MS = 5500;
  var EXAMPLES = [
    "Which miner should I get?",
    "Cheapest Bitaxe right now?",
    "Is solo mining worth it?"
  ];

  var reduceMotion = false;
  try { reduceMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches; } catch (e) {}

  function isMobile() {
    try { return window.matchMedia("(max-width: 520px)").matches; } catch (e) { return false; }
  }

  function modelContext() {
    var m = location.pathname.match(/^\/models\/([^\/]+)\/?$/);
    if (!m) return null;
    var id = decodeURIComponent(m[1]);
    var h = document.querySelector("main h1, h1");
    var name = h ? h.textContent.replace(/\s+/g, " ").trim() : id;
    return { id: id, name: name };
  }

  function chipList() {
    var list = EXAMPLES.slice();
    var ctx = modelContext();
    if (ctx) list.unshift("Where's the cheapest " + ctx.name + "?");
    return list;
  }

  function chipsDismissed() {
    try { return localStorage.getItem(LS_CHIPS) === "1"; } catch (e) { return false; }
  }
  function dismissChips() {
    try { localStorage.setItem(LS_CHIPS, "1"); } catch (e) {}
    if (chipsEl) chipsEl.hidden = true;
  }

  // ---- DOM ----
  var root = document.createElement("div");
  root.id = "radar-ask-root";
  root.setAttribute("data-radar-ask", "1");

  var chipsEl = document.createElement("div");
  chipsEl.id = "radar-ask-chips";
  chipsEl.setAttribute("aria-live", "polite");
  chipsEl.hidden = true;

  var bubble = document.createElement("button");
  bubble.type = "button";
  bubble.id = "radar-ask-bubble";
  bubble.setAttribute("aria-haspopup", "dialog");
  bubble.setAttribute("aria-expanded", "false");
  bubble.setAttribute("aria-controls", "radar-ask-panel");
  bubble.title = "Ask Bitaxe Radar";
  bubble.innerHTML = '<span class="ra-ico" aria-hidden="true">' +
    '<svg viewBox="0 0 64 64" width="28" height="28" focusable="false">' +
    '<circle cx="32" cy="32" r="31" fill="#0f1a2e"/>' +
    '<g fill="none" stroke="#5b74a6" stroke-width="3.2"><circle cx="32" cy="32" r="25"/><circle cx="32" cy="32" r="16.5"/><circle cx="32" cy="32" r="8"/></g>' +
    '<path d="M32 32 L40.6 8.5 A25 25 0 0 1 53.2 18.8 Z" fill="#f7931a" fill-opacity=".55"/>' +
    '<circle cx="45" cy="17.5" r="4" fill="#f7931a"/><circle cx="32" cy="32" r="4" fill="#f7931a"/>' +
    '</svg></span><span class="ra-label">Ask</span>';
  if (!reduceMotion) bubble.classList.add("ra-bounce");

  var panel = document.createElement("div");
  panel.id = "radar-ask-panel";
  panel.setAttribute("role", "dialog");
  panel.setAttribute("aria-modal", "true");
  panel.setAttribute("aria-labelledby", "radar-ask-title");
  panel.hidden = true;

  panel.innerHTML =
    '<div class="ra-head">' +
      '<div class="ra-head-text"><strong id="radar-ask-title">Ask Bitaxe Radar</strong>' +
      '<span class="ra-sub">AI answers from today\'s miner prices</span></div>' +
      '<div class="ra-head-actions">' +
        '<button type="button" class="ra-new" aria-label="Start a new chat">New chat</button>' +
        '<button type="button" class="ra-close" aria-label="Close chat">&times;</button>' +
      '</div>' +
    '</div>' +
    '<div class="ra-msgs" id="radar-ask-msgs" aria-live="polite"></div>' +
    '<form class="ra-form" id="radar-ask-form">' +
      '<label class="sr" for="radar-ask-input">Your question</label>' +
      '<textarea id="radar-ask-input" maxlength="300" rows="2" placeholder="Ask about miners, prices, or which one to get…" required></textarea>' +
      '<button type="submit" class="ra-send" aria-label="Send">Ask</button>' +
    '</form>' +
    '<p class="ra-foot">AI can be wrong. Check the miner page before you buy.</p>';

  root.appendChild(chipsEl);
  root.appendChild(panel);
  root.appendChild(bubble);
  document.body.appendChild(root);

  var msgs = panel.querySelector("#radar-ask-msgs");
  var form = panel.querySelector("#radar-ask-form");
  var input = panel.querySelector("#radar-ask-input");
  var sendBtn = panel.querySelector(".ra-send");
  var closeBtn = panel.querySelector(".ra-close");
  var newBtn = panel.querySelector(".ra-new");
  var open = false;
  var busy = false;
  var lastFocus = null;
  var lockScrollY = 0;
  var vvListening = false;

  function el(tag, cls, text) {
    var n = document.createElement(tag);
    if (cls) n.className = cls;
    if (text != null) n.textContent = text;
    return n;
  }

  function scrollLatest() {
    requestAnimationFrame(function () {
      msgs.scrollTop = msgs.scrollHeight;
      var last = msgs.lastElementChild;
      if (last && last.scrollIntoView) {
        try { last.scrollIntoView({ block: "end", inline: "nearest" }); } catch (e) { last.scrollIntoView(false); }
      }
    });
  }

  // Pin the open panel to the visible viewport (above the iOS keyboard).
  function fitPanelToViewport() {
    if (!open || !isMobile()) {
      panel.style.top = panel.style.left = panel.style.right = panel.style.bottom = "";
      panel.style.height = panel.style.width = panel.style.borderRadius = "";
      return;
    }
    var vv = window.visualViewport;
    var top = vv ? vv.offsetTop : 0;
    var left = vv ? vv.offsetLeft : 0;
    var height = vv ? vv.height : window.innerHeight;
    var width = vv ? vv.width : window.innerWidth;
    // Full-bleed when the keyboard has shrunk the viewport; small inset otherwise.
    var keyboardOpen = vv && vv.height < window.innerHeight * 0.8;
    var inset = keyboardOpen ? 0 : 8;
    panel.style.position = "fixed";
    panel.style.top = (top + inset) + "px";
    panel.style.left = (left + inset) + "px";
    panel.style.width = Math.max(0, width - inset * 2) + "px";
    panel.style.height = Math.max(0, height - inset * 2) + "px";
    panel.style.right = "auto";
    panel.style.bottom = "auto";
    panel.style.borderRadius = inset ? "16px" : "0";
  }

  function onViewportChange() {
    if (!open) return;
    fitPanelToViewport();
    scrollLatest();
  }

  function startViewportWatch() {
    if (vvListening) return;
    vvListening = true;
    window.addEventListener("resize", onViewportChange);
    if (window.visualViewport) {
      window.visualViewport.addEventListener("resize", onViewportChange);
      window.visualViewport.addEventListener("scroll", onViewportChange);
    }
  }

  function stopViewportWatch() {
    if (!vvListening) return;
    vvListening = false;
    window.removeEventListener("resize", onViewportChange);
    if (window.visualViewport) {
      window.visualViewport.removeEventListener("resize", onViewportChange);
      window.visualViewport.removeEventListener("scroll", onViewportChange);
    }
  }

  function lockBody() {
    if (!isMobile()) return;
    lockScrollY = window.scrollY || window.pageYOffset || 0;
    document.body.classList.add("ra-ask-lock");
    document.documentElement.classList.add("ra-ask-lock");
    document.body.style.top = "-" + lockScrollY + "px";
  }

  function unlockBody() {
    if (!document.body.classList.contains("ra-ask-lock")) return;
    document.body.classList.remove("ra-ask-lock");
    document.documentElement.classList.remove("ra-ask-lock");
    document.body.style.top = "";
    window.scrollTo(0, lockScrollY);
  }

  // ---- conversation memory (sessionStorage so the chat follows you around the site) ----
  function loadHistory() {
    try {
      var raw = JSON.parse(sessionStorage.getItem(LS_HIST) || "[]");
      return Array.isArray(raw) ? raw.filter(function (m) {
        return m && (m.role === "user" || m.role === "assistant") && typeof m.content === "string" && m.content.trim();
      }).slice(-6) : [];
    } catch (e) { return []; }
  }
  function saveHistory(h) {
    try { sessionStorage.setItem(LS_HIST, JSON.stringify((h || []).slice(-6))); } catch (e) {}
  }
  var history = loadHistory();

  function noteFor(d) {
    if (d.in_data === false) return "General knowledge — not from our price data.";
    if (d.confidence === "low") return "Low confidence — double-check the miner page.";
    return "From our price data · " + d.confidence + " confidence";
  }

  function renderWelcome() {
    var tip = el("div", "ra-row ra-bot");
    var b = el("div", "ra-bubble");
    b.appendChild(el("p", null, "Ask about home Bitcoin miners — prices, stock, or which one to get. I use today's data from this site."));
    tip.appendChild(b);
    msgs.appendChild(tip);
  }

  function renderHistory() {
    msgs.textContent = "";
    if (!history.length) { renderWelcome(); return; }
    history.forEach(function (m) {
      if (m.role === "user") addUser(m.content, true);
      else addBot({ ok: true, answer: m.content, models_mentioned: [], confidence: "", in_data: true }, true);
    });
  }

  function addUser(text, skipScroll) {
    var row = el("div", "ra-row ra-user");
    row.appendChild(el("div", "ra-bubble", text));
    msgs.appendChild(row);
    if (!skipScroll) scrollLatest();
  }

  function addTyping() {
    var row = el("div", "ra-row ra-bot ra-typing");
    row.id = "radar-ask-typing";
    var b = el("div", "ra-bubble");
    b.innerHTML = '<span></span><span></span><span></span>';
    row.appendChild(b);
    msgs.appendChild(row);
    scrollLatest();
  }

  function clearTyping() {
    var t = document.getElementById("radar-ask-typing");
    if (t) t.remove();
  }

  function addBot(d, skipScroll) {
    clearTyping();
    var row = el("div", "ra-row ra-bot");
    var b = el("div", "ra-bubble");
    if (!d.ok) {
      b.appendChild(el("p", null, d.error || "Something went wrong."));
      row.appendChild(b);
      msgs.appendChild(row);
      if (!skipScroll) scrollLatest();
      return;
    }
    b.appendChild(el("p", null, d.answer));
    if (d.models_mentioned && d.models_mentioned.length) {
      var links = el("p", "ra-links");
      d.models_mentioned.forEach(function (id, i) {
        if (i) links.appendChild(document.createTextNode(" · "));
        var a = document.createElement("a");
        a.href = "/models/" + encodeURIComponent(id) + "/";
        a.textContent = window.RadarAsk.modelName(id);
        links.appendChild(a);
      });
      b.appendChild(links);
    }
    if (!skipScroll && (d.confidence || d.in_data === false)) {
      b.appendChild(el("p", "ra-note", noteFor(d)));
    }
    row.appendChild(b);
    msgs.appendChild(row);
    if (!skipScroll) scrollLatest();
  }

  function openPanel(prefill, autoSend) {
    if (open) {
      if (prefill) { input.value = prefill; if (autoSend) submitQ(prefill); }
      input.focus();
      return;
    }
    lastFocus = document.activeElement;
    open = true;
    panel.hidden = false;
    bubble.setAttribute("aria-expanded", "true");
    bubble.classList.remove("ra-bounce");
    root.classList.add("ra-open");
    dismissChips();
    lockBody();
    startViewportWatch();
    fitPanelToViewport();
    if (prefill) input.value = prefill;
    setTimeout(function () {
      input.focus();
      fitPanelToViewport();
      scrollLatest();
    }, 30);
    if (autoSend && prefill) submitQ(prefill);
  }

  function closePanel() {
    if (!open) return;
    open = false;
    panel.hidden = true;
    bubble.setAttribute("aria-expanded", "false");
    root.classList.remove("ra-open");
    stopViewportWatch();
    fitPanelToViewport(); // clears inline styles
    unlockBody();
    if (lastFocus && lastFocus.focus) lastFocus.focus();
    else bubble.focus();
  }

  function submitQ(q) {
    q = String(q || "").replace(/\s+/g, " ").trim();
    if (!q || busy) return;
    if (q.length > window.RadarAsk.MAX) {
      addBot({ ok: false, error: "Keep it under " + window.RadarAsk.MAX + " characters." });
      return;
    }
    busy = true;
    sendBtn.disabled = true;
    input.value = "";
    addUser(q);
    addTyping();
    // Send prior turns so follow-ups like "why is it expensive?" still know which miner.
    window.RadarAsk.ask(q, history.slice()).then(function (d) {
      addBot(d);
      if (d && d.ok) {
        history.push({ role: "user", content: q });
        history.push({ role: "assistant", content: d.answer });
        if (history.length > 6) history = history.slice(-6);
        saveHistory(history);
      }
    }).then(function () {
      busy = false;
      sendBtn.disabled = false;
      input.focus();
      fitPanelToViewport();
      scrollLatest();
    });
  }

  function clearChat() {
    history = [];
    saveHistory(history);
    msgs.textContent = "";
    renderWelcome();
    scrollLatest();
    input.focus();
  }

  // ---- chips ----
  var chipIdx = 0;
  var chipTimer = null;
  var chipsAnimated = false;
  var allChips = chipList();

  function renderChip() {
    chipsEl.textContent = "";
    var wrap = el("div", "ra-chip-wrap");
    // Fade in only the first time — later cycles stay fully opaque (no mid-animation washout).
    if (!chipsAnimated && !reduceMotion) { wrap.classList.add("ra-chip-anim"); chipsAnimated = true; }
    var q = allChips[chipIdx % allChips.length];
    var btn = el("button", "ra-chip", q);
    btn.type = "button";
    btn.title = q;
    btn.addEventListener("click", function () {
      dismissChips();
      openPanel(q, true);
    });
    wrap.appendChild(btn);
    var x = el("button", "ra-chip-x", "×");
    x.type = "button";
    x.setAttribute("aria-label", "Hide suggestions");
    x.addEventListener("click", function (e) { e.stopPropagation(); dismissChips(); });
    wrap.appendChild(x);
    chipsEl.appendChild(wrap);
    chipsEl.hidden = false;
  }

  // On phones, don't cover the primary Buy CTA — wait until it scrolls above the widget.
  function ctaIsClear() {
    if (!isMobile()) return true;
    var cta = document.querySelector(".model-deal a.btn, .cta a.btn, .model-deal .btn");
    if (!cta) return true;
    var r = cta.getBoundingClientRect();
    var box = root.getBoundingClientRect();
    return r.bottom < box.top - 6;
  }

  function startChips() {
    if (chipsDismissed()) return;
    function showIfClear() {
      if (chipsDismissed() || open) return;
      if (!ctaIsClear()) { chipsEl.hidden = true; return; }
      renderChip();
    }
    showIfClear();
    window.addEventListener("scroll", showIfClear, { passive: true });
    window.addEventListener("resize", showIfClear, { passive: true });
    if (reduceMotion || allChips.length < 2) return;
    chipTimer = setInterval(function () {
      if (chipsEl.hidden || open || !ctaIsClear()) return;
      chipIdx = (chipIdx + 1) % allChips.length;
      renderChip();
    }, CHIP_CYCLE_MS);
  }

  // ---- events ----
  bubble.addEventListener("click", function () { openPanel(); });
  closeBtn.addEventListener("click", closePanel);
  newBtn.addEventListener("click", clearChat);
  form.addEventListener("submit", function (e) {
    e.preventDefault();
    submitQ(input.value);
  });
  input.addEventListener("focus", function () {
    if (!open) return;
    // iOS opens the keyboard after focus — re-fit once it settles.
    setTimeout(onViewportChange, 100);
    setTimeout(onViewportChange, 350);
  });
  document.addEventListener("keydown", function (e) {
    if (e.key === "Escape" && open) { e.preventDefault(); closePanel(); }
  });
  // Click outside panel closes it (not the bubble)
  document.addEventListener("mousedown", function (e) {
    if (!open) return;
    if (root.contains(e.target)) return;
    closePanel();
  });
  // Stop the page behind from scrolling/dragging while the panel is open on phones.
  document.addEventListener("touchmove", function (e) {
    if (!open || !isMobile()) return;
    if (msgs.contains(e.target)) return;
    e.preventDefault();
  }, { passive: false });

  // Restore this tab's chat (or show the welcome tip) the first time the panel opens.
  var painted = false;
  function ensurePainted() {
    if (painted) return;
    painted = true;
    renderHistory();
  }
  var _openPanel = openPanel;
  openPanel = function (prefill, autoSend) {
    ensurePainted();
    _openPanel(prefill, autoSend);
  };

  setTimeout(startChips, reduceMotion ? 400 : CHIP_DELAY_MS);
})();
