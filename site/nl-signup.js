// Home Mining Weekly signup (double opt-in): POST {type:"newsletter", email} + Turnstile token to the same Worker as price alerts.
// Needs window.RADAR_SIGNUP and window.radarTurnstileReady (both from signup.js, which loads first).
(function () {
  "use strict";
  var C = window.RADAR_SIGNUP, form = document.getElementById("nlsignup");
  if (!C || !form || !window.radarTurnstileReady) return;
  var msg = document.getElementById("nlMsg"), btn = document.getElementById("nlBtn"), email = document.getElementById("nlEmail");
  var tsHost = document.getElementById("nlTurnstile"), tsWidget = null, loaded = false;
  function load() { if (loaded) return; loaded = true; window.radarTurnstileReady(function () { if (tsWidget == null) tsWidget = window.turnstile.render(tsHost, { sitekey: C.sitekey, theme: "dark" }); }); }
  if ("IntersectionObserver" in window) {
    var io = new IntersectionObserver(function (es) { if (es.some(function (e) { return e.isIntersecting; })) { load(); io.disconnect(); } }, { rootMargin: "400px" });
    io.observe(form);
  } else { load(); }
  form.addEventListener("focusin", load);
  form.addEventListener("submit", function (e) {
    e.preventDefault(); load();
    var tok = form.querySelector('[name="cf-turnstile-response"]');
    if (!/^\S+@\S+\.\S+$/.test(email.value)) { msg.textContent = "Please enter a valid email address."; email.focus(); return; }
    if (!tok || !tok.value) { msg.textContent = "Please wait for the bot check to finish, then try again."; return; }
    btn.disabled = true; msg.textContent = "Sending…";
    fetch(C.workerUrl, {
      method: "POST", headers: { "Content-Type": "application/json", "Accept": "application/json" },
      body: JSON.stringify({ type: "newsletter", email: email.value.trim(), website: document.getElementById("nlWebsite").value, "cf-turnstile-response": tok.value })
    }).then(function (r) { return r.json().catch(function () { return {}; }).then(function (d) { return { ok: r.ok && d.ok, d: d }; }); })
      .then(function (res) {
        if (res.ok) { msg.textContent = res.d.message || "Check your inbox to confirm."; email.value = ""; }
        else { msg.textContent = res.d.error || "Something went wrong. Please try again."; }
      })
      .catch(function () { msg.textContent = "Network error. Please try again."; })
      .then(function () { btn.disabled = false; if (window.turnstile && tsWidget != null) window.turnstile.reset(tsWidget); });
  });
})();
