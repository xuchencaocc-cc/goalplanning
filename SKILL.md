---
name: goal_planning
description: >-
  Plan ANY financial goal — buy a house, retire, fund education, hit a net-worth number — modeling
  start → target with what-ifs, sequence risk, and Monte Carlo, then concrete levers to reach it.
  Trigger on "can I afford a house by X", "can I retire at Y", "how much to save for Z", "am I on
  track for <goal>", "what if I buy / save more / the market dips". Gathers the inputs in chat, then
  runs a deterministic sandbox engine. Spending habits → spending_insight; current-state risk → cashflow_health.
metadata:
  visible_to_agents:
    - user_agent_official
---

# Goal Planning

A goal is **[start] → accumulate → [target]** (an amount by an age). Retirement adds a second phase —
**spend down** after the target. Buy-a-house = 1 phase; retirement = 2. Same engine.

**Two phases, and the order is load-bearing.** This skill is shown to you INLINE — you read Phase A here
and run it **in chat first** (gather + recap + confirm). The engine runs in a **sandbox** you enter by
calling `transfer_to_agent("sandbox_runner")`, and that sandbox is one-way: it can't see the profile/tools
or come back to ask. So finish Phase A and get the recap confirmed BEFORE you transfer — the confirmed
recap is the ONLY thing that crosses into the sandbox.

---

## Phase A — IN CHAT (you are the main agent; do this before transferring)

### Step 1 — name the goal, then build the story (extract → ask → assume → confirm)
First pin **what goal**: home down payment / retirement / education / FIRE / a net-worth number. That
decides whether there's a `retirement` (spend-down) layer.

Then 30/40/70 — the user gives ~30%, you extend to a coherent ~70% they react to (never a form):
- **Extract** — injected finance profile (age, income, household, goals, risk) + `query_personal_database`
  ("my net worth", "my savings rate over the last 3 months") for hard numbers. `query_personal_database`
  is US-Plaid only; if it returns nothing (non-US / unconnected), take the numbers from profile/memory
  or **ask the user** and mark them "(as you told me)".
- **Ask** — only what you can't infer: the target (amount + by when) and any big plans on their mind.
- **Assume → 70%** — fill the rest from profile (life events, contributions, market assumptions). The
  assumed 40% must be **coherent** (follows from profile) and **visible** (mark "(assumed)" so they can
  correct just that).
- **Confirm → iterate** — narrate the 70% back in one paragraph; OK → assemble spec; not OK → re-ask only that piece.

### Step 2 — assemble the scenario_spec (built here; the sandbox only runs it)
Three blocks (everything the engine needs):
- `start`: { age, assets }
- `target`: { amount, by_age, label, min_success (0.9) }            ← the goal
- `contributions`: { annual_savings, income_growth (3%) }
- `assumptions`: { nominal_return, inflation, return_std }   ← NOMINAL + explicit inflation; **defaults below are US — adjust to the user's market**
- `retirement`: { annual_spend (today's $), plan_to_age (95) }      ← OPTIONAL; only for retire-type goals
- `market_scenario`: { mode: "monte_carlo" | "sequence_risk", runs (5000), seed (42) }
- `life_events`: [ ... ]  ·  `whatifs`: [ { name, overrides:{ annual_savings | by_age | add_events | remove_events } } ]

Ages (`start.age`, `target.by_age`, `retirement.plan_to_age`, any `by_age` override) must be **whole
integers**. Every what-if `name` must be a short **ASCII/Latin slug** (e.g. `no_house`, `retire_45`) — it
becomes a chart legend label and non-ASCII renders as blank boxes.

**Life-event vocabulary** (pick types, fill NOMINAL params):

| type | fields | effect |
|---|---|---|
| home_purchase / home_sale | age, down/proceeds, annual_payment_delta | one-off ± and a savings shift after |
| child | born_age, daycare_yrs, daycare_annual (18k), college_at (18), college_cost | daycare drain + college lump |
| career_change | age, savings_delta | savings ± permanently after age |
| startup / gap_year / sabbatical | start, end, savings_override (0), seed | savings paused in window + seed cost |
| derisk | start, nominal_return | return overridden from age (e.g. 0.05) |
| eldercare | start, end, annual | drain during window |
| windfall | age, amount | one-off ± (RSU / inheritance / wedding) |
| recurring_cashflow | start, end, annual, growth | a recurring ± stream (rental income, side gig, alimony) |

For window events (startup / gap_year / sabbatical / eldercare / recurring_cashflow) always give **both** `start` and `end`.

**What-ifs — use the scenario library.** A what-if can name a pre-built scenario by `template` instead of
hand-encoding overrides (they resolve against the user's own baseline, so they work in any market):
`whatifs: [ { "name": "upside", "template": "bull_run" }, { "template": "crash_at_goal" } ]`. **Default
panel** (keep it balanced — a range, not a wall of crashes): baseline always runs; add `bull_run` +
`crash_at_goal` (retirement: also `longevity_100`). For choosing scenarios, richer situations (a
windfall, rental income, a specific worry), and the full template list, **load `references/scenarios.md`**.
A healthy plan → lead with that + the upside; don't manufacture alarm.

**Defaults for the assumed 40%** (state which you used, and which market they're for): **US baseline** =
nominal return 7% (5/7/9 by risk), inflation 3%, income growth 3%, daycare 18k. **Adjust to the user's
market** — high-inflation markets (e.g. BR ~4–5% inflation, higher nominal & rates) and near-zero
markets (e.g. JP) need different return/inflation; if you don't have a local figure, ask or use a
sensible local default and mark it "(assumed, <market>)". Retirement accounts likewise: US 401k/IRA/Roth,
JP NISA/iDeCo, SG CPF/SRS, BR PGBL/VGBL, MY EPF, MX Afore — use the local one. Spec amounts are NOMINAL;
retirement spend is today's money (engine inflates it). Currency is the user's, not necessarily USD.

### Step 3 — restate EVERYTHING as a recap, get confirmation, THEN transfer
The sandbox inherits ONLY the conversation Q&A — **NOT** your injected profile, **NOT** function-call /
tool results. So recap, in **plain user-friendly prose** (a short readable summary, NOT a JSON dump), for
the user to confirm. This recap is the ONLY channel the numbers cross into the sandbox on:
- **every input + where it came from** — start age & assets, target, contributions, income, life events
  (note which came from profile / tools / the user / assumed);
- **every assumption** (returns, inflation, the assumed-40%, the market), flagged as assumptions;
- **which scenarios** will run — baseline + each what-if, one line each.
Build the scenario_spec JSON internally, but show the USER readable prose, never raw JSON.

---

## R. Hand-off contract — Phase A → sandbox

**Gate — ALL must be true before you `transfer_to_agent("sandbox_runner")`:**
- [ ] the user explicitly confirmed the recap
- [ ] the full recap (every input + assumption + scenario) is present as plain text in the conversation
- [ ] market / currency / mode (`monte_carlo` | `sequence_risk`) are decided and in the recap
- [ ] ages are whole integers and what-if names are ASCII slugs
- [ ] the confirm turn was text-only; transfer on the NEXT turn

When the gate passes, call `transfer_to_agent("sandbox_runner")`. (If the sandbox is unavailable for this
user, say so plainly and stop — do NOT hand-compute the plan in chat.)

**Sandbox task (you are now `sandbox_runner`) — do EXACTLY this and nothing else:**
> The confirmed recap above is your ONLY source — you cannot see the injected profile or tool results here.
> The engine is authoritative and lives in a pinned public bundle; download and run it, never rewrite or
> hand-compute it.
> 1. `curl -fsSL -o ./skill.zip "https://raw.githubusercontent.com/xuchencaocc-cc/goalplanning/main/goal_planning_v1_1.zip"`
> 2. `rm -rf ./skill && mkdir ./skill && unzip -o ./skill.zip -d ./skill`
> 3. Read `./skill/references/spec_schema.json` (worked example + notes) and `./skill/references/assumptions.md`
>    (money model + defaults). Assemble the confirmed recap above into `./spec.json` — copy every number
>    VERBATIM from the recap; invent nothing, change nothing. If the recap is missing or incomplete, STOP
>    and say intake (Phase A) must run first — do not fabricate numbers.
> 4. `python3 ./skill/scripts/lint_spec.py ./spec.json` — must exit 0. On any `ERROR`, fix the spec so it
>    matches the confirmed recap (if a *number* would have to change, STOP and re-confirm with the user).
> 5. `python3 ./skill/scripts/run_plan.py ./spec.json --outdir .` → writes `result.json`,
>    `fan_baseline.png`, `compare.png`.
> 6. `upload_file` the two PNGs; write the reply from `result.json` (two lenses, two money labels — see Output).
>
> **FORBIDDEN:** writing your own engine / projection / Monte-Carlo, hand-computing any figure, editing
> `engine.py` or `plots.py`, swapping in a different lib for the compute path, or skipping `lint_spec.py` /
> `run_plan.py`. A wrong-method number is worse than an honest error. (Installing the engine's OWN deps —
> `numpy`, `matplotlib` — if they are genuinely missing is fine; substituting them is not.)
>
> **Fail loud:** if the `curl` fails (non-200), `run_plan.py` is missing, or the engine errors → STOP and
> report the error verbatim. Never fabricate an engine, hand-compute, or invent numbers.

---

## Output — give the plan, in two lenses, both labeled
Lead with **whether the goal is on track**, then the **plan to reach it** (the engine's levers) — not just a verdict.
- **Two lenses, never merged**: "hit the goal" (`target_hit_rate`) vs "won't run out in retirement"
  (`success_rate`, retirement only). State which is which.
- **Two money labels, always**: every net-worth figure as nominal AND today's purchasing power
  ("10M at 40 ≈ 6.6M today"). A big nominal number is not wealth.
- **If off-track → levers** (all from the engine's `plan`): save more → $X/yr · reach/retire later → age Y ·
  trim target → $Z. Present the 2–3 that fit this person, let them pick.
- Numbers come only from the engine. These are measured planning levers (save / date / target / risk),
  not specific product or investment picks. Currency is the user's, as set in the recap.

## Hard rule (Evidence)
Every figure = engine output (`result.json`) or an injected-profile fact stated in the recap. You never
project/compound/percentage/diff yourself — the engine does. Always state the assumptions used.

## Boundaries
Read-only, educational, under the system prompt's compliance/disclaimer rules — projections are
illustrative, not guarantees; no specific investment/tax/legal directives. Surface missing inputs plainly.
