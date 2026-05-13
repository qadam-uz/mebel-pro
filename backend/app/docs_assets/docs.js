/* Progressive enhancement for the docs site (app/docs_site.py):
   (1) filter the left nav as you type in the header search box, and
   (2) highlight the section you're reading in the "on this page" rail. */
(function () {
  "use strict";

  // --- (1) filter the sidebar nav -----------------------------------------
  var search = document.getElementById("docs-search");
  var nav = document.querySelector("nav.side");
  if (search && nav) {
    var anchors = [].slice.call(nav.querySelectorAll("a"));
    var groups = [].slice.call(nav.querySelectorAll("details"));
    function applyFilter() {
      var q = search.value.trim().toLowerCase();
      anchors.forEach(function (a) {
        var hit = !q || a.textContent.toLowerCase().indexOf(q) !== -1;
        var li = a.closest("li");
        if (li) li.classList.toggle("hidden", !hit);
      });
      groups.forEach(function (d) {
        var visible = [].some.call(d.querySelectorAll("a"), function (a) {
          var li = a.closest("li");
          return li && !li.classList.contains("hidden");
        });
        d.classList.toggle("hidden", !visible);
        if (q && visible) d.open = true;
      });
    }
    search.addEventListener("input", applyFilter);
    // tapping a link closes the mobile nav drawer
    nav.addEventListener("click", function (e) {
      if (e.target.closest && e.target.closest("a")) {
        var toggle = document.getElementById("nav-toggle");
        if (toggle) toggle.checked = false;
      }
    });

    // ⌘K / Ctrl+K → focus & select the filter; Esc while focused → clear & blur.
    var isMac = /Mac|iPhone|iPad|iPod/.test(navigator.platform || navigator.userAgent || "");
    search.placeholder = "Filter pages…  " + (isMac ? "⌘K" : "Ctrl+K");
    document.addEventListener("keydown", function (e) {
      if ((e.key === "k" || e.key === "K") && (isMac ? e.metaKey : e.ctrlKey) && !e.altKey) {
        e.preventDefault();
        search.focus();
        search.select();
      } else if (e.key === "Escape" && document.activeElement === search) {
        if (search.value) {
          search.value = "";
          applyFilter();
        } else {
          search.blur();
        }
      }
    });
  }

  // --- (2) "on this page" scroll-spy --------------------------------------
  var tocAnchors = [].slice.call(document.querySelectorAll("aside.toc a[href^='#']"));
  if (tocAnchors.length) {
    var byId = {};
    var headings = [];
    tocAnchors.forEach(function (a) {
      var raw = a.getAttribute("href").slice(1);
      var id = raw && decodeURIComponent(raw);
      var el = id && document.getElementById(id);
      if (el) { byId[id] = a; headings.push(el); }
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
})();
