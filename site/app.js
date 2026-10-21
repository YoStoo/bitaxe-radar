var AFFILIATE = { powermining: "ref=bitaxeradar" };

// ---- email alerts config -------------------------------------------------------------------
// build_site.py reads these (single source of truth) and passes them to signup.js on every page with the alert form.
var WORKER_URL = "https://bitaxe-radar-alerts.bitaxeradar.workers.dev/subscribe";
var TURNSTILE_SITEKEY = "0x4AAAAAAFYqcERY2Pvc1wQI";   // public site key
var SIGNUP_ENABLED = true;
// Cloudflare Web Analytics site token (public, cookie-free). Empty = no analytics tag. build_site.py reads it.
var CF_BEACON_TOKEN = "c27e77d1efd346c6aeed5b72e1ff7b0b";

// Home page extras. The miner cards, alert form and links are pre-rendered by build_site.py from data/latest.json;
// this script only adds the "updated X ago" label and the running-cost calculator, using window.RADAR from data.js.
(function () {
  "use strict";
  var R = window.RADAR;
  if (!R || !R.latest) return;
  var L = R.latest;

  function el(tag, attrs) {
    var n = document.createElement(tag), i, c;
    if (attrs) for (var k in attrs) { if (k === "class") n.className = attrs[k]; else n.setAttribute(k, attrs[k]); }
    for (i = 2; i < arguments.length; i++) {
      c = arguments[i]; if (c == null || c === false) continue;
      n.appendChild(typeof c === "string" ? document.createTextNode(c) : c);
    }
    return n;
  }

  // ---- freshness: "Updated 3 hours ago"
  var f = document.getElementById("freshness");
  if (f) {
    var mins = Math.max(0, Math.round((Date.now() - new Date(L.generated_at).getTime()) / 60000));
    var txt = mins < 60 ? (mins <= 1 ? "just now" : mins + " min ago") : mins < 48 * 60 ? Math.round(mins / 60) + (Math.round(mins / 60) === 1 ? " hour ago" : " hours ago") : null;
    if (txt) f.textContent = txt;
    f.title = new Date(L.generated_at).toLocaleString();
  }

  // ---- open a FAQ item when linked to directly (e.g. /#cost from a model page)
  function openFromHash() { var d = location.hash && document.getElementById(location.hash.slice(1)); if (d && d.tagName === "DETAILS") d.open = true; }
  window.addEventListener("hashchange", openFromHash); openFromHash();

  // ---- running cost calculator (only models we have listings for)
  var rate = document.getElementById("rate"), tb = document.querySelector("#costTable tbody");
  if (!rate || !tb) return;
  var mids = Object.keys(L.models).filter(function (mid) { return L.models[mid].category !== "home" && L.offers.some(function (o) { return o.model === mid; }); });
  function usd(v) { return "$" + v.toFixed(2); }
  function renderCost() {
    var r = parseFloat(rate.value); if (!(r >= 0)) r = 0;
    tb.textContent = "";
    mids.forEach(function (mid) {
      var m = L.models[mid], yr = m.watts * 8.76 * r;
      tb.appendChild(el("tr", null, el("td", null, el("a", { href: "/models/" + mid + "/" }, m.name.replace(/\s*\(.*\)$/, ""))),
        el("td", { class: "num" }, "≈" + m.watts), el("td", { class: "num" }, usd(yr / 12)), el("td", { class: "num" }, usd(yr))));
    });
  }
  rate.addEventListener("input", renderCost); renderCost();
})();
