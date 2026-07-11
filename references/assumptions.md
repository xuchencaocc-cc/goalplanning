# Planning model & default assumptions (v1)

## Money model — NOMINAL + explicit inflation
Assets grow at `nominal_return`; savings grow nominally; **retirement spend is given in today's
purchasing power and inflated each year** (keeps standard of living). Spec amounts are NOMINAL — the
figure the user pictures. **Every net-worth output is shown twice: nominal AND deflated to today's $**,
so a big nominal number never masquerades as wealth.

| Assumption | Default | Basis |
|---|---|---|
| nominal_return | 7% | ≈5% real + ~2–3% inflation; by risk tier 5 / 7 / 9 |
| inflation | 3% | long-run US CPI ballpark |
| income_growth | 3% nominal | conservative |
| return_std | 13% | Monte Carlo dispersion |
| mc_runs / seed | 5000 / 42 | reproducible |
| plan_to_age | 95 | longevity buffer (retirement only) |
| daycare_annual | $18,000 | editable per user |

## Two lenses (never merge them)
- `target_hit_rate` = P( net worth at `by_age` ≥ `target.amount` ) — **"can I hit the goal?"**
- `success_rate` = P( never depleted before `plan_to_age` ) — **"won't I run out?"** — only when a `retirement` layer exists

## A goal = phases
- **1 phase** (e.g. home down payment, tuition): `start` + `target`, **no** `retirement` → only `target_hit_rate`.
- **2 phases** (retirement): add `retirement { annual_spend, plan_to_age }` → also `success_rate`.

## Sequence-of-returns
`market_scenario.mode = "sequence_risk"` forces a `depth` (default −30%) crash in the first year past `by_age`.

## Life events — time-window parameter overrides
| type | key fields | effect |
|---|---|---|
| home_purchase / home_sale | age, down/proceeds, annual_payment_delta | one-off ± at age, savings shift after |
| child | born_age, daycare_yrs, daycare_annual (18k), college_at (18), college_cost | daycare drain + college lump |
| career_change | age, savings_delta | savings ± permanently after age |
| startup / gap_year / sabbatical | start, end, savings_override (0), seed | savings paused in window + one-off seed |
| derisk | start, nominal_return | return overridden from age (e.g. 0.05) |
| eldercare | start, end, annual | drain during window |
| windfall | age, amount | one-off ± (RSU / inheritance / wedding) |

What-ifs can `add_events` or `remove_events: ["home_purchase"]`.

## plan_to_goal — the levers to actually reach the target
- **save_more** — annual savings needed to hit `min_success`
- **reach_later / retire_later** — earliest `by_age` that works (pushes the retire date too, if there's a retirement layer)
- **trim_target** — net worth `min_success`-reachable by `by_age` (shown nominal + today's $)

## Simplifications (v1, stated for auditability)
- savings = base × (1 + income_growth)^years; events override on top
- home_purchase = down payment (+ optional payment delta), not full amortization
- retirement spend constant-real (inflated yearly, no go-go / slow-go phases)

## v1.1 additions (scenarios)
- **`recurring_cashflow` event** `{ start, end, annual, growth }` — a recurring ± stream inside a window
  (rental income, side gig, alimony). `cf += annual × (1+growth)^(age−start)`. NOMINAL; negative = a drain.
- **Scenario-level overrides** — a what-if / template may patch `assumptions` (nominal_return, inflation,
  return_std) and `market_scenario` (mode, crash_year, depth) for that scenario only; the baseline is
  untouched. This is what makes `bull_run` / `high_inflation` / `crash_at_goal` possible as what-ifs.
- **Scenario library** (`scenario_library.json`) — named templates a what-if references by `template`.
  Relative values (`"+0.025"`, `"*0.8"`, `"-5"`) resolve against the user's OWN baseline field, so a
  template is market-agnostic; `@start_age` / `@by_age` / `@plan_to_age` (±N) resolve event ages.
  Resolution happens in `run_plan.py` — the engine only ever sees absolute overrides.
- Simplification: a scenario's crash (`market_scenario`) shows up in the Monte-Carlo lens
  (`target_hit_rate`, percentile paths, charts), not in the single deterministic mean-return path — so a
  stress scenario's `ending_net_worth` echoes the baseline while its hit-rate and chart carry the shock.
