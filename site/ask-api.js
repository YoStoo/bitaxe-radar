// Shared Ask helper. window.RADAR_ASK = {url, names?} is set by build_site.py on every page.
// ask(question, history?) -> Promise<{ok, answer, models_mentioned, confidence, in_data, data_updated, error}>
// history is optional: [{role:"user"|"assistant", content:"..."}, ...] (last ~6 turns).
// modelName(id) -> friendly label from RADAR_ASK.names, else window.RADAR, else the id.
(function (w) {
  "use strict";
  var MAX = 300;

  function modelName(id) {
    var names = (w.RADAR_ASK && w.RADAR_ASK.names) || {};
    if (names[id]) return names[id];
    var m = w.RADAR && w.RADAR.latest && w.RADAR.latest.models && w.RADAR.latest.models[id];
    if (m && m.name) return String(m.name).replace(/\s*\(.*\)\s*$/, "").trim();
    return id;
  }

  // signal is optional (AbortSignal). It is not sent to the Worker; it only cancels the browser fetch.
  function ask(question, history, signal) {
    var cfg = w.RADAR_ASK;
    if (!cfg || !cfg.url) return Promise.resolve({ ok: false, error: "Ask isn't set up on this page." });
    var q = String(question || "").replace(/\s+/g, " ").trim();
    if (!q) return Promise.resolve({ ok: false, error: "Please type a question." });
    if (q.length > MAX) return Promise.resolve({ ok: false, error: "Keep it under " + MAX + " characters." });
    var body = { question: q };
    if (Array.isArray(history) && history.length) body.history = history;
    var opts = {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body)
    };
    if (signal) opts.signal = signal;
    return fetch(cfg.url, opts).then(function (r) {
      return r.json().then(function (d) {
        if (!d || typeof d !== "object") return { ok: false, error: "Ask isn't reachable right now. Try again later." };
        return d;
      }, function () {
        return { ok: false, error: "Ask isn't reachable right now. Try again later." };
      });
    }).catch(function (err) {
      if (err && err.name === "AbortError") return { ok: false, aborted: true };
      return { ok: false, error: "Ask isn't reachable right now. Try again later." };
    });
  }

  w.RadarAsk = { ask: ask, MAX: MAX, modelName: modelName };
})(window);
