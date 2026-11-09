// "Ask Bitaxe Radar" box on /ask/. Uses window.RadarAsk (ask-api.js).
(function () {
  "use strict";
  var form = document.getElementById("ask-form");
  if (!form || !window.RadarAsk) return;
  var box = form.querySelector("textarea"), btn = form.querySelector("button"), out = document.getElementById("ask-answer");
  var history = []; // [{role, content}, ...] last few turns on this page

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

  function noteFor(d) {
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

  form.addEventListener("submit", function (e) {
    e.preventDefault();
    var q = box.value.trim();
    if (!q) return;
    btn.disabled = true; show("Thinking...");
    window.RadarAsk.ask(q, history).then(function (d) {
      if (!d.ok) return show(d.error || "Something went wrong.");
      history.push({ role: "user", content: q });
      history.push({ role: "assistant", content: d.answer });
      if (history.length > 6) history = history.slice(-6);
      show(d.answer, d.models_mentioned, noteFor(d));
    }).then(function () { btn.disabled = false; });
  });
})();
