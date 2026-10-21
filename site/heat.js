/* Bitaxe Radar room heat calculator. Mirrors heat_need / heat_fit in build_site.py (tests/test_heat_calc.py).
   Rule of thumb only: about 10 W of heat per square foot for an average room with an 8 ft ceiling. */
(function (root) {
  var WPSF = { good: 7, average: 10, poor: 13 }, SQFT_PER_M2 = 10.7639;
  function need(sqft, ins) { return sqft * (WPSF[ins] || WPSF.average); }
  function fit(heatW, needW) {
    var r = heatW / needW;
    if (r > 1.6) return "big";
    if (r >= 0.8) return "fits";
    if (r >= 0.3) return "helps";
    return "small";
  }
  function rank(heatW, needW) { var f = fit(heatW, needW); return { fits: 0, helps: 1, big: 2, small: 3 }[f] * 1e6 + Math.abs(heatW - needW); }
  function commas(x) { return Math.round(x).toLocaleString("en-US"); }
  root.RadarHeat = { need: need, fit: fit, rank: rank, WPSF: WPSF };
  if (typeof document === "undefined") return;

  var LABEL = { fits: "Can heat this room", helps: "Adds warmth, won't heat it alone", big: "More heat than this room needs", small: "Too small for this room" };
  function init() {
    var f = document.getElementById("heat-form"); if (!f) return;
    var a = f.querySelector("#heat-a"), u = f.querySelector("#heat-u"), ins = f.querySelector("#heat-i");
    var list = document.getElementById("heat-list"), rows = [].slice.call(list.querySelectorAll("li[data-w]"));
    function show() {
      var v = parseFloat(a.value); if (!(v > 0 && v < 100000)) return;
      var sqft = u.value === "m2" ? v * SQFT_PER_M2 : v, n = need(sqft, ins.value), shown = 0;
      [].forEach.call(document.querySelectorAll("[data-heat]"), function (el) {
        var k = el.dataset.heat;
        if (k === "w") el.textContent = commas(n) + " W";
        if (k === "btu") el.textContent = commas(n * 3.412) + " BTU/h";
      });
      rows.sort(function (x, y) { return rank(+x.dataset.w, n) - rank(+y.dataset.w, n); });
      rows.forEach(function (li) {
        var ft = fit(+li.dataset.w, n), tag = li.querySelector(".fit");
        tag.textContent = LABEL[ft]; tag.className = "fit f-" + ft;
        li.hidden = ft === "small"; if (!li.hidden) shown++;
        list.appendChild(li);
      });
      document.getElementById("heat-none").hidden = shown > 0;
    }
    a.addEventListener("input", show); u.addEventListener("change", show); ins.addEventListener("change", show);
    f.addEventListener("submit", function (e) { e.preventDefault(); show(); });
    f.hidden = false; show();
  }
  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", init); else init();
})(typeof window !== "undefined" ? window : globalThis);
