// "Ask Bitaxe Radar" box on /ask/. Uses window.RadarAsk (ask-api.js).
(function () {
  "use strict";
  var form = document.getElementById("ask-form");
  if (!form || !window.RadarAsk) return;
  var box = form.querySelector("textarea"), btn = form.querySelector("button"), out = document.getElementById("ask-answer");

  function show(text, links, note) {
    out.textContent = "";
    var p = document.createElement("p"); p.textContent = text; out.appendChild(p);
    (links || []).forEach(function (id) {
      var a = document.createElement("a");
      a.href = "/models/" + encodeURIComponent(id) + "/";
      a.textContent = window.RadarAsk.modelName(id);
      out.appendChild(a); out.appendChild(document.createTextNode(" "));
    });
    if (note) { var s = document.createElement("p"); s.className = "hint"; s.textContent = note; out.appendChild(s); }
  }

  form.addEventListener("submit", function (e) {
    e.preventDefault();
    var q = box.value.trim();
    if (!q) return;
    btn.disabled = true; show("Thinking...");
    window.RadarAsk.ask(q).then(function (d) {
      if (!d.ok) return show(d.error || "Something went wrong.");
      var note = (d.in_data ? "From our price data" : "Our data didn't cover this") + " · confidence: " + d.confidence +
        " · data updated " + new Date(d.data_updated).toLocaleString() + ". AI answers can be wrong; check the miner page.";
      show(d.answer, d.models_mentioned, note);
    }).then(function () { btn.disabled = false; });
  });
})();
