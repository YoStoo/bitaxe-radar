// Home Mining Weekly signup (double opt-in): POST {type:"newsletter", email} + Turnstile token to the same Worker as price alerts.
// Needs window.RADAR_SIGNUP and window.radarBotCheck (both from signup.js, which loads first). The bot check is invisible
// unless Cloudflare needs a click (see signup.js).
(function () {
  "use strict";
  var C = window.RADAR_SIGNUP, form = document.getElementById("nlsignup");
  if (!C || !form || !window.radarBotCheck) return;
  var msg = document.getElementById("nlMsg"), btn = document.getElementById("nlBtn"), email = document.getElementById("nlEmail");
  var bot = window.radarBotCheck(document.getElementById("nlTurnstile"), C.sitekey);
  if ("IntersectionObserver" in window) {
    var io = new IntersectionObserver(function (es) { if (es.some(function (e) { return e.isIntersecting; })) { bot.load(); io.disconnect(); } }, { rootMargin: "400px" });
    io.observe(form);
  } else { bot.load(); }
  form.addEventListener("focusin", bot.load);
  form.addEventListener("submit", function (e) {
    e.preventDefault();
    if (!/^\S+@\S+\.\S+$/.test(email.value)) { msg.textContent = "Please enter a valid email address."; email.focus(); return; }
    btn.disabled = true; msg.textContent = "Checking you're not a bot…";
    bot.get(function (tok) {
      if (!tok) { msg.textContent = "The bot check didn't finish. Please reload the page and try again."; btn.disabled = false; return; }
      msg.textContent = "Sending…";
      fetch(C.workerUrl, {
        method: "POST", headers: { "Content-Type": "application/json", "Accept": "application/json" },
        body: JSON.stringify({ type: "newsletter", email: email.value.trim(), website: document.getElementById("nlWebsite").value, "cf-turnstile-response": tok })
      }).then(function (r) { return r.json().catch(function () { return {}; }).then(function (d) { return { ok: r.ok && d.ok, d: d }; }); })
        .then(function (res) {
          if (res.ok) { msg.textContent = res.d.message || "Check your inbox to confirm."; email.value = ""; }
          else { msg.textContent = res.d.error || "Something went wrong. Please try again."; }
        })
        .catch(function () { msg.textContent = "Network error. Please try again."; })
        .then(function () { btn.disabled = false; bot.reset(); });
    });
  });
})();
