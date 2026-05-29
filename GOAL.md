  # Goal: self-improve prototype-full

  Polish `web/prototypes/prototype-full/` to a production-grade demo:
  catch UI/UX inconsistencies and copy issues, fix them in place, verify
  visually. Run up to **3 review → fix → verify cycles**, stopping early
  once a clean pass finds nothing.

  ## Context (read first, in this order)

  1. `AGENTS.md` — repo conventions, docs-as-source-of-truth rule.
  2. `docs/index.md`, `docs/architecture.md`, `docs/scope.md` — what the
     product is.
  3. `docs/ref/features/*.md` and `docs/ref/entities/*.md` on demand
     when a page's behaviour is ambiguous.
  4. `web/prototypes/prototype-full/` — the artefact you're polishing.
     Static HTML + `assets/data.js`. Served via
     `python3 -m http.server 8001` from the prototype dir.

  The prototype's UI language is **Uzbek**. Domain terms stay English
  (material, panel, edge, order, branch, status values, IDs). Treat
  this exactly like `docs_uz/` — Uzbek grammar carrying English terms.

  ## Scope rules

  - **Polish, don't redesign.** Don't add screens, flows, fields, or
    features. Fix what's broken or inconsistent against the docs.
  - **Docs win on conflicts.** If a screen contradicts `docs/`, fix the
    screen. If the docs themselves are wrong, stop and surface the
    conflict — don't silently diverge.
  - **No new dependencies.** Vanilla HTML/CSS/JS, the existing helpers.
  - **Don't break existing flows.** If a fix risks a flow elsewhere,
    trace it before committing the change.

  ## What to look for (per cycle, scan ALL pages across all 3 personas:
  client, workshop, admin)

  ### Copy quality (product-owner voice)

  - **Brief and focused** — every label, hint, empty state, error,
    toast, button. Cut hedging, cut filler, cut redundancy. Voice is
    calm and direct, not chatty.
  - **Grammatically correct Uzbek** — no awkward calques from English,
    no machine-translation residue. Latin orthography, apostrophes
    consistent (`oʻ` vs `o'` — pick one and apply everywhere).
  - **Consistent terminology** — same concept, same word, every screen.
    Build a quick term map on the first cycle; reuse it.
  - **Tone parity with docs** — if the docs say "panel" not "list",
    the UI says "panel" not "list". Sweep for legacy terms.

  ### Visual consistency

  - Spacing scale, type scale, colour tokens, border radii, shadow use,
    icon weights — used the same way across pages.
  - Status badges, chips, tags — same visual treatment per status, same
    ordering of states in legends.
  - Tables: column alignment (numbers right, text left), header style,
    empty-row treatment.
  - Forms: label position, hint position, error position, required mark.
  - Buttons: primary/secondary/ghost usage, destructive treatment,
    loading and disabled states present where they matter.

  ### Interaction & state coverage

  - Empty states with helpful next action.
  - Loading states where data would load in real backend.
  - Error states with recovery affordance, not just a red line.
  - Hover, focus, active visible — accessible focus ring on keyboard.

  ### Responsiveness — 5 breakpoints

  Test every page at each width and confirm nothing clips, overflows,
  or becomes unusable:

  | Tag        | Width   | Represents                  |
  |------------|---------|-----------------------------|
  | mobile-sm  | 360px   | small Android, iPhone SE    |
  | mobile     | 414px   | standard phone              |
  | tablet     | 768px   | iPad portrait               |
  | laptop     | 1280px  | 13" laptop                  |
  | desktop    | 1680px  | external monitor / wide     |

  Touch targets ≥ 40px on mobile-sm and mobile. Tables must scroll
  horizontally rather than squash; modals must fit the viewport with
  internal scroll, not push past it.

  ## The cycle (repeat up to 3 times)

  For each cycle:

  1. **Review.** Start the static server if not running. Open the
     prototype in a real browser via `mcp__claude-in-chrome`. Walk
     every page across all 3 personas at all 5 breakpoints. Take
     screenshots at boundaries. Log every finding with `file:line` +
     short description + severity (blocker / polish / nit). Use Agent
     subagents with `Explore` for per-persona sweeps to keep main
     context lean.
  2. **Fix.** Edit files in place. Group edits by file. Don't refactor
     for refactoring's sake — only touch what the findings call for.
     For copy changes, write the new Uzbek string in full, don't
     paraphrase in the diff message.
  3. **Verify.** Reload each touched page in the browser. Re-check the
     specific finding at the breakpoints it occurred at. Screenshot
     before/after for any visual fix. If a fix introduces a new issue,
     it goes on the next cycle's review list.

  **Stop early** if a review pass finds zero blockers and ≤ 2 nits, or
  if the same nits survive two consecutive cycles (means they're
  debatable preferences, not defects — surface them to the user).

  ## Report (after each cycle and at the end)

  Per cycle, post a compact summary:

  - Cycle N — what was scanned, count of findings by severity.
  - What was fixed, grouped by file (paths + 1-line description each).
  - What's deferred to the next cycle and why.
  - Screenshots: 2-4 before/after pairs for the biggest fixes.

  Final report:

  - Total findings, total fixes, files touched.
  - Any docs ↔ prototype conflicts surfaced (NOT auto-fixed in docs).
  - Anything you intentionally left alone, with reason.
  - Provide these in the REPORT.md file

  ## Hard constraints

  - **No commits.** User commits manually.
  - **No new files** unless replacing a page with a clear redirect
    rationale.
  - **No screenshots dumped into the repo.** Keep them in the chat.
  - **No docs edits without a clear conflict** — if you find one,
    raise it and wait for user direction; don't unilaterally rewrite
    canon to match a broken screen.

  Begin with cycle 1, review phase.
