/* Bitaxe Radar "your electricity price" calculator. Mirrors earnings.py exactly (tests/test_calc_parity.py).
   Network inputs come from the build (window.RADAR_NET). Every figure is an estimate. */
(function (root) {
  var N = root.RADAR_NET; if (!N) return;
  var DPM = 365 / 12;
  function floorTo(x, step) { return Math.round(Math.floor(x / step + 1e-9) * step * 100) / 100; }
  function roundDown(x) { return x < 10 ? floorTo(x, 0.01) : Math.floor(x); }
  function roundUp(x) { return x < 10 ? Math.ceil(x * 100 - 1e-9) / 100 : Math.ceil(x - 1e-9); }
  function fmtUsd(x) { return x < 10 ? "$" + x.toFixed(2) : "$" + Math.round(x).toLocaleString("en-US"); }
  function fmtRate(r) { var s = (Math.floor(r * 1000 + 0.5) / 1000).toFixed(3); return "$" + (s.slice(-1) === "0" ? s.slice(0, -1) : s); }
  function poolMonth(th) {
    var share = th * 1e12 / N.network_hashrate_hs;
    var btcDay = share * 144 * (N.subsidy_btc + N.avg_fees_btc) * (1 - N.pool_fee) * (1 - N.haircut);
    return btcDay * N.btc_usd * DPM;
  }
  function power(w, r) { return w / 1000 * 24 * DPM * r; }
  function netMonth(th, w, r) { return roundDown(poolMonth(th)) - power(w, r); }
  function netWords(th, w, r) {
    var n = netMonth(th, w, r), rs = fmtRate(r);
    if (Math.abs(n) < 0.01) return "About breaks even at " + rs;
    if (n > 0) return "Earns about " + fmtUsd(roundDown(n)) + "/mo more than its power costs at " + rs;
    return "Costs about " + fmtUsd(roundUp(-n)) + "/mo more than it earns at " + rs;
  }
  function netShort(th, w, r) {
    var n = netMonth(th, w, r);
    if (Math.abs(n) < 0.01) return "$0.00";
    return n > 0 ? "+" + fmtUsd(roundDown(n)) : "\u2212" + fmtUsd(roundUp(-n));
  }
  function breakeven(th, w) { return Math.floor(poolMonth(th) / (w / 1000 * 24 * DPM) * 1000 + 1e-9) / 1000; }
  function heat(w, r) { return roundDown(power(w, r)); }
  var C = root.RadarCalc = { poolMonth: poolMonth, power: power, netMonth: netMonth, netWords: netWords, netShort: netShort, breakeven: breakeven,
                             heat: heat, fmtUsd: fmtUsd, fmtRate: fmtRate, roundDown: roundDown, roundUp: roundUp };
  if (typeof document === "undefined") return;

  var KEY = "radarRate", DEF = N.default_rate;
  function getRate() { var v = NaN; try { v = parseFloat(localStorage.getItem(KEY)); } catch (e) {} return v >= 0 && v <= 2 ? v : DEF; }
  function apply(r) {
    [].forEach.call(document.querySelectorAll("[data-calc]"), function (el) {
      var d = el.dataset, th = +d.th, w = +d.w;
      if (d.calc === "net") { var n = netMonth(th, w, r); el.textContent = netWords(th, w, r); el.classList.toggle("pos", n >= 0.01); el.classList.toggle("neg", n <= -0.01); }
      else if (d.calc === "netnum") { var m = netMonth(th, w, r); el.textContent = netShort(th, w, r); el.classList.toggle("pos", m >= 0.01); el.classList.toggle("neg", m <= -0.01); }
      else if (d.calc === "power") el.textContent = fmtUsd(roundUp(power(w, r)));
      else if (d.calc === "heat") el.textContent = fmtUsd(heat(w, r));
      else if (d.calc === "rate") el.textContent = fmtRate(r);
    });
  }
  function init() {
    var r = getRate(), forms = document.querySelectorAll("form.ratebox");
    [].forEach.call(forms, function (f) {
      f.hidden = false; var i = f.querySelector("input"); i.value = r;
      i.addEventListener("input", function () {
        var v = parseFloat(i.value); if (!(v >= 0 && v <= 2)) return;
        try { localStorage.setItem(KEY, String(v)); } catch (e) {}
        [].forEach.call(forms, function (g) { var j = g.querySelector("input"); if (j !== i) j.value = i.value; });
        apply(v);
      });
      f.addEventListener("submit", function (e) { e.preventDefault(); });
    });
    apply(r);
  }
  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", init); else init();
})(typeof window !== "undefined" ? window : globalThis);
