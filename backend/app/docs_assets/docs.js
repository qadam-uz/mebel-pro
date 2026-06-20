/* Progressive enhancement for the docs site (app/docs_site.py):
   (1) ⌘K / Ctrl+K opens a search modal that ranks pages from the JSON index
       served at /docs/_search.json, and
   (2) highlights the section you're reading in the "on this page" rail. */
(function () {
  "use strict";

  // Mount prefix ("/docs"), injected by the page shell so search + crumbs
  // resolve against it.
  var PREFIX = String(window.__DOCS_PREFIX__ || "/docs").replace(/\/+$/, "");
  var PREFIX_RE = new RegExp(
    "^" + PREFIX.replace(/[.*+?^${}()|[\]\\]/g, "\\$&") + "\\/?"
  );

  // --- (1) ⌘K search modal ------------------------------------------------
  var trigger = document.getElementById("docs-search-trigger");
  var modal = document.getElementById("docs-search-modal");
  var input = document.getElementById("docs-search-input");
  var results = document.getElementById("docs-search-results");
  var kbdHint = document.getElementById("docs-search-kbd");

  if (trigger && modal && input && results) {
    var isMac = /Mac|iPhone|iPad|iPod/.test(navigator.platform || navigator.userAgent || "");
    if (kbdHint && !isMac) kbdHint.textContent = "Ctrl+K";

    var index = null;        // [{title, url, headings:[...], text}]
    var indexPromise = null;
    var rendered = [];       // result items currently in the DOM
    var activeIndex = -1;
    var lastTrigger = null;  // element to restore focus to on close

    function loadIndex() {
      if (index) return Promise.resolve(index);
      if (indexPromise) return indexPromise;
      indexPromise = fetch(PREFIX + "/_search.json", { credentials: "same-origin" })
        .then(function (r) { return r.ok ? r.json() : []; })
        .then(function (data) { index = Array.isArray(data) ? data : []; return index; })
        .catch(function () { index = []; return index; });
      return indexPromise;
    }

    function escapeHTML(s) {
      return String(s).replace(/[&<>"']/g, function (c) {
        return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c];
      });
    }

    function tokenize(q) {
      return q.toLowerCase().split(/\s+/).filter(Boolean);
    }

    function humanize(s) {
      return s.replace(/[-_]+/g, " ").replace(/\b\w/g, function (c) { return c.toUpperCase(); });
    }

    function crumb(url) {
      var parts = url.replace(PREFIX_RE, "").split("/").filter(Boolean);
      return parts.slice(0, -1).map(humanize).join(" › ");
    }

    function highlight(text, tokens) {
      var esc = escapeHTML(text);
      tokens.forEach(function (t) {
        if (!t) return;
        var re = new RegExp("(" + t.replace(/[.*+?^${}()|[\]\\]/g, "\\$&") + ")", "gi");
        esc = esc.replace(re, "<mark>$1</mark>");
      });
      return esc;
    }

    function snippet(text, tokens) {
      if (!text) return "";
      var lo = text.toLowerCase();
      var first = -1;
      for (var i = 0; i < tokens.length; i++) {
        var at = lo.indexOf(tokens[i]);
        if (at !== -1 && (first === -1 || at < first)) first = at;
      }
      if (first === -1) return highlight(text.slice(0, 160) + (text.length > 160 ? "…" : ""), tokens);
      var start = Math.max(0, first - 70);
      var end = Math.min(text.length, first + 130);
      var slice = (start > 0 ? "…" : "") + text.slice(start, end) + (end < text.length ? "…" : "");
      return highlight(slice, tokens);
    }

    function score(doc, tokens) {
      var title = doc.title.toLowerCase();
      var headings = (doc.headings || []).join(" ").toLowerCase();
      var text = (doc.text || "").toLowerCase();
      var s = 0;
      for (var i = 0; i < tokens.length; i++) {
        var t = tokens[i];
        if (!t) continue;
        if (title === t) s += 200;
        else if (title.indexOf(t) === 0) s += 120;
        else if (title.indexOf(t) !== -1) s += 60;
        if (headings.indexOf(t) !== -1) s += 25;
        if (text.indexOf(t) !== -1) s += 5;
        if (title.indexOf(t) === -1 && headings.indexOf(t) === -1 && text.indexOf(t) === -1) {
          return -1;  // every token must hit somewhere
        }
      }
      return s;
    }

    function search(q) {
      var tokens = tokenize(q);
      if (!tokens.length || !index) return [];
      var hits = [];
      for (var i = 0; i < index.length; i++) {
        var doc = index[i];
        var s = score(doc, tokens);
        if (s > 0) hits.push({ doc: doc, score: s });
      }
      hits.sort(function (a, b) { return b.score - a.score; });
      return hits.slice(0, 12).map(function (h) { return h.doc; });
    }

    function render(q) {
      var tokens = tokenize(q);
      var hits = search(q);
      results.innerHTML = "";
      rendered = [];
      if (!q) {
        results.innerHTML = '<div class="search-modal-empty">Type to search the documentation.</div>';
        activeIndex = -1;
        return;
      }
      if (!hits.length) {
        results.innerHTML = '<div class="search-modal-empty">No matches for <em>' +
          escapeHTML(q) + "</em>.</div>";
        activeIndex = -1;
        return;
      }
      hits.forEach(function (doc, i) {
        var a = document.createElement("a");
        a.href = doc.url;
        a.className = "search-modal-row";
        a.setAttribute("role", "option");
        a.setAttribute("data-i", String(i));
        var c = crumb(doc.url);
        a.innerHTML =
          (c ? '<div class="search-modal-crumb">' + escapeHTML(c) + "</div>" : "") +
          '<div class="search-modal-title">' + highlight(doc.title, tokens) + "</div>" +
          '<div class="search-modal-snippet">' + snippet(doc.text || "", tokens) + "</div>";
        results.appendChild(a);
        rendered.push(a);
      });
      setActive(0);
    }

    function setActive(i) {
      if (!rendered.length) { activeIndex = -1; return; }
      if (i < 0) i = rendered.length - 1;
      if (i >= rendered.length) i = 0;
      if (activeIndex >= 0 && rendered[activeIndex]) rendered[activeIndex].classList.remove("active");
      activeIndex = i;
      var el = rendered[activeIndex];
      el.classList.add("active");
      // keep the active row in view inside the scrollable results pane
      var pr = results.getBoundingClientRect();
      var er = el.getBoundingClientRect();
      if (er.top < pr.top) el.scrollIntoView({ block: "start" });
      else if (er.bottom > pr.bottom) el.scrollIntoView({ block: "end" });
    }

    function openModal() {
      lastTrigger = document.activeElement;
      modal.hidden = false;
      document.body.classList.add("search-open");
      input.value = "";
      render("");
      // defer focus a tick so the just-shown input is actually focusable
      setTimeout(function () { input.focus(); }, 0);
      loadIndex();
    }

    function closeModal() {
      if (modal.hidden) return;
      modal.hidden = true;
      document.body.classList.remove("search-open");
      results.innerHTML = "";
      rendered = [];
      activeIndex = -1;
      if (lastTrigger && typeof lastTrigger.focus === "function") lastTrigger.focus();
    }

    trigger.addEventListener("click", openModal);
    modal.addEventListener("click", function (e) {
      var t = e.target;
      if (t && t.getAttribute && t.getAttribute("data-dismiss")) closeModal();
    });
    input.addEventListener("input", function () { render(input.value.trim()); });
    input.addEventListener("keydown", function (e) {
      if (e.key === "ArrowDown") { e.preventDefault(); setActive(activeIndex + 1); }
      else if (e.key === "ArrowUp") { e.preventDefault(); setActive(activeIndex - 1); }
      else if (e.key === "Enter") {
        if (activeIndex >= 0 && rendered[activeIndex]) {
          e.preventDefault();
          window.location.href = rendered[activeIndex].href;
        }
      } else if (e.key === "Escape") {
        e.preventDefault();
        closeModal();
      }
    });

    document.addEventListener("keydown", function (e) {
      if ((e.key === "k" || e.key === "K") && (isMac ? e.metaKey : e.ctrlKey) && !e.altKey) {
        e.preventDefault();
        if (modal.hidden) openModal();
        else closeModal();
      } else if (e.key === "Escape" && !modal.hidden) {
        e.preventDefault();
        closeModal();
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

  // close the mobile nav drawer when a link inside it is tapped
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
