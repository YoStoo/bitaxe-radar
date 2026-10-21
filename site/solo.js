/* Bitaxe Radar solo odds calculator. Mirrors earnings.py exactly (tests/test_calc_parity.py).
   Network hashrate comes from the build (window.RADAR_SOLO). It's a lottery: these are odds, not a forecast. */
(function (root) {
  var N = root.RADAR_SOLO; if (!N) return;
  var DPM = 365 / 12, PERIODS = [["day", 1], ["year", 365], ["5y", 365 * 5]];
  function rate(th) { return th * 1e12 / N.network_hashrate_hs * 144; }
  function chance(th, days) { return -Math.expm1(-rate(th) * days); }
  function g2(x) { return String(Number(x.toPrecision(2))); }
  function commas(x) { return Math.round(x).toLocaleString("en-US"); }
  function fmtBig(n) {
    if (n >= 1e9) return n < 1e10 ? g2(n / 1e9) + " billion" : commas(n / 1e9) + " billion";
    if (n >= 1e6) return n < 1e7 ? g2(n / 1e6) + " million" : commas(n / 1e6) + " million";
    if (n >= 100) return commas(Number(n.toPrecision(2)));
    return commas(n);
  }
  function fmtPct(p) {
    var pct = p * 100;
    if (pct >= 99.5) return "over 99%";
    if (pct >= 10) return pct.toFixed(0) + "%";
    if (pct < 0.000001) return "under 0.000001%";
    return pct.toFixed(Math.max(1, 1 - Math.floor(Math.log10(pct)))) + "%";
  }
  function fmtOneIn(p) { return p >= 0.5 ? "better than even" : "1 in " + fmtBig(1 / p); }
  function fmtWait(days) {
    if (days < 1) { var h = Math.max(1, Math.floor(days * 24 + 0.5)); return "about " + h + " hour" + (h === 1 ? "" : "s"); }
    if (days < 60) { var d = Math.floor(days + 0.5); return "about " + d + " day" + (d === 1 ? "" : "s"); }
    if (days < 730) return "about " + Math.floor(days / DPM + 0.5) + " months";
    return "about " + fmtBig(days / 365) + " years";
  }
  function rows(th) {
    return [PERIODS.map(function (p) { var c = chance(th, p[1]); return [p[0], fmtPct(c), fmtOneIn(c)]; }), fmtWait(1 / rate(th))];
  }
  root.RadarSolo = { rate: rate, chance: chance, fmtBig: fmtBig, fmtPct: fmtPct, fmtOneIn: fmtOneIn, fmtWait: fmtWait, rows: rows };
  if (typeof document === "undefined") return;

  var UNIT = { gh: 0.001, th: 1, ph: 1000 };
  function init() {
    var f = document.getElementById("solo-form"); if (!f) return;
    var h = f.querySelector("#solo-h"), u = f.querySelector("#solo-u"), m = f.querySelector("#solo-m");
    function show(th) {
      var r = rows(th), out = {};
      r[0].forEach(function (x) { out[x[0] + "-pct"] = x[1]; out[x[0] + "-in"] = x[2]; });
      out.wait = r[1];
      out.th = (th >= 1000 ? g2(th / 1000) + " PH/s" : th >= 1 ? String(Number(th.toPrecision(3))) + " TH/s" : String(Number((th * 1000).toPrecision(3))) + " GH/s");
      [].forEach.call(document.querySelectorAll("[data-solo]"), function (el) { if (out[el.dataset.solo] != null) el.textContent = out[el.dataset.solo]; });
    }
    function fromInput() {
      var v = parseFloat(h.value), th = v * (UNIT[u.value] || 1);
      if (!(th > 0 && th < 1e9)) return;
      m.value = [].some.call(m.options, function (o) { return +o.value === th && u.value === "th"; }) ? String(th) : "";
      show(th);
    }
    m.addEventListener("change", function () { if (!m.value) return; h.value = m.value; u.value = "th"; show(+m.value); });
    h.addEventListener("input", fromInput); u.addEventListener("change", fromInput);
    f.addEventListener("submit", function (e) { e.preventDefault(); fromInput(); });
    var q = parseFloat((location.search.match(/[?&]th=([0-9.]+)/) || [])[1]);
    if (q > 0 && q < 1e9) { h.value = String(q); u.value = "th"; }
    f.hidden = false; fromInput();
  }
  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", init); else init();
})(typeof window !== "undefined" ? window : globalThis);
