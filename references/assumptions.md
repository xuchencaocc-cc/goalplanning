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
