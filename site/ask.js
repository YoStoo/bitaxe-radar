// "Ask Bitaxe Radar" box on /ask/. Sends the question to our Worker (POST /ask) and shows the answer.
// window.RADAR_ASK = {url: ".../ask"} is written into the page by build_site.py.
(function () {
  "use strict";
  var cfg = window.RADAR_ASK, form = document.getElementById("ask-form");
  if (!cfg || !form) return;
  var box = form.querySelector("textarea"), btn = form.querySelector("button"), out = document.getElementById("ask-answer");

  function show(text, links, note) {
    out.textContent = "";                               // textContent shows it as plain text, so an answer can never inject code
    var p = document.createElement("p"); p.textContent = text; out.appendChild(p);
    (links || []).forEach(function (id) {
      var a = document.createElement("a"); a.href = "/models/" + encodeURIComponent(id) + "/"; a.textContent = id;
      out.appendChild(a); out.appendChild(document.createTextNode(" "));
    });
    if (note) { var s = document.createElement("p"); s.className = "hint"; s.textContent = note; out.appendChild(s); }
  }

  form.addEventListener("submit", function (e) {
    e.preventDefault();
    var q = box.value.trim();
    if (!q) return;
    btn.disabled = true; show("Thinking...");
    fetch(cfg.url, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ question: q }) })
      .then(function (r) { return r.json(); })
      .then(function (d) {
        if (!d.ok) return show(d.error || "Something went wrong.");
        var note = (d.in_data ? "From our price data" : "Our data didn't cover this") + " · confidence: " + d.confidence +
          " · data updated " + new Date(d.data_updated).toLocaleString() + ". AI answers can be wrong; check the miner page.";
        show(d.answer, d.models_mentioned, note);
      })
      .catch(function () { show("Ask isn't reachable right now. Try again later."); })
      .then(function () { btn.disabled = false; });
  });
})();
