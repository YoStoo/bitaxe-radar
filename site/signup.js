// Price-alert signup for the pre-rendered pages (model pages). Same flow as the home page form in app.js:
// double opt-in, Cloudflare Turnstile bot check, POST to the Cloudflare Worker. Config comes from build_site.py,
// which reads WORKER_URL / TURNSTILE_SITEKEY from app.js and writes window.RADAR_SIGNUP into the page.
// Shared Turnstile loader: the script is injected once even when a page has both the alerts and newsletter forms.
window.radarTurnstileReady = window.radarTurnstileReady || (function () {
  var q = [], state = 0;
  return function (cb) {
    if (state === 2) return cb();
    q.push(cb);
    if (state) return; state = 1;
    window.onTurnstileLoaded = function () { state = 2; q.splice(0).forEach(function (f) { f(); }); };
    var s = document.createElement("script");
    s.src = "https://challenges.cloudflare.com/turnstile/v0/api.js?render=explicit&onload=onTurnstileLoaded"; s.async = true; s.defer = true;
    document.head.appendChild(s);
  };
})();
(function () {
  "use strict";
  var tsReady = window.radarTurnstileReady;
  var C = window.RADAR_SIGNUP, form = document.getElementById("signup");
  if (!C || !form) return;
  var msg = document.getElementById("signupMsg"), btn = document.getElementById("signupBtn");
  var email = document.getElementById("email"), price = document.getElementById("alertPrice"), model = document.getElementById("alertModel");
  var tsHost = document.getElementById("turnstile"), tsWidget = null, loaded = false;

  function renderTurnstile() { if (window.turnstile && !tsWidget) tsWidget = window.turnstile.render(tsHost, { sitekey: C.sitekey, theme: "dark" }); }
  function loadTurnstile() { if (loaded) return; loaded = true; tsReady(renderTurnstile); }
  // Load the bot-check script only when the form is near the screen (keeps the page fast for readers who never sign up).
  if ("IntersectionObserver" in window) {
    var io = new IntersectionObserver(function (es) { if (es.some(function (e) { return e.isIntersecting; })) { loadTurnstile(); io.disconnect(); } }, { rootMargin: "400px" });
    io.observe(form);
  } else { loadTurnstile(); }
  form.addEventListener("focusin", loadTurnstile);

  form.addEventListener("submit", function (e) {
    e.preventDefault(); loadTurnstile();
    var tok = form.querySelector('[name="cf-turnstile-response"]');
    var p = Number(price.value);
    if (!/^\S+@\S+\.\S+$/.test(email.value)) { msg.textContent = "Please enter a valid email address."; email.focus(); return; }
    if (!(p >= 1 && p <= 100000)) { msg.textContent = "Please enter a target price in USD (1 to 100000)."; price.focus(); return; }
    if (!tok || !tok.value) { msg.textContent = "Please wait for the bot check to finish, then try again."; return; }
    btn.disabled = true; msg.textContent = "Sending…";
    fetch(C.workerUrl, {
      method: "POST", headers: { "Content-Type": "application/json", "Accept": "application/json" },
      body: JSON.stringify({ email: email.value.trim(), model: model.value, target_price: p, website: document.getElementById("website").value, "cf-turnstile-response": tok.value })
    }).then(function (r) { return r.json().catch(function () { return {}; }).then(function (d) { return { ok: r.ok && d.ok, d: d }; }); })
      .then(function (res) {
        if (res.ok) { msg.textContent = res.d.message || "Check your inbox to confirm."; email.value = ""; price.value = ""; }
        else { msg.textContent = res.d.error || "Something went wrong. Please try again."; }
      })
      .catch(function () { msg.textContent = "Network error. Please try again."; })
      .then(function () { btn.disabled = false; if (window.turnstile && tsWidget != null) window.turnstile.reset(tsWidget); });
  });
})();
