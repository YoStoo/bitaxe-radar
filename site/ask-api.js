// Shared Ask helper. window.RADAR_ASK = {url} is set by build_site.py on every page.
// ask(question) -> Promise<{ok, answer, models_mentioned, confidence, in_data, data_updated, error}>
(function (w) {
  "use strict";
  var MAX = 300;

  function ask(question) {
    var cfg = w.RADAR_ASK;
    if (!cfg || !cfg.url) return Promise.resolve({ ok: false, error: "Ask isn't set up on this page." });
    var q = String(question || "").replace(/\s+/g, " ").trim();
    if (!q) return Promise.resolve({ ok: false, error: "Please type a question." });
    if (q.length > MAX) return Promise.resolve({ ok: false, error: "Keep it under " + MAX + " characters." });
    return fetch(cfg.url, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ question: q })
    }).then(function (r) {
      return r.json().then(function (d) {
        if (!d || typeof d !== "object") return { ok: false, error: "Ask isn't reachable right now. Try again later." };
        return d;
      }, function () {
        return { ok: false, error: "Ask isn't reachable right now. Try again later." };
      });
    }).catch(function () {
      return { ok: false, error: "Ask isn't reachable right now. Try again later." };
    });
  }

  w.RadarAsk = { ask: ask, MAX: MAX };
})(window);
