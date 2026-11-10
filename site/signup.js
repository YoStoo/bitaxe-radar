// Price-alert signup for the pre-rendered pages (home and model pages): double opt-in, Cloudflare Turnstile bot
// check, POST to the Cloudflare Worker. Config comes from build_site.py, which reads WORKER_URL / TURNSTILE_SITEKEY
// from app.js and writes window.RADAR_SIGNUP into the page.
//
// The bot check is invisible: Turnstile runs with appearance "interaction-only", so nothing shows unless Cloudflare
// actually needs the visitor to click. The Worker still verifies the same cf-turnstile-response token.

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

// One invisible bot check per form. get(cb) calls cb(token), or cb("") if the check failed or timed out.
window.radarBotCheck = window.radarBotCheck || function (host, sitekey) {
  var widget = null, token = "", waiters = [], loaded = false, timer = null;
  function flush() { clearTimeout(timer); timer = null; waiters.splice(0).forEach(function (f) { f(token); }); }
  function load() {
    if (loaded) return; loaded = true;
    window.radarTurnstileReady(function () {
      widget = window.turnstile.render(host, {
        sitekey: sitekey, theme: "dark", appearance: "interaction-only",
        callback: function (t) { token = t; host.classList.remove("ts-show"); flush(); },
        "expired-callback": function () { token = ""; },
        "error-callback": function () { token = ""; flush(); },
        "before-interactive-callback": function () { host.classList.add("ts-show"); clearTimeout(timer); },
        "after-interactive-callback": function () { host.classList.remove("ts-show"); }
      });
    });
  }
  return {
    load: load,
    get: function (cb) {
      load();
      if (token) return cb(token);
      waiters.push(cb);
      if (!timer) timer = setTimeout(flush, 20000);   // never leave the button stuck on "Checking…"
    },
    reset: function () { token = ""; if (window.turnstile && widget != null) window.turnstile.reset(widget); }
  };
};

(function () {
  "use strict";
  var C = window.RADAR_SIGNUP, form = document.getElementById("signup");
  if (!C || !form) return;
  var msg = document.getElementById("signupMsg"), btn = document.getElementById("signupBtn");
  var email = document.getElementById("email"), price = document.getElementById("alertPrice"), model = document.getElementById("alertModel");
  var bot = window.radarBotCheck(document.getElementById("turnstile"), C.sitekey);
  // Load the bot-check script only when the form is near the screen (keeps the page fast for readers who never sign up).
  if ("IntersectionObserver" in window) {
    var io = new IntersectionObserver(function (es) { if (es.some(function (e) { return e.isIntersecting; })) { bot.load(); io.disconnect(); } }, { rootMargin: "400px" });
    io.observe(form);
  } else { bot.load(); }
  form.addEventListener("focusin", bot.load);

  form.addEventListener("submit", function (e) {
    e.preventDefault();
    var p = Number(price.value);
    if (!/^\S+@\S+\.\S+$/.test(email.value)) { msg.textContent = "Please enter a valid email address."; email.focus(); return; }
    if (!(p >= 1 && p <= 100000)) { msg.textContent = "Please enter a target price in USD (1 to 100000)."; price.focus(); return; }
    btn.disabled = true; msg.textContent = "Checking you're not a bot…";
    bot.get(function (tok) {
      if (!tok) { msg.textContent = "The bot check didn't finish. Please reload the page and try again."; btn.disabled = false; return; }
      msg.textContent = "Sending…";
      fetch(C.workerUrl, {
        method: "POST", headers: { "Content-Type": "application/json", "Accept": "application/json" },
        body: JSON.stringify({ email: email.value.trim(), model: model.value, target_price: p, website: document.getElementById("website").value, "cf-turnstile-response": tok })
      }).then(function (r) { return r.json().catch(function () { return {}; }).then(function (d) { return { ok: r.ok && d.ok, d: d }; }); })
        .then(function (res) {
          if (res.ok) { msg.textContent = res.d.message || "Check your inbox to confirm."; email.value = ""; price.value = ""; }
          else { msg.textContent = res.d.error || "Something went wrong. Please try again."; }
        })
        .catch(function () { msg.textContent = "Network error. Please try again."; })
        .then(function () { btn.disabled = false; bot.reset(); });
    });
  });
})();
