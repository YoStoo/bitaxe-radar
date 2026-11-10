/* Eval dashboard motion. Vanilla JS. Honors prefers-reduced-motion. */
(function () {
  var reduce = window.matchMedia && window.matchMedia("(prefers-reduced-motion: reduce)").matches;

  function onView(el, fn) {
    if (reduce || !("IntersectionObserver" in window)) {
      el.classList.add("is-inview");
      if (fn) fn(el);
      return;
    }
    var io = new IntersectionObserver(function (entries) {
      entries.forEach(function (e) {
        if (!e.isIntersecting) return;
        e.target.classList.add("is-inview");
        if (fn) fn(e.target);
        io.unobserve(e.target);
      });
    }, { threshold: 0.2, rootMargin: "0px 0px -8% 0px" });
    io.observe(el);
  }

  function countUp(el) {
    var pass = Number(el.getAttribute("data-pass"));
    var total = Number(el.getAttribute("data-total"));
    if (!isFinite(pass) || !isFinite(total)) return;
    if (reduce) {
      el.textContent = pass + "/" + total;
      return;
    }
    var start = null, dur = 900;
    function tick(now) {
      if (start === null) start = now;
      var t = Math.min(1, (now - start) / dur);
      var eased = 1 - Math.pow(1 - t, 3);
      el.textContent = Math.round(pass * eased) + "/" + total;
      if (t < 1) requestAnimationFrame(tick);
    }
    el.textContent = "0/" + total;
    requestAnimationFrame(tick);
  }

  document.querySelectorAll(".eval-reveal, .eval-score, .eval-ba article, .eval-chart").forEach(function (el) {
    onView(el);
  });
  document.querySelectorAll(".eval-count").forEach(function (el) {
    var card = el.closest(".eval-score") || el;
    onView(card, function () { countUp(el); });
  });
})();
