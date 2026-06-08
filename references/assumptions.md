# Default planning assumptions (v1)

All returns are **REAL** (after inflation). Always state which value you used in the answer.

| Assumption | Default | Basis |
|---|---|---|
| Real return | 5% | conservative ~60/40 real; profile risk shifts it (4% conservative / 6% moderate / 7% aggressive) |
| Return volatility (σ) | 12% | Monte Carlo dispersion |
| Inflation | 3% | long-run US CPI ballpark |
| Income growth | 1% real | conservative |
| Monte Carlo runs | 5000 | fixed seed 42 → reproducible |
| Plan-to age | 95 | longevity buffer |
| Daycare annual | $18,000 | editable per user |

**Sequence-of-returns**: with `market_scenario.mode = "sequence_risk"`, a crash of `depth`
(default −35%) is forced in retirement year `crash_year` (default 1).

**Success** = the path is never depleted before `plan_to_age`. Success rate = share of Monte
Carlo runs that succeed.

## Life events — "time-window parameter overrides"
Put events in `life_events[]` (shared by all scenarios) or a what-if's `overrides.add_events[]`.
Each event can inject cashflow, override/delta the year's savings, or override the real return for
a window.

| type | key fields | effect |
|---|---|---|
| `home_purchase` | age, down (or cashflow), annual_payment_delta | −down at age; savings − payment after |
| `home_sale` | age, proceeds (or cashflow), savings_delta | +proceeds at age; savings + after (mortgage gone) |
| `child` | born_age, daycare_yrs, daycare_annual (def 18k), college_at (def 18), college_cost | daycare drain in window; college lump |
| `career_change` | age, savings_delta (or income_delta) | savings ± permanently after age |
| `startup` / `gap_year` / `sabbatical` | start, end (or age), savings_override (def 0), seed/cashflow | savings paused in window; optional one-off seed cost |
| `derisk` | start (or age), real_return | return overridden from age (e.g. 0.03) — explicit, replaces ad-hoc r×0.6 |
| `eldercare` | start, end, annual (or cashflow_annual) | extra drain in window |
| `windfall` | age, amount | +amount at age (RSU vest / inheritance) |

**Defaults for the assumed 40%** (state which you used): daycare $18k/yr; derisk-at-retirement →
real 3%; gap/startup → savings 0 during the window.

## Simplifications (v1, stated for auditability)
- income growth applied as `savings × (1+g)^years`; events override on top
- `home_purchase` models the down payment (+ optional `annual_payment_delta`), not full amortization
- retirement spend is constant real (no go-go / slow-go phases yet)
- returns are real, so inflation is not modeled per line
