"""
engine.py — deterministic, auditable goal/retirement projection.

Input:  scenario_spec (dict; see spec_schema.json)
Output: run(spec) -> results per scenario (+ solve_for if requested)

Auditable by design:
  - fixed RNG seed  -> Monte Carlo is reproducible
  - all assumptions echoed in the output
  - full year-by-year deterministic path dumped
The calling LLM never computes anything; it only reads this engine's output.

Life events are "time-window parameter overrides": an event can inject a one-off/periodic
cashflow, override or delta the year's savings, or override the real return for a window.
See assumptions.md for the supported event types.

Run a quick check:  python3 engine.py            (uses the built-in demo)
                    python3 engine.py spec.json   (reads a spec file)
"""
from __future__ import annotations
import numpy as np

DEFAULTS = {
    "real_return": 0.05,   # annual REAL (after-inflation) return
    "return_std": 0.12,    # volatility for Monte Carlo
    "income_growth": 0.01,
    "mc_runs": 5000,
    "seed": 42,
    "daycare_annual": 18000,
    "plan_to_age": 95,
}


def assumptions(spec):
    a = dict(DEFAULTS)
    a.update(spec.get("assumptions", {}))
    a["seed"] = spec.get("market_scenario", {}).get("seed", a["seed"])
    return a


def apply_events(events, age, base_savings, base_return, a):
    """Resolve one year after life events.

    Returns (extra_cashflow, savings_this_year, real_return_this_year).
    Events may: inject one-off/periodic cashflow, override/delta savings, or override return.
    """
    cf = 0.0
    savings = base_savings
    ret = base_return
    for e in events:
        t = e.get("type")
        if t == "home_purchase":
            if age == e.get("age"):
                cf += e.get("cashflow", -e.get("down", 0))
            if age >= e.get("age", 1e9):
                savings += e.get("savings_delta", -e.get("annual_payment_delta", 0))
        elif t == "home_sale":
            if age == e.get("age"):
                cf += e.get("cashflow", e.get("proceeds", 0))
            if age >= e.get("age", 1e9):
                savings += e.get("savings_delta", 0)        # mortgage gone -> savings up
        elif t == "child":
            b = e["born_age"]
            if b <= age < b + e.get("daycare_yrs", 0):
                cf -= e.get("daycare_annual", a["daycare_annual"])
            if age == b + e.get("college_at", 18):
                cf -= e.get("college_cost", 0)
        elif t == "career_change":
            if age >= e.get("age", 1e9):
                savings += e.get("savings_delta", e.get("income_delta", 0))
        elif t in ("startup", "gap_year", "sabbatical"):
            s = e.get("start", e.get("age"))
            en = e.get("end", e.get("age"))
            if s is not None and s <= age <= en:
                savings = e.get("savings_override", 0.0)    # income paused -> savings stop
            if age == s and ("cashflow" in e or "seed" in e):
                cf += e.get("cashflow", -e.get("seed", 0))  # one-off seed cost
        elif t == "derisk":
            s = e.get("start", e.get("age"))
            if s is not None and age >= s:
                ret = e.get("real_return", ret)             # explicit post-event return
        elif t == "eldercare":
            s, en = e.get("start"), e.get("end")
            if s is not None and en is not None and s <= age <= en:
                cf += e.get("cashflow_annual", -e.get("annual", 0))
        elif t == "windfall":
            if age == e.get("age"):
                cf += e.get("amount", e.get("cashflow", 0))
    return cf, savings, ret


def project(spec, scenario, returns=None):
    """One path. returns=None -> deterministic at real_return; else a per-year array."""
    a = assumptions(spec)
    cur, goal = spec["current"], spec["goal"]
    start = cur["age"]
    end = scenario.get("plan_to_age", goal.get("plan_to_age", a["plan_to_age"]))
    retire = scenario.get("retire_age", goal["retire_age"])
    savings0 = scenario.get("annual_savings", cur["annual_savings"])
    spend = scenario.get("annual_spend_retire", goal["annual_spend_retire"])
    ig = a["income_growth"]
    # events shared across scenarios + any added by this what-if
    events = list(spec.get("life_events", [])) + list(scenario.get("add_events", []))
    nw = float(cur["investable"])
    path, shortfall = [], None
    for i, age in enumerate(range(start, end + 1)):
        r_base = a["real_return"] if returns is None else float(returns[i])
        base_savings_y = savings0 * ((1 + ig) ** (age - start))   # natural income growth
        cf, savings_y, r = apply_events(events, age, base_savings_y, r_base, a)
        if age < retire:
            nw = nw * (1 + r) + savings_y + cf
        else:
            nw = nw * (1 + r) - spend + cf
        if nw < 0:
            if shortfall is None:
                shortfall = age
            nw = 0.0   # depleted: floors at 0, never negative
        path.append((age, round(nw, 2)))
    return path, shortfall


def monte_carlo(spec, scenario):
    a = assumptions(spec)
    rng = np.random.default_rng(a["seed"])
    start = spec["current"]["age"]
    end = scenario.get("plan_to_age", spec["goal"].get("plan_to_age", a["plan_to_age"]))
    years = end - start + 1
    mc = spec.get("market_scenario", {})
    runs = int(mc.get("runs", a["mc_runs"]))
    retire = scenario.get("retire_age", spec["goal"]["retire_age"])
    grid = np.zeros((runs, years))
    successes = 0
    for k in range(runs):
        rets = rng.normal(a["real_return"], a["return_std"], years)
        if mc.get("mode") == "sequence_risk":
            cy = (retire - start) + (int(mc.get("crash_year", 1)) - 1)  # crash in early retirement
            if 0 <= cy < years:
                rets[cy] = mc.get("depth", -0.35)
        path, sf = project(spec, scenario, returns=rets)
        grid[k] = [v for _, v in path]
        if sf is None:
            successes += 1
    pct = {p: np.round(np.percentile(grid, p, axis=0), 2).tolist() for p in (10, 25, 50, 75, 90)}
    return successes / runs, pct


def _success(spec, scenario):
    return monte_carlo(spec, scenario)[0]


def solve_for(spec):
    """Binary/linear search a single target to meet a success constraint."""
    sf = spec["solve_for"]
    target = sf.get("target", "annual_savings")
    need = sf.get("min_success", 0.9)
    fixed = dict(sf.get("fixed", {}))
    if target == "annual_savings":
        lo, hi = 0.0, 500000.0
        for _ in range(40):
            mid = (lo + hi) / 2
            if _success(spec, {**fixed, "annual_savings": mid}) >= need:
                hi = mid
            else:
                lo = mid
        return {"target": "annual_savings", "annual": round(hi, 2),
                "monthly": round(hi / 12, 2), "constraint": f"success>={need} with {fixed}"}
    if target == "retire_age":
        for age in range(spec["goal"]["retire_age"], 76):
            if _success(spec, {**fixed, "retire_age": age}) >= need:
                return {"target": "retire_age", "earliest_age": age, "constraint": f"success>={need}"}
        return {"target": "retire_age", "earliest_age": None, "constraint": f"success>={need}"}
    return {"error": f"unsupported solve target: {target}"}


def run(spec):
    a = assumptions(spec)
    scenarios = {"baseline": {}}
    for w in spec.get("whatifs", []):
        scenarios[w["name"]] = dict(w.get("overrides", {}))
    results = {}
    for name, sc in scenarios.items():
        det, sf = project(spec, sc)
        succ, pct = monte_carlo(spec, sc)
        results[name] = {
            "ending_net_worth": det[-1][1],
            "success_rate": round(succ, 3),
            "shortfall_age": sf,
            "percentiles_by_year": pct,
            "deterministic_path": det,
        }
    out = {"assumptions": a, "start_age": spec["current"]["age"], "scenarios": results}
    if "solve_for" in spec:
        out["solve_for"] = solve_for(spec)
    return out


_DEMO = {
    "current": {"age": 38, "investable": 250000, "annual_savings": 18000},
    "goal": {"retire_age": 60, "annual_spend_retire": 70000, "plan_to_age": 95},
    "assumptions": {"real_return": 0.05},
    "market_scenario": {"mode": "monte_carlo", "runs": 3000, "seed": 42},
    "life_events": [
        {"type": "child", "born_age": 35, "daycare_yrs": 5, "college_at": 18, "college_cost": 100000},
        {"type": "derisk", "start": 60, "real_return": 0.03},          # retire -> conservative (explicit)
    ],
    "whatifs": [
        {"name": "retire@55", "overrides": {"retire_age": 55}},
        {"name": "save_30k", "overrides": {"annual_savings": 30000}},
        {"name": "startup@45", "overrides": {"add_events": [
            {"type": "startup", "start": 45, "end": 47, "seed": 50000}]}},   # 3yr no-income + $50k seed
    ],
    "solve_for": {"target": "annual_savings", "min_success": 0.9, "fixed": {"retire_age": 60}},
}


if __name__ == "__main__":
    import json, sys
    spec = json.load(open(sys.argv[1])) if len(sys.argv) > 1 else _DEMO
    res = run(spec)
    print(f"assumptions: real_return={res['assumptions']['real_return']:.0%} "
          f"runs={spec.get('market_scenario', {}).get('runs', res['assumptions']['mc_runs'])} "
          f"seed={res['assumptions']['seed']}")
    for name, r in res["scenarios"].items():
        print(f"  {name:12s} success={r['success_rate']:6.1%}  "
              f"end=${r['ending_net_worth']:>12,.0f}  shortfall={r['shortfall_age']}")
    if "solve_for" in res:
        s = res["solve_for"]
        if s.get("target") == "annual_savings":
            print(f"  solve annual_savings -> ${s['annual']:,.0f}/yr (${s['monthly']:,.0f}/mo) "
                  f"to hit {s['constraint']}")
        else:
            print("  solve:", s)
