---
name: goal_planning
description: Plan ANY financial goal — buy a house, retire, fund education, hit a net-worth number — by
  modeling start → target with what-ifs, sequence-of-returns risk, and Monte Carlo, then giving concrete
  levers to actually reach it. Trigger on "can I afford a house by X", "can I retire at Y", "how much to
  save for Z", "am I on track for <goal>", "what if I buy / save more / the market dips". Spending habits
  → spending_insight; current-state risk → cashflow_health.
metadata:
  execution_mode: sandbox
---

# Goal Planning

A goal is just **[start] → accumulate → [target]** (an amount by an age). Retirement adds a second phase:
**spend down** after the target. Buy-a-house = 1 phase; retirement = 2. Same engine.

Two phases of work, and the sandbox is one-way (once inside you can't ask the user). In chat: build a
complete scenario_spec. Then enter the sandbox to download the engine and compute. Multi-round = each
round is one closed round-trip.

## Phase A — in chat: build the spec

### Step 1 — name the goal, then build the story (extract → ask → assume → confirm)
First pin **what goal**: home down payment / retirement / education / FIRE / a net-worth number. That
decides whether there's a `retirement` (spend-down) layer.

Then 30/40/70 — the user gives ~30%, you extend to a coherent ~70% they react to (never a form):
- **Extract** — injected finance profile (age, income, household, goals, risk) + Plaid tools
  (get_net_worth, get_savings_rate) for hard numbers.
- **Ask** — only what you can't infer: the target (amount + by when) and any big plans on their mind.
- **Assume → 70%** — fill the rest from profile (life events, contributions, market assumptions). The
  assumed 40% must be **coherent** (follows from profile) and **visible** (mark "(assumed)" so they can
  correct just that).
- **Confirm → iterate** — narrate the 70% back in one paragraph; OK → assemble spec; not OK → re-ask only that piece.

### Step 2 — assemble the scenario_spec (built here; the sandbox only runs it)
Three blocks (everything you need is below — don't rely on the sandbox files):
- `start`: { age, assets }
- `target`: { amount, by_age, label, min_success (0.9) }            ← the goal
- `contributions`: { annual_savings, income_growth (3%) }
- `assumptions`: { nominal_return (7%), inflation (3%), return_std (13%) }   ← NOMINAL + explicit inflation
- `retirement`: { annual_spend (today's $), plan_to_age (95) }      ← OPTIONAL; only for retire-type goals
- `market_scenario`: { mode: "monte_carlo" | "sequence_risk", runs (5000), seed (42) }
- `life_events`: [ ... ]  ·  `whatifs`: [ { name, overrides:{ annual_savings | by_age | add_events | remove_events } } ]

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

**Defaults for the assumed 40%** (state which you used): nominal return 7% (5/7/9 by risk), inflation 3%,
income growth 3%, daycare 18k. Spec amounts are NOMINAL; retirement spend is today's $ (engine inflates it).

## Phase B — in the sandbox: download the engine, then run it
The authoritative engine is in references/ — **download and run it; never rewrite it.**
1. `curl -fsSL -o /tmp/gp_refs.zip "https://raw.githubusercontent.com/xuchencaocc-cc/goalplanning/main/goal_planning_refs.zip" && unzip -o /tmp/gp_refs.zip -d ./references`
2. Write the spec to ./spec.json
3. `python references/engine.py ./spec.json` → per-scenario hit_target / no_deplete + a **plan** (levers)
4. Plot with references/plots.py → PNGs, upload them.
If download fails or engine.py is missing, say so and STOP — never fabricate an engine or hand-compute.

## Output — give the plan, in two lenses, both labeled
Lead with **whether the goal is on track**, then the **plan to reach it** (the engine's levers) — not just a verdict.
- **Two lenses, never merged**: "hit the goal" (`target_hit_rate`) vs "won't run out in retirement"
  (`success_rate`, retirement only). State which is which.
- **Two money labels, always**: every net-worth figure as nominal AND today's purchasing power
  ("10M at 40 ≈ 6.6M today"). A big nominal number is not wealth.
- **If off-track → levers** (all from the engine's plan): save more → $X/yr · reach/retire later → age Y ·
  trim target → $Z. Present the 2–3 that fit this person, let them pick.
- Numbers come only from the engine. These are measured planning levers (save / date / target / risk),
  not specific product or investment picks.

## Hard rule (Evidence)
Every figure = engine output or an injected-profile fact. You never project/compound/percentage/diff
yourself — the engine does. Always state the assumptions used.

## Boundaries
Read-only, educational, under the system prompt's compliance/disclaimer rules — projections are
illustrative, not guarantees; no specific investment/tax/legal directives. Surface missing inputs plainly.
