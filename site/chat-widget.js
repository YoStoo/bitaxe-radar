// Floating "Ask Bitaxe Radar" chat bubble on every page. Uses window.RadarAsk (ask-api.js).
// Chips (example questions) show once per browser; dismissal is stored in localStorage.
(function () {
  "use strict";
  if (!window.RadarAsk || document.getElementById("radar-ask-root")) return;

  var LS_CHIPS = "radarAskChipsDismissed";
  var CHIP_DELAY_MS = 2200;
  var CHIP_CYCLE_MS = 5500;
  var EXAMPLES = [
    "Which miner should I get?",
    "Cheapest Bitaxe right now?",
    "Is solo mining worth it?"
  ];

  var reduceMotion = false;
  try { reduceMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches; } catch (e) {}

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
      '<button type="button" class="ra-close" aria-label="Close chat">&times;</button>' +
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
  var open = false;
  var busy = false;
  var lastFocus = null;

  function el(tag, cls, text) {
    var n = document.createElement(tag);
    if (cls) n.className = cls;
    if (text != null) n.textContent = text;
    return n;
  }

  function addUser(text) {
    var row = el("div", "ra-row ra-user");
    row.appendChild(el("div", "ra-bubble", text));
    msgs.appendChild(row);
    msgs.scrollTop = msgs.scrollHeight;
  }

  function addTyping() {
    var row = el("div", "ra-row ra-bot ra-typing");
    row.id = "radar-ask-typing";
    var b = el("div", "ra-bubble");
    b.innerHTML = '<span></span><span></span><span></span>';
    row.appendChild(b);
    msgs.appendChild(row);
    msgs.scrollTop = msgs.scrollHeight;
  }

  function clearTyping() {
    var t = document.getElementById("radar-ask-typing");
    if (t) t.remove();
  }

  function addBot(d) {
    clearTyping();
    var row = el("div", "ra-row ra-bot");
    var b = el("div", "ra-bubble");
    if (!d.ok) {
      b.appendChild(el("p", null, d.error || "Something went wrong."));
      row.appendChild(b);
      msgs.appendChild(row);
      msgs.scrollTop = msgs.scrollHeight;
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
    if (d.in_data === false) {
      b.appendChild(el("p", "ra-note", "General knowledge — not from our price data."));
    } else if (d.confidence) {
      b.appendChild(el("p", "ra-note", "From our price data · " + d.confidence + " confidence"));
    }
    row.appendChild(b);
    msgs.appendChild(row);
    msgs.scrollTop = msgs.scrollHeight;
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
    if (prefill) input.value = prefill;
    setTimeout(function () { input.focus(); }, 30);
    if (autoSend && prefill) submitQ(prefill);
  }

  function closePanel() {
    if (!open) return;
    open = false;
    panel.hidden = true;
    bubble.setAttribute("aria-expanded", "false");
    root.classList.remove("ra-open");
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
    window.RadarAsk.ask(q).then(function (d) {
      addBot(d);
    }).then(function () {
      busy = false;
      sendBtn.disabled = false;
      input.focus();
    });
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

  function isMobile() {
    try { return window.matchMedia("(max-width: 520px)").matches; } catch (e) { return false; }
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
  form.addEventListener("submit", function (e) {
    e.preventDefault();
    submitQ(input.value);
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

  // Welcome empty state once opened with no messages
  bubble.addEventListener("click", function once() {
    if (msgs.childNodes.length === 0) {
      var tip = el("div", "ra-row ra-bot");
      var b = el("div", "ra-bubble");
      b.appendChild(el("p", null, "Ask about home Bitcoin miners — prices, stock, or which one to get. I use today's data from this site."));
      tip.appendChild(b);
      msgs.appendChild(tip);
    }
    bubble.removeEventListener("click", once);
  });

  setTimeout(startChips, reduceMotion ? 400 : CHIP_DELAY_MS);
})();
