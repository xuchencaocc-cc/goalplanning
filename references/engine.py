"""
engine.py — deterministic, auditable GOAL projection (not just retirement).

A goal is just: [start] --accumulate--> [target] (amount by an age).
  - start:      { age, assets }
  - target:     { amount, by_age, label }      e.g. home down payment / nest egg / tuition
  - retirement: { annual_spend, plan_to_age }  OPTIONAL — a spend-down phase AFTER the target
Buy-a-house = 1 phase (accumulate). Retirement = 2 phases (accumulate, then spend). Same engine.

Money model: NOMINAL with explicit inflation. Every net-worth figure is reported twice —
nominal AND deflated to today's purchasing power — so a big nominal number never fakes wealth.

Two lenses, never conflated:
  - target_hit_rate = P(nominal net worth at by_age >= target.amount)   "can I hit the goal?"
  - success_rate    = P(never depleted before plan_to_age)              "won't I run out?" (retirement only)

Auditable: fixed seed, assumptions echoed, year-by-year path dumped. The LLM never computes.
Run:  python3 engine.py    |    python3 engine.py spec.json
"""
from __future__ import annotations
import numpy as np

DEFAULTS = {
    "nominal_return": 0.07, "return_std": 0.13, "inflation": 0.03, "income_growth": 0.03,
    "mc_runs": 5000, "seed": 42, "daycare_annual": 18000, "plan_to_age": 95,
}


def assumptions(spec):
    a = dict(DEFAULTS)
    a.update(spec.get("assumptions", {}))
    a["seed"] = spec.get("market_scenario", {}).get("seed", a["seed"])
    return a


def real(nominal, years, infl):
    """Deflate a future nominal amount to today's purchasing power."""
    return nominal / ((1 + infl) ** years)


def apply_events(events, age, base_savings, base_return, a):
    """One year after life events -> (extra_cashflow, savings, nominal_return). Amounts nominal."""
    cf, savings, ret = 0.0, base_savings, base_return
    for e in events:
        t = e.get("type")
        if t == "home_purchase":
            if age == e.get("age"): cf += e.get("cashflow", -e.get("down", 0))
            if age >= e.get("age", 1e9): savings += e.get("savings_delta", -e.get("annual_payment_delta", 0))
        elif t == "home_sale":
            if age == e.get("age"): cf += e.get("cashflow", e.get("proceeds", 0))
            if age >= e.get("age", 1e9): savings += e.get("savings_delta", 0)
        elif t == "child":
            b = e["born_age"]
            if b <= age < b + e.get("daycare_yrs", 0): cf -= e.get("daycare_annual", a["daycare_annual"])
            if age == b + e.get("college_at", 18): cf -= e.get("college_cost", 0)
        elif t == "career_change":
            if age >= e.get("age", 1e9): savings += e.get("savings_delta", e.get("income_delta", 0))
        elif t in ("startup", "gap_year", "sabbatical"):
            s, en = e.get("start", e.get("age")), e.get("end", e.get("age"))
            if s is not None and s <= age <= en: savings = e.get("savings_override", 0.0)
            if age == s and ("cashflow" in e or "seed" in e): cf += e.get("cashflow", -e.get("seed", 0))
        elif t == "derisk":
            s = e.get("start", e.get("age"))
            if s is not None and age >= s: ret = e.get("nominal_return", ret)
        elif t == "eldercare":
            s, en = e.get("start"), e.get("end")
            if s is not None and en is not None and s <= age <= en: cf += e.get("cashflow_annual", -e.get("annual", 0))
        elif t == "windfall":
            if age == e.get("age"): cf += e.get("amount", e.get("cashflow", 0))
    return cf, savings, ret


def _events_for(spec, scenario):
    evs = list(spec.get("life_events", [])) + list(scenario.get("add_events", []))
    drop = set(scenario.get("remove_events", []))
    return [e for e in evs if e.get("type") not in drop]


def project(spec, scenario, returns=None):
    """One path: accumulate to target.by_age, then (if retirement) spend to plan_to_age."""
    a = assumptions(spec)
    start, target = spec["start"], spec["target"]
    contrib = spec.get("contributions", {})
    ret_layer = scenario.get("retirement", spec.get("retirement"))
    start_age = start["age"]
    by_age = scenario.get("by_age", target["by_age"])
    savings0 = scenario.get("annual_savings", contrib.get("annual_savings", 0))
    ig = scenario.get("income_growth", contrib.get("income_growth", a["income_growth"]))
    infl = a["inflation"]
    if ret_layer:
        end = scenario.get("plan_to_age", ret_layer.get("plan_to_age", a["plan_to_age"]))
        spend0 = scenario.get("annual_spend", ret_layer.get("annual_spend", 0))
    else:
        end = by_age           # pure accumulation goal: stop at the target year
        spend0 = 0
    nw = float(start["assets"])
    events = _events_for(spec, scenario)
    path, shortfall = [], None
    for i, age in enumerate(range(start_age, end + 1)):
        r = a["nominal_return"] if returns is None else float(returns[i])
        yrs = age - start_age
        base_sav = savings0 * ((1 + ig) ** yrs)
        spend_y = spend0 * ((1 + infl) ** yrs) if ret_layer else 0.0
        cf, sav_y, r = apply_events(events, age, base_sav, r, a)
        nw = nw * (1 + r) + (sav_y if age < by_age else -spend_y) + cf
        if nw < 0:
            if shortfall is None: shortfall = age
            nw = 0.0
        path.append((age, round(nw, 2)))
    return path, shortfall


def monte_carlo(spec, scenario):
    a = assumptions(spec)
    rng = np.random.default_rng(a["seed"])
    start_age = spec["start"]["age"]; target = spec["target"]
    ret_layer = scenario.get("retirement", spec.get("retirement"))
    by_age = scenario.get("by_age", target["by_age"])
    end = (scenario.get("plan_to_age", (ret_layer or {}).get("plan_to_age", a["plan_to_age"]))
           if ret_layer else by_age)
    years = end - start_age + 1
    mc = spec.get("market_scenario", {})
    runs = int(scenario.get("runs", mc.get("runs", a["mc_runs"])))
    grid = np.zeros((runs, years)); successes = 0
    for k in range(runs):
        rets = rng.normal(a["nominal_return"], a["return_std"], years)
        if mc.get("mode") == "sequence_risk":
            cy = (by_age - start_age) + (int(mc.get("crash_year", 1)) - 1)
            if 0 <= cy < years: rets[cy] = mc.get("depth", -0.30)
        path, sf = project(spec, scenario, returns=rets)
        grid[k] = [v for _, v in path]
        if sf is None: successes += 1
    pct = {p: np.round(np.percentile(grid, p, axis=0), 2).tolist() for p in (10, 25, 50, 75, 90)}
    ti = by_age - start_age
    col = grid[:, ti]
    res = {"target_hit_rate": float(np.mean(col >= target["amount"])),
           "target_age_nw": {p: float(np.percentile(col, p)) for p in (10, 25, 50, 75, 90)},
           "percentiles_by_year": pct,
           "success_rate": (successes / runs) if ret_layer else None}
    return res


def plan_to_goal(spec):
    """Levers to HIT target.amount by target.by_age. Numbers shown nominal + today's $."""
    a = assumptions(spec)
    start, target = spec["start"], spec["target"]
    contrib = spec.get("contributions", {})
    amount = target["amount"]; by_age = target["by_age"]
    need = target.get("min_success", spec.get("min_success", 0.9))
    infl = a["inflation"]; yrs = by_age - start["age"]
    has_ret = bool(spec.get("retirement"))

    def hit(scenario, runs=700):
        return monte_carlo(spec, {**scenario, "runs": runs})["target_hit_rate"]

    base = monte_carlo(spec, {})
    out = {"label": target.get("label", "goal"), "amount": amount,
           "amount_today": round(real(amount, yrs, infl)), "by_age": by_age,
           "min_success": need, "current_hit_rate": round(base["target_hit_rate"], 3)}
    # lever 1 — save more
    lo, hi = 0.0, 5_000_000.0
    for _ in range(22):
        mid = (lo + hi) / 2
        if hit({"annual_savings": mid}) >= need: hi = mid
        else: lo = mid
    cur_sav = contrib.get("annual_savings", 0)
    out["save_more"] = {"annual": round(hi), "monthly": round(hi / 12),
                        "vs_current": cur_sav, "feasible": hit({"annual_savings": hi}) >= need}
    # lever 2 — reach later (push by_age; if retirement, that also pushes the retire date)
    out["reach_later"] = {"earliest_by_age": None}
    for age in range(by_age, by_age + 31):
        if hit({"by_age": age}) >= need:
            out["reach_later"] = {"earliest_by_age": age, "years_later": age - by_age,
                                  "is_retirement": has_ret}; break
    # lever 3 — trim the target
    key = min(base["target_age_nw"], key=lambda p: abs(p - int(round((1 - need) * 100))))
    ach = base["target_age_nw"][key]
    out["trim_target"] = {"achievable": round(ach), "achievable_today": round(real(ach, yrs, infl)),
                          "by_age": by_age, "with_prob": need}
    return out


def run(spec):
    a = assumptions(spec); start_age = spec["start"]["age"]
    has_ret = bool(spec.get("retirement"))
    end = (spec["retirement"].get("plan_to_age", a["plan_to_age"]) if has_ret else spec["target"]["by_age"])
    scenarios = {"baseline": {}}
    for w in spec.get("whatifs", []):
        scenarios[w["name"]] = dict(w.get("overrides", {}))
    results = {}
    for name, sc in scenarios.items():
        det, sf = project(spec, sc)
        mc = monte_carlo(spec, sc)
        end_nom = det[-1][1]
        results[name] = {
            "ending_net_worth": end_nom,
            "ending_net_worth_today": round(real(end_nom, end - start_age, a["inflation"])),
            "target_hit_rate": round(mc["target_hit_rate"], 3),
            "success_rate": round(mc["success_rate"], 3) if mc["success_rate"] is not None else None,
            "shortfall_age": sf,
            "percentiles_by_year": mc["percentiles_by_year"],
            "deterministic_path": det,
        }
    return {"assumptions": a, "start_age": start_age, "scenarios": results, "plan": plan_to_goal(spec)}


_DEMO_RETIRE = {
    "start": {"age": 26, "assets": 400000},
    "target": {"amount": 10000000, "by_age": 40, "label": "retire at 40", "min_success": 0.9},
    "contributions": {"annual_savings": 126000, "income_growth": 0.03},
    "assumptions": {"nominal_return": 0.07, "inflation": 0.03},
    "market_scenario": {"runs": 3000, "seed": 42},
    "retirement": {"annual_spend": 100000, "plan_to_age": 85},
    "life_events": [
        {"type": "windfall", "age": 30, "amount": -200000},
        {"type": "child", "born_age": 32, "daycare_yrs": 6, "daycare_annual": 50000},
        {"type": "home_purchase", "age": 35, "down": 1000000},
    ],
    "whatifs": [{"name": "no_house", "overrides": {"remove_events": ["home_purchase"]}}],
}

_DEMO_HOUSE = {
    "start": {"age": 28, "assets": 150000},
    "target": {"amount": 800000, "by_age": 33, "label": "home down payment", "min_success": 0.9},
    "contributions": {"annual_savings": 120000, "income_growth": 0.03},
    "assumptions": {"nominal_return": 0.05, "inflation": 0.03},      # shorter horizon -> conservative
    "market_scenario": {"runs": 3000, "seed": 42},
    # no retirement layer -> pure accumulation
}


if __name__ == "__main__":
    import json, sys
    spec = json.load(open(sys.argv[1])) if len(sys.argv) > 1 else _DEMO_RETIRE
    res = run(spec); a = res["assumptions"]
    print(f"assumptions: nominal={a['nominal_return']:.0%} inflation={a['inflation']:.0%} seed={a['seed']}")
    for name, r in res["scenarios"].items():
        sr = f"{r['success_rate']:.1%}" if r["success_rate"] is not None else "n/a"
        print(f"  {name:11s} hit={r['target_hit_rate']:5.1%}  no_deplete={sr:>5}  "
              f"end=${r['ending_net_worth']:>11,.0f} (today ${r['ending_net_worth_today']:>10,.0f})")
    p = res["plan"]
    print(f"\nPLAN '{p['label']}': hit {p['amount']:,.0f} by age {p['by_age']} "
          f"(= today ${p['amount_today']:,.0f}); need {p['min_success']:.0%}; current {p['current_hit_rate']:.1%}")
    sm = p["save_more"]
    print(f"  · save more  → ${sm['annual']:,.0f}/yr (${sm['monthly']:,.0f}/mo) vs now ${sm['vs_current']:,.0f}"
          + ("" if sm["feasible"] else "  [short even maxed]"))
    rl = p["reach_later"]
    lbl = "retire" if rl.get("is_retirement") else "reach it"
    print(f"  · {lbl} later → earliest age {rl['earliest_by_age']}"
          + (f" (+{rl['years_later']}y)" if rl["earliest_by_age"] else " (not in range)"))
    tt = p["trim_target"]
    print(f"  · trim target→ ${tt['achievable']:,.0f} (today ${tt['achievable_today']:,.0f}) {tt['with_prob']:.0%}-reachable by {tt['by_age']}")
