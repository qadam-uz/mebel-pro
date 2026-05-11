# Forms & System States

## When this matters

Designing or reviewing any form (a single search field counts), any validation, any error message — *and* the states every data-bearing surface can be in: empty, loading, partial, error, success. Most of a product's value flows through forms, and most of a product's *frustration* lives in the states people forget to design. A list, table, card grid, or detail screen that's only been designed in its full, happy state is half-finished.

## Principles — forms

### 1. Every input has a visible, persistent label

A label that's always there, above or beside the field. **Placeholder text is not a label.** It disappears the moment the user focuses or types (so they lose track of what the field was for); it's typically rendered too low-contrast to read comfortably; screen readers treat it inconsistently; and it leaves the user nothing to check their answer against when reviewing a filled-in form. Placeholders are for *examples or format hints* — `e.g. jane@work.com`, `MM / YY` — shown *in addition to* a real label, never instead of one.

### 2. Ask for the minimum, structure it well, default the obvious

Every field is friction and a chance to bail — so cut the ones you don't truly need *now*, and don't ask for what you can derive (city/state from a postcode; the date from "today"). Group related fields, and order them the way the user thinks about them. Pre-fill and default whatever you reasonably can. Use the *right control* for the data (a toggle for on/off, a stepper for small numbers, a select for one-of-many, checkboxes for any-of-many) — and on a text field, the *right input type* (`email`, `tel`, `number`, `url`, `date`, …) so mobile keyboards adapt and the browser can help; set `autocomplete` so saved data fills in. Mark which fields are *optional* rather than starring the (usually more numerous) required ones — whichever set is smaller, that's the one to label.

### 3. Validate at a humane moment, and help before erroring

Don't yell at someone for an incomplete email while they're still typing it. Validate a field on **blur** (when they move on) or at **submit**. For fields with rules, show the rules *up front* ("8+ characters, at least one number") so the user can satisfy them *before* being told off — and turn that into live, positive feedback as each rule is met. Inline validation *as you type* is acceptable only where live feedback genuinely helps rather than nags — a password-strength meter, a username-availability check — not for ordinary text fields.

### 4. Errors: at the field, plain language, cause + fix, and don't lose the user's work

A form error message:

- **Sits immediately next to the field it's about.** A summary at the top is good *as well* for long forms — but never *only* a top summary the user has to map back to a field eight rows down.
- **Names what's wrong and how to fix it** — "Password needs at least one number", not "Invalid input"; "That email is already registered — sign in instead?", not "Error".
- **Is announced to screen readers** (associated with the field, in a live region).
- On a failed submit, **focus moves to the first invalid field** and it scrolls into view — don't make the user hunt.
- **Never clear the form on error.** Preserve everything the user typed; making them retype it makes them slower *and* angrier.

### 5. Submission has its own states, and it's double-submit-safe

The submit button: **rest → busy** (disabled, with a spinner or label change, so it physically cannot be clicked again) → **success** (an actual confirmation — a message, a redirect, a visible state change — not just silently returning to rest) *or* **error** (the form re-enabled, errors shown, focus moved, input preserved). For slow submits, say what's happening. Disabling on click is the first line of defence against the double-submit; server-side idempotency is the backstop.

### 6. Destructive form actions are clearly the dangerous one

Delete, discard, reset — give them a danger color, visual separation from the routine actions, and a label naming the consequence ("Discard draft", "Delete account"), plus either a confirmation or an undo (see `interaction-and-touch.md`). Don't let "Reset" sit flush against "Submit" where one slip wipes everything the user typed.

## Principles — system states

### 7. Design *all* of these for every data surface

Any region that shows fetched or generated data has more states than "full". Design each:

- **Empty (first-run)** — nothing here *yet*. Don't show a blank, and don't show "No data." Say what goes here, why it's worth having, and give the action to add the first one. This is an onboarding moment, not an error — treat it like one.
- **Empty (no results)** — a filter or search matched nothing. Distinguish it clearly from first-run-empty (the user *did* something; acknowledge that), and offer a way forward — "clear filters", "try a broader term", suggestions.
- **Loading** — prefer a **skeleton shaped like the real content** over a centered spinner: it communicates *what's* coming and *where*, and reads as faster. Reserve the right amount of space so nothing jumps when the data lands (see `layout-and-responsive.md`). Only fall back to a plain spinner for very short or genuinely unstructured waits.
- **Partial / streaming** — show what you have as it arrives; don't block the whole screen waiting on the slowest piece.
- **Error** — say what failed in plain language, whether it's the user's side or yours, and give a way out: **retry**, go back, contact support. An error state with no recovery path is a dead end. And never an infinite spinner that's secretly a permanent failure — *every load that can hang needs a timeout → error path.*
- **Success / confirmation** — completed actions are acknowledged. "Did that actually work?" should never be a question the user has to ask.
- **Stale / offline** (where relevant) — if the data might be out of date or the connection's gone, *say so*, rather than presenting old data as if it's live.

### 8. System status is always visible

The thread running through all of the above (it's Nielsen heuristic #1 for a reason): the interface keeps the user informed about what's happening — what's loading, what saved, what failed, what's in progress — through feedback that's appropriately prominent but not intrusive. Silence is the worst possible status; the user fills the silence with "is it broken?"

## Heuristics & checklist

- Every input: visible persistent label? Right control and `type`? `autocomplete` set? Placeholder (if any) is a *hint* alongside the label, not the label itself?
- Can any field be cut, derived, or defaulted? Are optional/required marked the economical way (label whichever set is smaller)?
- Validation timing humane (blur/submit, not keystroke-nagging)? Are the rules shown *before* they're violated, with positive live feedback as they're met?
- Errors: beside the field, plain-language cause + fix, announced, focus moved to the first bad field, input preserved? Is there a top summary too if the form is long?
- Submit: busy state that blocks double-clicks? Explicit success state? Error state that re-enables, shows errors, preserves input?
- Destructive actions: danger-colored, visually separated, consequence named in the label, confirm-or-undo?
- For *every* data region: are the empty (first-run), empty (no-results), loading, error, and success states designed — not just the full one?
- Does anything load with no timeout and no error path?

## Common mistakes

- **Placeholder as label** — vanishes on focus/typing, low contrast, screen-reader-hostile, nothing to review against.
- **The 20-field form** — asking everything up front; cut, derive, defer.
- **Validation that nags mid-typing** — "invalid email" while they're on character 4.
- **"Invalid input." / "An error occurred."** — names neither the problem nor the fix; might as well say nothing.
- **Errors only summarized at the top** — the user maps "Field 3 is wrong" back to a field rows below.
- **Form cleared on error** — the user retypes everything; now they're angry *and* slower.
- **Submit with no busy state** — double-click, double-submit, duplicate record.
- **Silent success** — the form just resets; the user has no idea it worked and resubmits.
- **"No data."** — a bare blank where a first-run empty state should be teaching and inviting.
- **Centered spinner for everything** — tells the user nothing; a skeleton tells them what's coming and where.
- **Infinite spinner = permanent failure in disguise** — no timeout, no error path; the user waits forever.
- **"Reset" next to "Submit"** — one slip nukes the form.
