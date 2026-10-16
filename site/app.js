var AFFILIATE = { powermining: "ref=bitaxeradar" };

// ---- email alerts config -------------------------------------------------------------------
// TODO (before launch): deploy the Cloudflare Worker (see worker/README.md), then set all three:
var WORKER_URL = "https://bitaxe-radar-alerts.bitaxeradar.workers.dev/subscribe";
var TURNSTILE_SITEKEY = "0x4AAAAAAFYqcERY2Pvc1wQI";   // public site key
var SIGNUP_ENABLED = true;                                        
(function () {
  "use strict";
  var R = window.RADAR;
  if (!R || !R.latest) { document.getElementById("freshness").textContent = "Data failed to load."; return; }
  var L = R.latest, H = R.history || {};
  var COLORS = ["#f7931a", "#6ea8fe", "#3ecf8e", "#d58cff", "#f5c04a", "#ef6b6b"];
  var STATUS = { in_stock: "In stock", out_of_stock: "Out of stock", preorder: "Pre-order", backorder: "Backorder", unknown: "Unknown" };

  function el(tag, attrs) {
    var n = document.createElement(tag), i, c;
    if (attrs) for (var k in attrs) { if (k === "class") n.className = attrs[k]; else n.setAttribute(k, attrs[k]); }
    for (i = 2; i < arguments.length; i++) {
      c = arguments[i]; if (c == null || c === false) continue;
      n.appendChild(typeof c === "string" ? document.createTextNode(c) : c);
    }
    return n;
  }
  function svg(tag, attrs, text) {
    var n = document.createElementNS("http://www.w3.org/2000/svg", tag);
    for (var k in attrs) n.setAttribute(k, attrs[k]);
    if (text != null) n.textContent = text;
    return n;
  }
  function money(v, cur) {
    try { return new Intl.NumberFormat("en-US", { style: "currency", currency: cur }).format(v); }
    catch (e) { return cur + " " + v.toFixed(2); }
  }
  function fmtTime(iso) {
    var d = new Date(iso);
    return d.toLocaleString(undefined, { month: "short", day: "numeric", hour: "numeric", minute: "2-digit" });
  }
  function ageHours(iso) { return (Date.now() - new Date(iso).getTime()) / 36e5; }
  function sellerName(id) { return (L.sellers[id] || {}).name || id; }

  // ---- freshness line
  (function () {
    var f = document.getElementById("freshness");
    var txt = "Data last collected " + fmtTime(L.generated_at) + " · " + L.offers.length + " offers from " +
      Object.keys(L.sellers).length + " sellers";
    if (L.fx) txt += " · EUR→USD ≈ " + L.fx.EUR_USD + " (" + L.fx.date + ")";
    f.textContent = txt;
    if (ageHours(L.generated_at) > 48) { f.appendChild(el("span", { class: "stale" }, "  ⚠ Data is more than 48 hours old.")); }
  })();

  // ---- comparison tables
  var onlyStock = document.getElementById("onlyStock");
  function renderTables() {
    var host = document.getElementById("tables"); host.textContent = "";
    Object.keys(L.models).forEach(function (mid) {
      var m = L.models[mid];
      var offers = L.offers.filter(function (o) { return o.model === mid; });
      if (!offers.length) return;
      var shown = offers.filter(function (o) { return !onlyStock.checked || o.in_stock; });
      var cand = offers.filter(function (o) { return o.in_stock && o.price_usd_approx != null; });
      var best = cand.length ? cand.reduce(function (a, b) { return b.price_usd_approx < a.price_usd_approx ? b : a; }) : null;
      shown.sort(function (a, b) {
        if (a.in_stock !== b.in_stock) return a.in_stock ? -1 : 1;
        return (a.price_usd_approx == null ? 1e9 : a.price_usd_approx) - (b.price_usd_approx == null ? 1e9 : b.price_usd_approx);
      });
      var card = el("div", { class: "model" });
      card.appendChild(el("header", null,
        el("h3", null, m.name),
        el("span", { class: "spec" }, "≈" + m.hashrate_ths + " TH/s · ≈" + m.watts + " W (vendor-stated, approximate) · " + m.chip + (m.note ? " · " + m.note : ""))));
      var tbody = el("tbody");
      if (!shown.length) tbody.appendChild(el("tr", null, el("td", { colspan: 6 }, "No in-stock offers found at the last check.")));
      shown.forEach(function (o) {
        var isBest = best && o.id === best.id;
        var priceCell = el("td", { class: "num" }, money(o.price, o.currency));
        if (o.currency !== "USD" && o.price_usd_approx != null) priceCell.appendChild(el("div", { class: "cfg" }, "≈ " + money(o.price_usd_approx, "USD")));
        if (o.compare_at && o.compare_at > o.price) priceCell.appendChild(el("div", { class: "cfg" }, "list " + money(o.compare_at, o.currency)));
        var cfg = o.config + (o.ship_note ? " · " + o.ship_note : "") +
          (o.variants_total ? " · " + o.variants_in_stock + "/" + o.variants_total + " options in stock" : "");
        var aff = AFFILIATE[o.seller];
        var href = aff ? o.url + (o.url.indexOf("?") < 0 ? "?" : "&") + aff : o.url;
        var link = el("a", { class: "btn", href: href, target: "_blank", rel: "nofollow noopener sponsored" }, "View at " + sellerName(o.seller) + " ↗");
        tbody.appendChild(el("tr", isBest ? { class: "best" } : null,
          el("td", null, sellerName(o.seller), isBest ? el("span", { class: "tag-best" }, "Best in-stock") : null,
            o.stale ? el("div", { class: "stale" }, "stale data") : null),
          priceCell,
          el("td", null, el("span", { class: "badge b-" + o.stock_status }, STATUS[o.stock_status] || o.stock_status)),
          el("td", { class: "cfg" }, cfg),
          el("td", { class: "cfg" }, fmtTime(o.checked_at)),
          el("td", null, link, aff ? el("div", { class: "ph" }, "affiliate link") : null)));
      });
      card.appendChild(el("div", { class: "tablewrap" }, el("table", null,
        el("thead", null, el("tr", null, el("th", null, "Seller"), el("th", { class: "num" }, "Price"), el("th", null, "Stock"),
          el("th", null, "Config"), el("th", null, "Checked"), el("th", null, "Buy"))), tbody)));
      host.appendChild(card);
    });
  }
  onlyStock.addEventListener("change", renderTables);
  renderTables();

  // ---- model selects
  var histSel = document.getElementById("histModel"), alertSel = document.getElementById("alertModel");
  Object.keys(L.models).forEach(function (mid) {
    if (!L.offers.some(function (o) { return o.model === mid; })) return;
    histSel.appendChild(el("option", { value: mid }, L.models[mid].name));
    alertSel.appendChild(el("option", { value: mid }, L.models[mid].name));
  });

  // ---- price history chart (USD-approx so sellers are comparable)
  function usd(pt) { return pt.currency === "EUR" ? (L.fx ? pt.price * L.fx.EUR_USD : null) : pt.price; }
  function renderChart() {
    var mid = histSel.value, host = document.getElementById("chart"), legend = document.getElementById("legend");
    host.textContent = ""; legend.textContent = "";
    var series = L.offers.filter(function (o) { return o.model === mid; }).map(function (o, i) {
      return { o: o, color: COLORS[i % COLORS.length], pts: (H[o.id] || []).map(function (p) { return { t: new Date(p.t).getTime(), v: usd(p), p: p }; }).filter(function (p) { return p.v != null; }) };
    }).filter(function (s) { return s.pts.length; });
    var total = series.reduce(function (n, s) { return n + s.pts.length; }, 0);
    document.getElementById("histHint").textContent = series.length
      ? (total <= series.length
          ? "Tracking started " + fmtTime(L.generated_at) + ". Only one data point per seller exists so far — lines appear as the collector keeps running. Values shown in USD (EUR converted at the rate above)."
          : "Values shown in USD (EUR sellers converted at the latest rate, so FX moves affect their lines).")
      : "No history yet for this model.";
    if (!series.length) return;
    var W = 900, Hh = 320, m = { l: 56, r: 16, t: 14, b: 34 };
    var all = [].concat.apply([], series.map(function (s) { return s.pts; }));
    var tmin = Math.min.apply(null, all.map(function (p) { return p.t; })), tmax = Math.max.apply(null, all.map(function (p) { return p.t; }));
    var vmin = Math.min.apply(null, all.map(function (p) { return p.v; })), vmax = Math.max.apply(null, all.map(function (p) { return p.v; }));
    var pad = Math.max((vmax - vmin) * 0.15, vmax * 0.05); vmin = Math.max(0, vmin - pad); vmax = vmax + pad;
    var span = tmax - tmin;
    function X(t) { return span ? m.l + (t - tmin) / span * (W - m.l - m.r) : (W + m.l - m.r) / 2; }
    function Y(v) { return Hh - m.b - (v - vmin) / (vmax - vmin) * (Hh - m.t - m.b); }
    var s = svg("svg", { viewBox: "0 0 " + W + " " + Hh, role: "img", "aria-label": "Price history for " + L.models[mid].name });
    for (var i = 0; i <= 4; i++) {
      var v = vmin + (vmax - vmin) * i / 4, y = Y(v);
      s.appendChild(svg("line", { x1: m.l, x2: W - m.r, y1: y, y2: y, stroke: "#2a2f3a" }));
      s.appendChild(svg("text", { x: m.l - 8, y: y + 4, "text-anchor": "end", fill: "#9aa3b2", "font-size": 12 }, "$" + v.toFixed(0)));
    }
    [tmin, tmax].forEach(function (t, k) {
      if (k === 1 && !span) return;
      s.appendChild(svg("text", { x: X(t), y: Hh - 10, "text-anchor": span ? (k ? "end" : "start") : "middle", fill: "#9aa3b2", "font-size": 12 },
        new Date(t).toLocaleDateString(undefined, { month: "short", day: "numeric" })));
    });
    series.forEach(function (se) {
      if (se.pts.length > 1) {
        s.appendChild(svg("polyline", { fill: "none", stroke: se.color, "stroke-width": 2, points: se.pts.map(function (p) { return X(p.t) + "," + Y(p.v); }).join(" ") }));
      }
      se.pts.forEach(function (p) {
        var c = svg("circle", { cx: X(p.t), cy: Y(p.v), r: 4, fill: p.p.in_stock ? se.color : "#0f1115", stroke: se.color, "stroke-width": 2 });
        c.appendChild(svg("title", {}, sellerName(se.o.seller) + ": " + money(p.p.price, p.p.currency) + " (" + (STATUS[p.p.status] || p.p.status) + ") " + fmtTime(new Date(p.t).toISOString())));
        s.appendChild(c);
      });
      legend.appendChild(el("span", null, el("i", { style: "background:" + se.color }), sellerName(se.o.seller)));
    });
    legend.appendChild(el("span", null, "● filled = in stock, ○ hollow = not in stock at that check"));
    host.appendChild(s);
  }
  histSel.addEventListener("change", renderChart); renderChart();

  // ---- running cost calculator
  var rate = document.getElementById("rate"), tb = document.querySelector("#costTable tbody");
  function renderCost() {
    var r = parseFloat(rate.value); if (!(r >= 0)) r = 0;
    tb.textContent = "";
    Object.keys(L.models).forEach(function (mid) {
      var m = L.models[mid], kwh = m.watts * 24 * 365 / 1000, yr = kwh * r;
      tb.appendChild(el("tr", null, el("td", null, m.name), el("td", { class: "num" }, "≈" + m.watts),
        el("td", { class: "num" }, Math.round(kwh).toLocaleString()), el("td", { class: "num" }, "$" + yr.toFixed(2)), el("td", { class: "num" }, "$" + (yr / 12).toFixed(2))));
    });
    var w = document.getElementById("customW"), cw = w ? parseFloat(w.value) : 20;
    if (!(cw >= 0)) cw = 0;
    var ck = cw * 8.76, cy = ck * r;
    var row = el("tr", null, el("td", null, "My own wattage: ",
      (function () { var i = el("input", { id: "customW", type: "number", min: "0", step: "1", value: String(w ? w.value : 20), "aria-label": "Custom watts", style: "width:80px" }); i.addEventListener("input", renderCost); return i; })()),
      el("td", { class: "num" }, "≈" + cw), el("td", { class: "num" }, Math.round(ck).toLocaleString()), el("td", { class: "num" }, "$" + cy.toFixed(2)), el("td", { class: "num" }, "$" + (cy / 12).toFixed(2)));
    var hadFocus = document.activeElement && document.activeElement.id === "customW";
    tb.appendChild(row);
    if (hadFocus) { var ni = document.getElementById("customW"); ni.focus(); ni.setSelectionRange(ni.value.length, ni.value.length); }
  }
  rate.addEventListener("input", renderCost); renderCost();

  // ---- email alert signup (double opt-in; posts to the Cloudflare Worker)
  (function () {
    var form = document.getElementById("signup"), msg = document.getElementById("signupMsg"), btn = document.getElementById("signupBtn");
    var email = document.getElementById("email"), price = document.getElementById("alertPrice"), model = document.getElementById("alertModel");
    var tsHost = document.getElementById("turnstile"), tsWidget = null;
    if (!SIGNUP_ENABLED) {
      document.getElementById("signupIntro").appendChild(el("span", { class: "stale" }, " Alerts are launching soon: this form is not live yet and nothing you type is stored or sent."));
      btn.disabled = true; msg.textContent = "Not live yet.";
      [email, price, model].forEach(function (i) { i.disabled = true; });
      return;
    }
    function renderTurnstile() { if (window.turnstile && !tsWidget) tsWidget = window.turnstile.render(tsHost, { sitekey: TURNSTILE_SITEKEY, theme: "dark" }); }
    window.onTurnstileLoaded = renderTurnstile;
    var s = document.createElement("script");
    s.src = "https://challenges.cloudflare.com/turnstile/v0/api.js?render=explicit&onload=onTurnstileLoaded"; s.async = true; s.defer = true;
    document.head.appendChild(s);

    form.addEventListener("submit", function (e) {
      e.preventDefault();
      var tok = form.querySelector('[name="cf-turnstile-response"]');
      var p = Number(price.value);
      if (!/^\S+@\S+\.\S+$/.test(email.value)) { msg.textContent = "Please enter a valid email address."; email.focus(); return; }
      if (!(p >= 1 && p <= 100000)) { msg.textContent = "Please enter a target price in USD (1 to 100000)."; price.focus(); return; }
      if (!tok || !tok.value) { msg.textContent = "Please wait for the bot check to finish, then try again."; return; }
      btn.disabled = true; msg.textContent = "Sending…";
      fetch(WORKER_URL, {
        method: "POST", headers: { "Content-Type": "application/json", "Accept": "application/json" },
        body: JSON.stringify({ email: email.value.trim(), model: model.value, target_price: p, website: document.getElementById("website").value, "cf-turnstile-response": tok.value })
      }).then(function (r) { return r.json().catch(function () { return {}; }).then(function (d) { return { ok: r.ok && d.ok, d: d }; }); })
        .then(function (res) {
          if (res.ok) { msg.textContent = res.d.message || "Check your inbox to confirm."; email.value = ""; price.value = ""; }
          else { msg.textContent = res.d.error || "Something went wrong. Please try again."; }
        })
        .catch(function () { msg.textContent = "Network error. Please try again."; })
        .then(function () { btn.disabled = false; if (window.turnstile && tsWidget != null) window.turnstile.reset(tsWidget); });
    });
  })();

  // ---- coverage
  var ts = document.getElementById("trackedSellers"), grid = el("div", { class: "sellers" });
  Object.keys(L.sellers).forEach(function (id) {
    var s = L.sellers[id], n = L.offers.filter(function (o) { return o.seller === id; }).length;
    grid.appendChild(el("div", { class: "seller" }, el("strong", null, s.name), el("small", null, s.currency + " · " + n + " models tracked"),
      el("small", null, "Source: " + s.method), el("small", null, el("a", { href: s.url, rel: "nofollow noopener", target: "_blank" }, s.url.replace(/^https?:\/\//, "")))));
  });
  ts.appendChild(grid);
  var ul = document.getElementById("unscrapable");
  L.unscrapable.forEach(function (u) { ul.appendChild(el("li", null, el("strong", null, u.seller + ": "), u.reason)); });
})();
