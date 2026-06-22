/* Progressive enhancement for the docs site:
   highlight the current "On this page" heading and close mobile nav after a tap. */
(function () {
  "use strict";

  var tocAnchors = [].slice.call(document.querySelectorAll("aside.toc a[href^='#']"));
  if (tocAnchors.length) {
    var byId = {};
    var headings = [];
    tocAnchors.forEach(function (a) {
      var raw = a.getAttribute("href").slice(1);
      var id = raw && decodeURIComponent(raw);
      var el = id && document.getElementById(id);
      if (el) {
        byId[id] = a;
        headings.push(el);
      }
    });
    var active = null;
    function mark(a) {
      if (active === a) return;
      if (active) active.classList.remove("active");
      active = a || null;
      if (active) active.classList.add("active");
    }
    function spy() {
      if (!headings.length) return;
      var offset = 92;
      var best = headings[0];
      for (var i = 0; i < headings.length; i++) {
        if (headings[i].getBoundingClientRect().top - offset <= 1) best = headings[i];
        else break;
      }
      mark(byId[best.id]);
    }
    window.addEventListener("scroll", spy, { passive: true });
    window.addEventListener("resize", spy, { passive: true });
    spy();
  }

  var side = document.querySelector("nav.side");
  if (side) {
    side.addEventListener("click", function (e) {
      if (e.target.closest && e.target.closest("a")) {
        var toggle = document.getElementById("nav-toggle");
        if (toggle) toggle.checked = false;
      }
    });
  }
})();
