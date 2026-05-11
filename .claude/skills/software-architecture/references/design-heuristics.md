# Design heuristics — the construction layer

These are the timeless techniques for keeping a system understandable and changeable. They're
adapted from John Ousterhout's *A Philosophy of Software Design* and related craft, with one
addition the original mostly leaves implicit and this skill insists on: **every one of these is
context-calibrated.** How hard you apply a heuristic scales with the system's operating envelope
(see `SKILL.md`) — lifespan, churn, team size, and how high the stakes are on the axis it touches.
A weekend spike needs almost none of this; a decade-long core system that a dozen people touch
weekly needs all of it, and it's the best ROI in the codebase. Most things are in between.

Read the one or two that bear on what you're shaping right now; you don't need all of them every
time.

**Contents:** 1. Complexity is the enemy · 2. Make modules deep · 3. Hide information; watch for
leakage · 4. Pull complexity downward · 5. Keep interfaces a little general · 6. Make every layer
earn its place · 7. Define errors out of existence · 8. Comments capture what code can't ·
9. Design it twice · 10. Names · 11. Consistency · 12. Make it obvious · 13. Strategic, not
tactical.

---

## 1. Complexity is the enemy

Complexity is anything about a system's structure that makes it hard to understand or modify. You
recognize it by three symptoms:

- **Change amplification** — a conceptually small change requires edits in many places.
- **Cognitive load** — how much you must hold in your head to do something safely.
- **Unknown unknowns** — it isn't even obvious which code you need to touch, or which fact you
  need to know, to make a change correctly. This is the worst one, because you can't see it coming.

It has two root causes: **dependencies** (one piece can't be understood or changed in isolation
from others) and **obscurity** (important information isn't apparent — a hidden invariant, an
implicit ordering, a name that lies). Almost every heuristic below is an attack on one of these.

Complexity is *incremental*: it doesn't arrive in one bad decision, it accretes from dozens of
small concessions, each individually defensible. So you fight it the same way — with many small
refusals, applied continuously, not a big cleanup later. *Context note:* even throwaway code
benefits from low obscurity — you'll be confused by it tomorrow — but the dependency-management
work scales with how long the code lives and how many hands touch it.

## 2. Make modules deep

A module — a function, class, file, package, service — is *deep* when a lot of functionality sits
behind a small interface: the interface is much simpler than the implementation. Depth is the
goal because the interface is the cost everyone pays and the implementation is the cost paid once,
inside.

A *shallow* module is one whose interface is about as complicated as its implementation, or whose
interface costs more to learn than the functionality is worth. Shallow modules don't reduce
complexity, they relocate it — and add the interface you now have to learn on top. **"Classitis"**
— lots of tiny classes each doing almost nothing — is the classic failure: each class looks tidy,
but the *connections* between them become the system's complexity, and you can't understand any
one of them alone.

*The bound:* depth is not "make everything huge." A module with one entry point but forty
unrelated responsibilities is a god object — deep in interface-to-size ratio but a different
disaster. Aim for *deep within a single, nameable responsibility*. If you can't name what a module
is responsible for in a short phrase, it's either too shallow (split nothing — merge it into its
caller) or doing too much (split it along the responsibilities).

*Red flag:* a wrapper class, helper, or "util" that mostly forwards to something else. *Context:*
the more callers a module has and the longer it lives, the more depth pays — a deep interface used
by one caller for a month is over-investment; a deep interface used by twenty callers for years is
the difference between a maintainable system and a swamp.

## 3. Hide information; watch for leakage

Each module should *encapsulate a design decision* — a data format, an algorithm, a wire protocol,
a choice of dependency, a caching strategy — so that decision can change without anything outside
the module noticing. The test: "what does this module know that nothing else has to?"

**Information leakage** is the opposite: the same design decision is reflected in two or more
modules, so now they're coupled through it and a change to it touches all of them. Leakage is
often invisible until the change request arrives — it's a prime source of *unknown unknowns*.

The classic red flag is **temporal decomposition** — structuring code around *the order things
happen* instead of *what knowledge is needed*. A pipeline split into `read-config`, `process`,
`write-output` modules where all three know the config file's format has leaked that format three
ways. The fix: organize around knowledge, not chronology — one module owns the config format,
period. Ask "what must each module know?", never "what happens first?"

*Context:* leakage in a throwaway script costs nothing because there's no future change to suffer
it. Leakage in a long-lived, much-edited system is where most of the maintenance pain comes from —
invest accordingly.

## 4. Pull complexity downward

When there's a hard or ugly part of a problem, the *module* should swallow it rather than push it
up to its callers. A simple interface is worth more than a simple implementation, because the
interface is paid by every caller forever and the implementation is paid once, by you, now. So:
provide sane defaults; handle the edge cases inside; do the messy normalization; absorb the
retries. The module author suffers so the users don't.

*The bound:* this is "pull complexity *downward*," not "pile all complexity into one module." If
absorbing a concern would turn the module into a god object (§2) or hide something the caller
genuinely needs to decide (a security policy, a money-rounding rule, a user-visible trade-off),
that's not pulling complexity down — that's hiding a decision that wasn't yours to make. Pull down
*incidental* complexity; surface *essential* choices.

*Context:* scales with caller count × lifespan, same as depth.

## 5. Keep interfaces a little general

A somewhat general-purpose interface is often *simpler* than a special-purpose one — fewer
methods, cleaner shapes — and it decouples the module from the one caller it happens to have
today. The question to ask: **"what is the simplest interface that covers all my current needs?"**
That usually lands slightly more general than the single use case, and that's good.

*The bound — and this one matters because it's a favorite over-engineering trap:* "a little
general" is driven by *making the interface clean*, not by *speculating about future callers*. A
"framework for everything," a plugin system with one plugin, an abstraction layer over a database
you will never swap — those are special-purpose code wearing a general-purpose costume, and they
add the worst kind of complexity: complexity with no payoff. If generality doesn't make the
interface cleaner *today*, don't add it. (See also: rule of three, in `SKILL.md`.)

## 6. Make every layer earn its place

Adjacent layers in a system should offer *different* abstractions. A layer that presents the same
abstraction as the layer below it isn't adding value, it's adding a hop.

*Red flags, all common and all worth deleting:*
- **Pass-through methods** — a method whose body is mostly `return other.method(sameArgs)`.
- **Pass-through variables** — a parameter threaded through five functions just to reach the sixth
  (consider a context object, or hoisting the dependency).
- **Decorators that don't decorate**, wrappers that wrap exactly one thing and change nothing,
  "manager"/"coordinator"/"service" classes whose job is to call other classes.

Each of these is a layer that took a cut of the complexity budget and produced nothing. Collapse
it. *This is one of the strongest over-engineering smells* — agents and engineers both reach for
"add a layer" as a reflex; the discipline is to make the new layer *change the abstraction*, not
just relay it.

*Context-neutral:* this one applies at every tier. There's no envelope where a pure pass-through
layer is the right call.

## 7. Define errors out of existence

Exception and error handling is one of the largest sources of complexity in real code: every
`try`/`catch`, every `if err != nil`, every `Result` unwrap is a fork in the control flow, and
most of them are written hastily and tested rarely. The lever isn't "handle errors better" — it's
**reduce the number of places an error has to be handled at all.**

Three ways, in order of preference:
1. **Design the error out of the API.** Make the troublesome case not be an error. `delete(x)` on
   something that doesn't exist → a no-op, not an exception. `substring` past the end → clamp to
   the end, don't throw. Look at every error your interface can raise and ask whether the
   *interface* could be defined so it can't arise.
2. **Handle it low and once.** Catch the error at the lowest layer that can actually do something
   about it, in one place, rather than propagating it up through five callers who each have to
   decide what to do.
3. **For the truly unrecoverable, fail fast and loud.** A corrupted invariant, a config that can't
   possibly be valid, an "impossible" branch — crash with a clear message rather than limping on
   and corrupting more state. Liveness theater (swallow, log, continue) is worse than a clean stop.

*Context — this heuristic is itself calibrated:* "just crash" is exactly right for a CLI tool, a
build script, a dev-only utility. It is **negligent** for a high-criticality system — a payments
flow, a governance record store — where you instead need careful, audited error handling, retries
that are idempotent so a retry can't double-charge or double-record, and *no silent data loss
anywhere*. So: simplify error handling down to the level the envelope permits — aggressively at
Tier 0–1, deliberately and not at all "out of existence" for the things that hold money or legal
state. (See `references/envelope-tiers.md`.)

## 8. Comments capture what code can't

Code says *what* it does. Comments exist for what was in the designer's head and *can't* be put in
code: the *why* (the rationale, the rejected alternative, the external constraint), the invariants
("callers must hold the lock"; "this list is always sorted"), the units ("milliseconds"; "bytes,
not chars"), the ownership ("the cache layer owns eviction; don't evict here"), and the
*cross-module contract* (what this module promises, what it requires).

What comments are *not* for: restating the code (`i++  // increment i`), or describing *how* an
interface works internally to its users (that's leakage — they shouldn't need to know). An
**interface comment describes what and why, never how.**

A useful design check: try to write the interface comment *first*, before the implementation. If
you can't write a short, clean one, the interface is probably wrong — too broad, too leaky, doing
too much. The comment is a stress test on the design.

*Context:* the rationale comments (the *why*) earn their keep most on long-lived code, because
their job is to talk to a future maintainer who wasn't in the room. On a throwaway, skip them. The
*invariant* and *units* comments earn their keep almost immediately — a wrong assumption about
units is a same-week bug.

## 9. Design it twice

For any decision that's a one-way door or that you'll live with for a while, **generate at least
two genuinely different options and compare them on concrete criteria** before picking. Not "this,
or a worse version of this" — two real alternatives with different shapes.

Why it works so well for so little effort:
- The first design that comes to mind is rarely the best; it's just the first.
- The act of forcing a second option onto the table routinely surfaces a *third* that beats both.
- It's a built-in anti-over-engineering check: if one of your two options is "the minimal version"
  (and per `SKILL.md`'s decision loop, one of them always should be), then you're forced to
  articulate why the elaborate option is worth its cost — and you'll often find it isn't.

The cost is minutes of thinking; the return is not being locked into a mediocre choice for years.
*Context:* skip it for genuine two-way doors with low stakes — a library pick you can swap in an
afternoon doesn't need a design bake-off. Use it for the one-way doors, every time.

## 10. Names

A good name puts an accurate image in the reader's mind and needs no comment to do it. Names
should be **precise** (name the specific thing, not a vague category — `blockOffset` not `pos`),
**consistent** (the same concept gets the same name everywhere; different concepts get different
names), and **unambiguous** (a reader can't reasonably think it means something else).

If a name is hard to find, that's diagnostic: the thing it names is probably doing too much, or
isn't a coherent thing. Hard-to-name is a design smell, not just a vocabulary problem.

*Context-neutral and cheap:* good naming costs nothing extra and pays at every tier. There's no
envelope where vague names are fine.

## 11. Consistency

Consistency is one of the highest-leverage, lowest-cost complexity reducers there is: when the
same problem is always solved the same way, a reader who's seen it once understands it everywhere,
and an editor can change it in one place. Apply it to names, file and module structure, error
handling, the shape of an API, coding conventions, vocabulary in docs.

Two rules: **(a)** when there's an established way to do something in this codebase, use it — don't
introduce a second way that does the same job. **(b)** if you must change a convention, change it
*everywhere*, or you've made things worse, not better — now there are two conventions and a reader
has to know which era a file is from.

*Context:* matters more the bigger the team and the longer the codebase lives — but it's so cheap
that "just be consistent" is the right default even on small things.

## 12. Make it obvious

Obscurity is half of all complexity (§1). The antidote is *obviousness*: a reader should grok the
code quickly, with little surprise. Obviousness comes from the cheap things stacked together —
good names (§10), consistency (§11), whitespace that visually groups what belongs together, a
sane order, and a comment exactly where the code alone can't carry the intent (§8).

The orienting principle: **write for the reader, not the writer.** Code is read far more often than
written, and the reader is usually you, six months from now, with none of the context you have
today. If something took you a while to get right, it will take the next reader a while to
understand unless you make it obvious — so spend the extra minute.

## 13. Strategic, not tactical

*Tactical programming* is "make it work, ship it, move on" — each move small and locally sensible,
but they compound, and after enough of them you're in a swamp where every change is slow and
risky. *Strategic programming* treats working code as necessary but not sufficient: the goal is a
system that *stays* easy to change, and you spend roughly **10–20% extra effort now** — a cleaner
interface, the right abstraction, the comment, the small refactor you pass through — to keep it
that way. Over a long-lived system that 10–20% is the best-returning investment in the codebase;
the swamp is what you get by skipping it.

**This is the single most context-calibrated heuristic in the file.** The right amount of
strategic investment is roughly *lifespan × change-rate × team-size*:
- A weekend spike you'll delete: ~0%. Being "strategic" here is itself a form of over-engineering.
- An internal tool that runs for years but is edited a few times a year by one person: a little —
  keep it readable, but don't gold-plate.
- A core product a dozen people change every week for a decade: the full 20%, deliberately, every
  day. This is where skimping bankrupts you.

The error to actively avoid: being tactical on something long-lived *because it felt faster
today*. It wasn't faster; the bill just arrives later, with interest, paid by someone else.

And: **design is never done.** Every time you touch existing code you're doing design again — you
can leave it a little better or a little worse. Stay strategic in maintenance; don't just bolt the
new thing on next to the old thing and walk away.
