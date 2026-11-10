/* Site motion + the price-chart tooltip. Vanilla JS, no libraries.
   Rules (docs/EVAL_DASHBOARD.md story #46): the HTML is already the finished page. This script only adds the
   classes that start an animation, so with JavaScript off, or with reduced motion, nothing is ever hidden. */
(function () {
  "use strict";
  var reduce = window.matchMedia && window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  var canIO = "IntersectionObserver" in window;
  var motion = !reduce && canIO;

  function onView(el, fn, threshold) {
    if (!canIO) { fn(el); return; }
    var io = new IntersectionObserver(function (es) {
      es.forEach(function (e) { if (e.isIntersecting) { io.unobserve(e.target); fn(e.target); } });
    }, { threshold: threshold || 0.15, rootMargin: "0px 0px -6% 0px" });
    io.observe(el);
  }

  // ---- fade/slide sections and cards in as they scroll into view
  if (motion) {
    document.querySelectorAll("[data-reveal]").forEach(function (sec) {
      var kids = sec.querySelectorAll("[data-reveal-item], .card, .btile");
      sec.classList.add("rv");
      kids.forEach(function (k, i) { k.style.setProperty("--rv-i", i); });
      onView(sec, function (el) { el.classList.add("is-in"); });
    });
  }

  // ---- count-up numbers: the HTML already holds the final number
  document.querySelectorAll("[data-count]").forEach(function (el) {
    var end = Number(el.getAttribute("data-count"));
    if (!motion || !isFinite(end) || end <= 0) return;
    var fmt = function (n) { return Math.round(n).toLocaleString("en-US"); };
    onView(el, function () {
      var t0 = null, dur = 1100;
      function tick(now) {
        if (t0 === null) t0 = now;
        var t = Math.min(1, (now - t0) / dur), e = 1 - Math.pow(1 - t, 3);
        el.textContent = fmt(end * e);
        if (t < 1) requestAnimationFrame(tick); else el.textContent = fmt(end);
      }
      el.textContent = "0";
      requestAnimationFrame(tick);
    }, 0.6);
  });

  // ---- price chart: draw-in on scroll, tap/hover tooltip, legend highlight
  function money(v) { return "$" + (v >= 100 || Math.abs(v - Math.round(v)) < 0.005 ? Math.round(v).toLocaleString("en-US") : v.toFixed(2)); }
  function at(p, f) { var r = p[0]; for (var i = 0; i < p.length; i++) { if (p[i][0] <= f + 1e-9) r = p[i]; else break; } return r; }

  document.querySelectorAll(".pchart[data-chart]").forEach(function (fig) {
    var d; try { d = JSON.parse(fig.getAttribute("data-chart")); } catch (e) { return; }
    var plot = fig.querySelector(".pc-plot"), tip = fig.querySelector(".pc-tip");
    if (motion) { fig.classList.add("anim"); onView(fig, function () { fig.classList.add("is-inview"); }, 0.35); }
    if (!plot || !tip) return;
    var guide = document.createElement("span"); guide.className = "pc-guide"; guide.hidden = true; plot.appendChild(guide);
    var pinned = false;

    function show(clientX) {
      var r = plot.getBoundingClientRect();
      var f = Math.max(0, Math.min(1, (clientX - r.left) / r.width));
      var day = new Date(d.t0 + f * (d.t1 - d.t0)).toLocaleDateString("en-US", { month: "short", day: "numeric", timeZone: "America/New_York" });
      var rows = d.s.map(function (s) { var p = at(s.p, f); return { n: s.n, c: s.c, v: p[1], ok: p[2] }; })
        .sort(function (a, b) { return (b.ok - a.ok) || (a.v - b.v); });
      tip.textContent = "";
      var h = document.createElement("b"); h.textContent = day; tip.appendChild(h);
      rows.forEach(function (x) {
        var row = document.createElement("span"); row.className = "tr" + (x.ok ? "" : " out");
        var i = document.createElement("i"); i.style.background = x.c;
        var n = document.createElement("em"); n.textContent = x.n;
        var v = document.createElement("strong"); v.textContent = x.ok ? money(x.v) : money(x.v) + " · sold out";
        row.appendChild(i); row.appendChild(n); row.appendChild(v); tip.appendChild(row);
      });
      tip.hidden = false; guide.hidden = false;
      guide.style.left = (f * 100) + "%";
      tip.style.left = (f * 100) + "%";
      tip.classList.toggle("flip", f > 0.55);
    }
    function hide() { tip.hidden = true; guide.hidden = true; pinned = false; }
    plot.addEventListener("pointermove", function (e) { if (e.pointerType === "mouse" || pinned) show(e.clientX); });
    plot.addEventListener("pointerdown", function (e) { pinned = true; show(e.clientX); });
    plot.addEventListener("pointerleave", function (e) { if (e.pointerType === "mouse") hide(); });
    document.addEventListener("pointerdown", function (e) { if (pinned && !plot.contains(e.target)) hide(); });

    var paths = fig.querySelectorAll(".ln");
    function focus(i) {
      fig.classList.toggle("focus", i != null);
      paths.forEach(function (p) { p.classList.toggle("on", p.getAttribute("data-i") === String(i)); });
    }
    fig.querySelectorAll(".pc-legend li").forEach(function (li) {
      li.addEventListener("pointerenter", function () { focus(li.getAttribute("data-i")); });
      li.addEventListener("pointerleave", function () { focus(null); });
    });
  });
})();
