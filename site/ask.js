// "Ask Bitaxe Radar" full-page chat on /ask/. Uses window.RadarAsk (ask-api.js).
// Vanilla JS. Honors prefers-reduced-motion. Answers go through textContent, never as HTML.
(function () {
  "use strict";
  var form = document.getElementById("ask-form");
  var page = document.getElementById("ask-page");
  if (!form || !page || !window.RadarAsk) return;
  var box = form.querySelector("textarea");
  var btn = form.querySelector("button.ask-submit") || form.querySelector("button");
  var btnLabel = btn && btn.querySelector(".ask-submit-label");
  var out = document.getElementById("ask-answer");
  var count = document.getElementById("ask-count");
  var newBtn = document.getElementById("ask-new");
  var history = []; // [{role, content}, ...] last few turns on this page
  var reduce = window.matchMedia && window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  var busy = false;
  var abortCtl = null;
  var revealTimer = null;
  var stickToBottom = true;
  var SVG = "http://www.w3.org/2000/svg";

  function el(tag, cls, text) {
    var n = document.createElement(tag);
    if (cls) n.className = cls;
    if (text != null) n.textContent = text;
    return n;
  }

  function grow() {
    if (!box) return;
    box.style.height = "auto";
    var next = Math.min(Math.max(box.scrollHeight, 24), 200);
    box.style.height = next + "px";
  }

  function updateCount() {
    if (!count || !box) return;
    var n = box.value.length;
    count.textContent = String(n);
    count.parentElement.classList.toggle("is-near", n >= 260);
  }

  function hasText() {
    return !!(box && (box.value || "").trim());
  }

  function syncSend() {
    if (!btn) return;
    if (busy) {
      btn.disabled = false;
      btn.setAttribute("aria-label", "Stop");
      if (btnLabel) btnLabel.textContent = "Asking…";
    } else {
      btn.disabled = !hasText();
      btn.setAttribute("aria-label", "Ask");
      if (btnLabel) btnLabel.textContent = "Ask";
    }
  }

  function setBusy(on) {
    busy = !!on;
    form.setAttribute("aria-busy", on ? "true" : "false");
    if (btn) btn.classList.toggle("is-loading", on);
    syncSend();
  }

  function enterChat() {
    page.classList.remove("is-empty");
    page.classList.add("has-chat");
    if (newBtn) newBtn.disabled = false;
  }

  function resetChat() {
    if (abortCtl) {
      try { abortCtl.abort(); } catch (e) {}
      abortCtl = null;
    }
    stopReveal();
    history = [];
    if (out) out.textContent = "";
    page.classList.add("is-empty");
    page.classList.remove("has-chat");
    if (newBtn) newBtn.disabled = true;
    setBusy(false);
    if (box) {
      box.value = "";
      updateCount();
      grow();
      box.focus();
    }
    stickToBottom = true;
  }

  function nearBottom() {
    if (!out) return true;
    return out.scrollHeight - out.scrollTop - out.clientHeight < 96;
  }

  function scrollLatest(force) {
    if (!out) return;
    if (!force && !stickToBottom) return;
    requestAnimationFrame(function () {
      out.scrollTop = out.scrollHeight;
    });
  }

  function svgEl(name, attrs) {
    var n = document.createElementNS(SVG, name);
    Object.keys(attrs || {}).forEach(function (k) { n.setAttribute(k, attrs[k]); });
    return n;
  }

  function avatar() {
    var d = el("div", "ask-avatar");
    d.setAttribute("aria-hidden", "true");
    var s = svgEl("svg", { viewBox: "0 0 64 64", focusable: "false" });
    s.appendChild(svgEl("circle", { cx: "32", cy: "32", r: "31", fill: "#0f1a2e" }));
    var g = svgEl("g", { fill: "none", stroke: "#5b74a6", "stroke-width": "3.2" });
    g.appendChild(svgEl("circle", { cx: "32", cy: "32", r: "25" }));
    g.appendChild(svgEl("circle", { cx: "32", cy: "32", r: "16.5" }));
    g.appendChild(svgEl("circle", { cx: "32", cy: "32", r: "8" }));
    s.appendChild(g);
    s.appendChild(svgEl("path", { d: "M32 32 L40.6 8.5 A25 25 0 0 1 53.2 18.8 Z", fill: "#f7931a", "fill-opacity": ".55" }));
    s.appendChild(svgEl("circle", { cx: "45", cy: "17.5", r: "4", fill: "#f7931a" }));
    s.appendChild(svgEl("circle", { cx: "32", cy: "32", r: "4", fill: "#f7931a" }));
    d.appendChild(s);
    return d;
  }

  function safeUrl(u) {
    if (!u) return false;
    if (u.charAt(0) === "/" && u.indexOf("//") !== 0 && /^\/[a-zA-Z0-9/_\-.~#?=&%]*$/.test(u)) return true;
    try {
      var p = new URL(u);
      return p.protocol === "http:" || p.protocol === "https:";
    } catch (e) {
      return false;
    }
  }

  function appendInline(parent, text) {
    var re = /\*\*([^*]+)\*\*|\*([^*]+)\*|`([^`]+)`|\[([^\]]+)\]\(([^)]+)\)|(https?:\/\/[^\s<]+)/g;
    var last = 0, m;
    text = String(text || "");
    while ((m = re.exec(text))) {
      if (m.index > last) parent.appendChild(document.createTextNode(text.slice(last, m.index)));
      if (m[1] != null) parent.appendChild(el("strong", null, m[1]));
      else if (m[2] != null) parent.appendChild(el("em", null, m[2]));
      else if (m[3] != null) parent.appendChild(el("code", null, m[3]));
      else if (m[4] != null) {
        var href = m[5] || "";
        if (safeUrl(href)) {
          var a = el("a", "ask-md-link", m[4]);
          a.href = href;
          parent.appendChild(a);
        } else {
          parent.appendChild(document.createTextNode(m[0]));
        }
      } else if (m[6]) {
        var href = m[6].replace(/[.,;:!?)]+$/, "");
        var punct = m[6].slice(href.length);
        if (safeUrl(href)) {
          var a = el("a", "ask-md-link", href);
          a.href = href;
          parent.appendChild(a);
        } else {
          parent.appendChild(document.createTextNode(href));
        }
        if (punct) parent.appendChild(document.createTextNode(punct));
      }
      last = m.index + m[0].length;
    }
    if (last < text.length) parent.appendChild(document.createTextNode(text.slice(last)));
  }

  function renderMarkdown(text, root) {
    var lines = String(text || "").replace(/\r\n/g, "\n").split("\n");
    var i = 0;
    while (i < lines.length) {
      if (/^\s*$/.test(lines[i])) { i++; continue; }
      var unordered = /^\s*[-*•]\s+/.test(lines[i]);
      var ordered = /^\s*\d+\.\s+/.test(lines[i]);
      if (unordered || ordered) {
        var list = el(ordered ? "ol" : "ul");
        var itemRe = ordered ? /^\s*\d+\.\s+/ : /^\s*[-*•]\s+/;
        while (i < lines.length && itemRe.test(lines[i])) {
          var li = el("li");
          appendInline(li, lines[i].replace(itemRe, ""));
          list.appendChild(li);
          i++;
        }
        root.appendChild(list);
        continue;
      }
      var buf = [];
      while (i < lines.length && !/^\s*$/.test(lines[i]) && !/^\s*[-*•]\s+/.test(lines[i]) && !/^\s*\d+\.\s+/.test(lines[i])) {
        buf.push(lines[i]);
        i++;
      }
      var p = el("p");
      buf.forEach(function (line, idx) {
        if (idx) p.appendChild(el("br"));
        appendInline(p, line);
      });
      root.appendChild(p);
    }
    if (!root.childNodes.length) root.appendChild(el("p", null, text || ""));
  }

  function stopReveal() {
    if (revealTimer) {
      clearTimeout(revealTimer);
      revealTimer = null;
    }
  }

  function collectTextNodes(root) {
    var nodes = [];
    var w = document.createTreeWalker(root, NodeFilter.SHOW_TEXT, null);
    while (w.nextNode()) nodes.push(w.currentNode);
    return nodes;
  }

  function revealWords(root, done) {
    if (reduce) {
      if (done) done();
      return;
    }
    var nodes = collectTextNodes(root).filter(function (n) { return n.nodeValue && n.nodeValue.length; });
    var jobs = nodes.map(function (n) {
      var parts = n.nodeValue.split(/(\s+)/);
      n.nodeValue = "";
      return { node: n, parts: parts, i: 0 };
    });
    var j = 0;
    var started = Date.now();
    function step() {
      var budget = 1;
      var elapsed = Date.now() - started;
      if (elapsed > 700) budget = 3;
      if (elapsed > 1400) budget = 8;
      if (elapsed > 2200) budget = 24;
      while (budget-- > 0) {
        while (j < jobs.length && jobs[j].i >= jobs[j].parts.length) j++;
        if (j >= jobs.length) {
          revealTimer = null;
          if (done) done();
          return;
        }
        var job = jobs[j];
        job.node.nodeValue += job.parts[job.i++];
      }
      scrollLatest();
      revealTimer = setTimeout(step, 16);
    }
    step();
  }

  function addUser(text) {
    var row = el("div", "ask-msg ask-msg-user");
    row.appendChild(el("div", "ask-bubble", text));
    out.appendChild(row);
    if (reduce) row.classList.add("is-in");
    else requestAnimationFrame(function () { row.classList.add("is-in"); });
    scrollLatest(true);
  }

  function showThinking() {
    var row = el("div", "ask-msg ask-msg-bot ask-thinking");
    row.id = "ask-thinking";
    row.appendChild(avatar());
    var body = el("div", "ask-bot-body");
    var dots = el("span", "ask-dots");
    dots.setAttribute("aria-hidden", "true");
    dots.appendChild(el("span"));
    dots.appendChild(el("span"));
    dots.appendChild(el("span"));
    body.appendChild(dots);
    body.appendChild(el("span", "sr", "Looking up today's prices…"));
    row.appendChild(body);
    out.appendChild(row);
    if (reduce) row.classList.add("is-in");
    else requestAnimationFrame(function () { row.classList.add("is-in"); });
    scrollLatest(true);
  }

  function clearThinking() {
    var t = document.getElementById("ask-thinking");
    if (t) t.remove();
  }

  function badgeFor(d) {
    if (d.sources && d.sources.length) return { cls: "ask-badge ask-guides", text: "From our guides" };
    if (d.in_data === false) return { cls: "ask-badge ask-out", text: "Not in our data" };
    return { cls: "ask-badge", text: "From our data" };
  }

  function noteFor(d) {
    if (d.sources && d.sources.length) {
      return "From our guides · confidence: " + d.confidence + ". AI answers can be wrong; check the guide.";
    }
    if (d.in_data === false) {
      return "Our data didn't cover this · confidence: " + d.confidence +
        " · data updated " + new Date(d.data_updated).toLocaleString() + ". AI answers can be wrong; check the miner page.";
    }
    if (d.confidence === "low") {
      return "Low confidence — double-check the miner page · data updated " +
        new Date(d.data_updated).toLocaleString() + ".";
    }
    return "From our price data · confidence: " + d.confidence +
      " · data updated " + new Date(d.data_updated).toLocaleString() + ". AI answers can be wrong; check the miner page.";
  }

  function confLine(d, note) {
    if (d && d.confidence) {
      var conf = "Confidence: " + d.confidence;
      if (d.data_updated) {
        try { conf += " · data updated " + new Date(d.data_updated).toLocaleString(); } catch (e) {}
      }
      return conf;
    }
    return note || "";
  }

  function copyBtn(text) {
    var b = el("button", "ask-copy");
    b.type = "button";
    b.setAttribute("aria-label", "Copy answer");
    var ico = svgEl("svg", { viewBox: "0 0 24 24", focusable: "false", "aria-hidden": "true" });
    ico.appendChild(svgEl("rect", { x: "9", y: "9", width: "11", height: "11", rx: "2", fill: "none", stroke: "currentColor", "stroke-width": "1.8" }));
    ico.appendChild(svgEl("path", { d: "M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1", fill: "none", stroke: "currentColor", "stroke-width": "1.8", "stroke-linecap": "round" }));
    b.appendChild(ico);
    b.appendChild(el("span", "ask-copy-label", "Copy"));
    b.addEventListener("click", function () {
      var label = b.querySelector(".ask-copy-label");
      function ok() {
        if (label) label.textContent = "Copied";
        b.classList.add("is-copied");
        setTimeout(function () {
          if (label) label.textContent = "Copy";
          b.classList.remove("is-copied");
        }, 1600);
      }
      if (navigator.clipboard && navigator.clipboard.writeText) {
        navigator.clipboard.writeText(text).then(ok, function () {});
      }
    });
    return b;
  }

  function showAnswer(text, links, note, sources, d) {
    clearThinking();
    var row = el("div", "ask-msg ask-msg-bot ask-response");
    row.appendChild(avatar());
    var body = el("div", "ask-bot-body");
    var md = el("div", "ask-md");
    renderMarkdown(text, md);
    body.appendChild(md);
    if (links && links.length) {
      var models = el("div", "ask-models");
      links.forEach(function (id) {
        var a = el("a", "ask-model", window.RadarAsk.modelName(id));
        a.href = "/models/" + encodeURIComponent(id) + "/";
        models.appendChild(a);
      });
      body.appendChild(models);
    }
    var meta = el("div", "ask-meta");
    if (d) {
      var b = badgeFor(d);
      meta.appendChild(el("span", b.cls, b.text));
    }
    (sources || []).forEach(function (s) {
      var a = el("a", "ask-badge ask-source", s.title);
      if (safeUrl(s.url || "") && /^\/[a-z0-9\/-]*$/.test(s.url || "")) a.href = s.url;
      else a.removeAttribute("href");
      meta.appendChild(a);
    });
    var conf = confLine(d, note);
    if (conf) meta.appendChild(el("span", "ask-conf", conf));
    if (meta.childNodes.length) body.appendChild(meta);
    if (text) body.appendChild(copyBtn(text));
    row.appendChild(body);
    out.appendChild(row);
    if (reduce) {
      row.classList.add("is-in");
      scrollLatest(true);
    } else {
      requestAnimationFrame(function () { row.classList.add("is-in"); });
      revealWords(md, function () { scrollLatest(true); });
    }
  }

  function showError(text) {
    clearThinking();
    var row = el("div", "ask-msg ask-msg-bot ask-response ask-error");
    row.appendChild(avatar());
    var body = el("div", "ask-bot-body");
    body.appendChild(el("p", "ask-error-text", text || "Something went wrong."));
    row.appendChild(body);
    out.appendChild(row);
    if (reduce) row.classList.add("is-in");
    else requestAnimationFrame(function () { row.classList.add("is-in"); });
    scrollLatest(true);
  }

  function abort() {
    if (abortCtl) {
      try { abortCtl.abort(); } catch (e) {}
    }
  }

  function submitQuestion(q) {
    q = (q || "").replace(/\s+/g, " ").trim();
    if (!q || busy) return;
    box.value = "";
    updateCount();
    grow();
    enterChat();
    stickToBottom = true;
    addUser(q);
    setBusy(true);
    showThinking();
    abortCtl = typeof AbortController === "function" ? new AbortController() : null;
    window.RadarAsk.ask(q, history, abortCtl && abortCtl.signal).then(function (d) {
      if (!d || d.aborted) {
        clearThinking();
        return;
      }
      if (!d.ok) return showError(d.error || "Something went wrong.");
      history.push({ role: "user", content: q });
      history.push({ role: "assistant", content: d.answer });
      if (history.length > 6) history = history.slice(-6);
      showAnswer(d.answer, d.models_mentioned, noteFor(d), d.sources, d);
    }).then(function () {
      abortCtl = null;
      setBusy(false);
      box.focus();
    }, function () {
      abortCtl = null;
      setBusy(false);
    });
  }

  form.addEventListener("submit", function (e) {
    e.preventDefault();
    if (busy) { abort(); return; }
    submitQuestion(box.value);
  });

  box.addEventListener("input", function () { updateCount(); grow(); syncSend(); });
  box.addEventListener("keydown", function (e) {
    // Enter sends the question; Shift+Enter inserts a newline. Ignore IME composition.
    if (e.isComposing || e.keyCode === 229) return;
    if (e.key !== "Enter" || e.shiftKey) return;
    e.preventDefault();
    if (busy || (btn && btn.disabled) || !(box.value || "").trim()) return;
    form.requestSubmit ? form.requestSubmit() : form.dispatchEvent(new Event("submit", { cancelable: true }));
  });

  if (out) {
    out.addEventListener("scroll", function () {
      stickToBottom = nearBottom();
    }, { passive: true });
  }

  document.querySelectorAll(".ask-chip").forEach(function (chip) {
    chip.addEventListener("click", function () {
      var q = chip.getAttribute("data-q") || chip.textContent;
      submitQuestion(q);
    });
  });

  if (newBtn) newBtn.addEventListener("click", function () { resetChat(); });

  // Pin the page to the visible viewport so the iOS keyboard doesn't cover the input (BUILD_LOG_ASK #11).
  function fitToViewport() {
    var vv = window.visualViewport;
    if (!vv) {
      page.style.top = "0";
      page.style.height = "100dvh";
      return;
    }
    page.style.top = vv.offsetTop + "px";
    page.style.left = (vv.offsetLeft || 0) + "px";
    page.style.height = vv.height + "px";
    page.style.width = vv.width + "px";
    scrollLatest();
  }
  fitToViewport();
  window.addEventListener("resize", fitToViewport);
  if (window.visualViewport) {
    window.visualViewport.addEventListener("resize", fitToViewport);
    window.visualViewport.addEventListener("scroll", fitToViewport);
  }
  box.addEventListener("focus", function () {
    setTimeout(fitToViewport, 100);
    setTimeout(fitToViewport, 350);
  });

  updateCount();
  grow();
  syncSend();

  // Cards start visible; motion CSS only applies when scripting + no reduced motion.
  var reveals = document.querySelectorAll(".ask-reveal");
  if (reduce || !("IntersectionObserver" in window)) {
    reveals.forEach(function (node) { node.classList.add("is-inview"); });
  } else {
    var io = new IntersectionObserver(function (entries) {
      entries.forEach(function (e) {
        if (e.isIntersecting) { e.target.classList.add("is-inview"); io.unobserve(e.target); }
      });
    }, { threshold: 0.12 });
    reveals.forEach(function (node) { io.observe(node); });
  }
})();
