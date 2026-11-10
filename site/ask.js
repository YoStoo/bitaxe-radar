// "Ask Bitaxe Radar" box on /ask/. Uses window.RadarAsk (ask-api.js).
// Vanilla JS. Honors prefers-reduced-motion. Answers go through textContent, never as HTML.
(function () {
  "use strict";
  var form = document.getElementById("ask-form");
  if (!form || !window.RadarAsk) return;
  var box = form.querySelector("textarea");
  var btn = form.querySelector("button.ask-submit") || form.querySelector("button");
  var btnLabel = btn && btn.querySelector(".ask-submit-label");
  var out = document.getElementById("ask-answer");
  var count = document.getElementById("ask-count");
  var history = []; // [{role, content}, ...] last few turns on this page
  var reduce = window.matchMedia && window.matchMedia("(prefers-reduced-motion: reduce)").matches;

  function grow() {
    if (!box) return;
    box.style.height = "auto";
    var next = Math.min(Math.max(box.scrollHeight, 96), 240);
    box.style.height = next + "px";
  }

  function updateCount() {
    if (!count || !box) return;
    var n = box.value.length;
    count.textContent = String(n);
    count.parentElement.classList.toggle("is-near", n >= 260);
  }

  function el(tag, cls, text) {
    var n = document.createElement(tag);
    if (cls) n.className = cls;
    if (text != null) n.textContent = text;
    return n;
  }

  function setBusy(on) {
    btn.disabled = on;
    form.setAttribute("aria-busy", on ? "true" : "false");
    if (btn) {
      btn.classList.toggle("is-loading", on);
      if (btnLabel) btnLabel.textContent = on ? "Asking…" : "Ask";
    }
  }

  function showThinking() {
    out.textContent = "";
    var wrap = el("div", "ask-thinking");
    var dots = el("span", "ask-dots");
    dots.setAttribute("aria-hidden", "true");
    dots.appendChild(el("span"));
    dots.appendChild(el("span"));
    dots.appendChild(el("span"));
    wrap.appendChild(dots);
    wrap.appendChild(document.createTextNode("Looking up today's prices…"));
    out.appendChild(wrap);
  }

  function badgeFor(d) {
    if (d.sources && d.sources.length) return { cls: "ask-badge ask-guides", text: "From our guides" };
    if (d.in_data === false) return { cls: "ask-badge ask-out", text: "Not in our data" };
    return { cls: "ask-badge", text: "From our data" };
  }

  function show(text, links, note, sources, d) {
    out.textContent = "";
    var card = el("div", "ask-response");
    var p = el("p", null, text);
    card.appendChild(p);
    if (links && links.length) {
      var models = el("div", "ask-models");
      links.forEach(function (id) {
        var a = el("a", "ask-model", window.RadarAsk.modelName(id));
        a.href = "/models/" + encodeURIComponent(id) + "/";
        models.appendChild(a);
      });
      card.appendChild(models);
    }
    var meta = el("div", "ask-meta");
    if (d) {
      var b = badgeFor(d);
      meta.appendChild(el("span", b.cls, b.text));
    }
    (sources || []).forEach(function (s) {
      var a = el("a", "ask-badge ask-source", s.title);
      if (/^\/[a-z0-9\/-]*$/.test(s.url || "")) a.href = s.url;
      else a.removeAttribute("href");
      meta.appendChild(a);
    });
    if (d && d.confidence) {
      var conf = "Confidence: " + d.confidence;
      if (d.data_updated) {
        try { conf += " · data updated " + new Date(d.data_updated).toLocaleString(); } catch (e) {}
      }
      meta.appendChild(el("span", "ask-conf", conf));
    } else if (note) {
      meta.appendChild(el("span", "ask-conf", note));
    }
    if (meta.childNodes.length) card.appendChild(meta);
    out.appendChild(card);
    if (reduce) {
      card.classList.add("is-in");
    } else {
      requestAnimationFrame(function () { card.classList.add("is-in"); });
    }
  }

  function showError(text) {
    show(text, [], "", [], null);
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

  function submitQuestion(q) {
    q = (q || "").replace(/\s+/g, " ").trim();
    if (!q) return;
    box.value = q;
    updateCount();
    grow();
    setBusy(true);
    showThinking();
    window.RadarAsk.ask(q, history).then(function (d) {
      if (!d.ok) return showError(d.error || "Something went wrong.");
      history.push({ role: "user", content: q });
      history.push({ role: "assistant", content: d.answer });
      if (history.length > 6) history = history.slice(-6);
      show(d.answer, d.models_mentioned, noteFor(d), d.sources, d);
    }).then(function () { setBusy(false); box.focus(); }, function () { setBusy(false); });
  }

  form.addEventListener("submit", function (e) {
    e.preventDefault();
    submitQuestion(box.value);
  });

  box.addEventListener("input", function () { updateCount(); grow(); });
  box.addEventListener("keydown", function (e) {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      form.requestSubmit ? form.requestSubmit() : form.dispatchEvent(new Event("submit", { cancelable: true }));
    }
  });

  document.querySelectorAll(".ask-chip").forEach(function (chip) {
    chip.addEventListener("click", function () {
      var q = chip.getAttribute("data-q") || chip.textContent;
      submitQuestion(q);
    });
  });

  updateCount();
  grow();

  // Cards start visible; motion CSS only applies when scripting + no reduced motion.
  var reveals = document.querySelectorAll(".ask-reveal");
  if (reduce || !("IntersectionObserver" in window)) {
    reveals.forEach(function (el) { el.classList.add("is-inview"); });
  } else {
    var io = new IntersectionObserver(function (entries) {
      entries.forEach(function (e) {
        if (e.isIntersecting) { e.target.classList.add("is-inview"); io.unobserve(e.target); }
      });
    }, { threshold: 0.12 });
    reveals.forEach(function (el) { io.observe(el); });
  }
})();
