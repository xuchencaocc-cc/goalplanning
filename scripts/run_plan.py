#!/usr/bin/env python3
"""
run_plan.py — the ONE deterministic entry for goal_planning in the sandbox.

Reads a scenario_spec (the confirmed recap, assembled to JSON), runs the
authoritative engine, and writes everything a reply needs:
  - prints a human-readable summary (numbers the reply quotes)
  - writes result.json          (full engine output, machine-readable)
  - writes fan_baseline.png      (Monte-Carlo fan for the baseline scenario)
  - writes compare.png           (baseline vs each what-if, median paths)

It only orchestrates engine.py + plots.py — it never computes a figure itself.
Determinism comes from the engine's fixed seed; same spec -> same output.

Usage:
  python3 run_plan.py <spec.json> [--outdir DIR]

Input schema: see ../references/spec_schema.json (a worked example with notes)
and ../references/assumptions.md (the money model + defaults). Validate the spec
with lint_spec.py BEFORE running this.
"""
from __future__ import annotations

import argparse
import json
import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)  # so `import engine` / `import plots` resolve in-bundle

import engine  # noqa: E402  (authoritative core — never reimplemented here)


def _load_spec(path: str) -> dict:
    if not os.path.exists(path):
        sys.exit(f"ERROR: spec file not found: {path} — assemble the confirmed recap into JSON first.")
    with open(path, encoding="utf-8") as f:
        return json.load(f)


# --- scenario-library template expansion (resolved here so the engine only ever sees absolute overrides) ---

def _library_path() -> str:
    return os.path.join(_HERE, "..", "references", "scenario_library.json")


def _load_library() -> dict:
    p = _library_path()
    if not os.path.exists(p):
        sys.exit(f"ERROR: scenario library not found: {p} — a what-if uses `template` but the bundle is missing scenario_library.json.")
    with open(p, encoding="utf-8") as f:
        return json.load(f)


def _rel(val, base):
    """A NUMBER is absolute; a '+x' / '-x' / '*x' STRING is a delta from the baseline value `base`."""
    if isinstance(val, bool):
        raise ValueError(f"unexpected boolean override value {val!r}")
    if isinstance(val, (int, float)):
        return val
    if isinstance(val, str) and val[:1] in ("+", "-", "*"):
        op, num = val[0], float(val[1:])
        if op == "*":
            if not base:
                raise ValueError(f"cannot scale by {val!r} — the baseline value is 0 or absent, so the result would just be 0.")
            return base * num
        return base + num if op == "+" else base - num
    raise ValueError(f"cannot resolve override value {val!r} (use a number, or a '+x'/'-x'/'*x' delta).")


def _anchor(val, ages: dict):
    """A NUMBER is as-is; '@start_age' / '@by_age' / '@plan_to_age' (optionally +/-N) resolves to an integer age."""
    if isinstance(val, (int, float)) and not isinstance(val, bool):
        return val
    if isinstance(val, str) and val.startswith("@"):
        body = val[1:]
        for op in ("+", "-"):
            if op in body:
                name, n = body.split(op, 1)
                base = ages.get(name.strip())
                if base is None:
                    raise ValueError(f"unknown anchor @{name.strip()}")
                return int(base) + (int(n) if op == "+" else -int(n))
        base = ages.get(body.strip())
        if base is None:
            raise ValueError(f"unknown anchor @{body.strip()}")
        return int(base)
    raise ValueError(f"cannot resolve anchor {val!r}")


def _resolve_event(e: dict, ages: dict) -> dict:
    out = dict(e)
    for f in ("start", "end", "age", "born_age", "college_at"):
        if f in out:
            out[f] = _anchor(out[f], ages)
    return out


def _resolve_overrides(ov: dict, spec: dict) -> dict:
    a = {**engine.DEFAULTS, **spec.get("assumptions", {})}
    contrib = spec.get("contributions", {})
    ret = spec.get("retirement") or {}
    ages = {
        "start_age": spec["start"]["age"],
        "by_age": spec["target"]["by_age"],
        "plan_to_age": ret.get("plan_to_age", a["plan_to_age"]),
    }
    out: dict = {}
    for k, v in ov.items():
        if k == "assumptions":
            out[k] = {ak: _rel(av, a.get(ak, 0)) for ak, av in v.items()}
        elif k == "annual_savings":
            out[k] = _rel(v, contrib.get("annual_savings", 0))
        elif k == "annual_spend":
            out[k] = _rel(v, ret.get("annual_spend", 0))
        elif k == "income_growth":
            out[k] = _rel(v, contrib.get("income_growth", a["income_growth"]))
        elif k == "by_age":
            out[k] = int(_rel(v, ages["by_age"]))
        elif k == "plan_to_age":
            out[k] = int(_rel(v, ages["plan_to_age"]))
        elif k == "add_events":
            out[k] = [_resolve_event(e, ages) for e in v]
        else:  # market_scenario, remove_events, runs, retirement — absolute, pass through
            out[k] = v
    return out


def _deep_merge(base: dict, inline: dict) -> dict:
    """Merge an inline tweak onto a template's resolved overrides WITHOUT clobbering nested blocks:
    dict values (assumptions, market_scenario) merge per sub-key (inline wins); list values
    (add_events, remove_events) concatenate; scalars replace."""
    out = dict(base)
    for k, v in inline.items():
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k] = {**out[k], **v}
        elif isinstance(v, list) and isinstance(out.get(k), list):
            out[k] = out[k] + v
        else:
            out[k] = v
    return out


def _expand_templates(spec: dict) -> dict:
    """Replace each what-if that names a `template` with its resolved absolute overrides."""
    whatifs = spec.get("whatifs")
    if not whatifs:
        return spec
    lib = None
    expanded = []
    for w in whatifs:
        if isinstance(w, dict) and "template" in w:
            if lib is None:
                lib = _load_library()
            tname = w["template"]
            if tname not in lib:
                known = ", ".join(k for k in lib if not k.startswith("_"))
                sys.exit(f"ERROR: unknown scenario template {tname!r} (not in scenario_library.json). Known: {known}.")
            merged = _deep_merge(
                _resolve_overrides(lib[tname].get("overrides", {}), spec),
                _resolve_overrides(w.get("overrides", {}), spec),   # inline tweak wins, per sub-key
            )
            expanded.append({"name": w.get("name", tname), "overrides": merged})
        else:
            expanded.append(w)
    out = dict(spec)
    out["whatifs"] = expanded
    _guard_resolved(out)
    return out


def _guard_resolved(spec: dict) -> None:
    """A template can resolve to an invalid combo (e.g. pull_forward on a near-term goal makes
    by_age <= start_age). lint runs on the pre-resolution spec and can't see this, so guard here —
    fail loud instead of letting the engine's year loop blow up."""
    start_age = spec["start"]["age"]
    base_by = spec["target"]["by_age"]
    base_pta = (spec.get("retirement") or {}).get("plan_to_age")
    for w in spec.get("whatifs", []):
        if not isinstance(w, dict):
            continue
        nm = w.get("name", "?")
        ov = w.get("overrides", {})
        by = ov.get("by_age", base_by)
        if isinstance(by, int) and by <= start_age:
            sys.exit(f"ERROR: scenario {nm!r} resolves to by_age {by} <= start age {start_age} — "
                     f"pick a goal further out or drop this scenario.")
        pta = ov.get("plan_to_age", base_pta)
        if isinstance(pta, int) and isinstance(by, int) and pta <= by:
            sys.exit(f"ERROR: scenario {nm!r} resolves to plan_to_age {pta} <= by_age {by}.")


def _print_summary(res: dict) -> None:
    a = res["assumptions"]
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
    print(f"  · trim target→ ${tt['achievable']:,.0f} (today ${tt['achievable_today']:,.0f}) "
          f"{tt['with_prob']:.0%}-reachable by {tt['by_age']}")


def _write_plots(res: dict, spec: dict, outdir: str) -> list[str]:
    """Import plots lazily so a missing matplotlib fails loud at the plotting step, not at import."""
    import plots  # noqa: E402
    written = []
    scenarios = res["scenarios"]
    start_age = res["start_age"]
    goal_amount = spec.get("target", {}).get("amount")
    if "baseline" in scenarios:
        written.append(plots.fan_chart(
            scenarios["baseline"], start_age, goal_amount=goal_amount,
            title="Net worth — Monte Carlo (baseline)",
            path=os.path.join(outdir, "fan_baseline.png")))
    written.append(plots.compare(scenarios, start_age, path=os.path.join(outdir, "compare.png")))
    return written


def main() -> None:
    ap = argparse.ArgumentParser(description="Run the goal_planning engine + plots (single deterministic entry).")
    ap.add_argument("spec", help="path to the scenario_spec JSON assembled from the confirmed recap")
    ap.add_argument("--outdir", default=".", help="where to write result.json and the PNGs (default: cwd)")
    args = ap.parse_args()

    os.makedirs(args.outdir, exist_ok=True)
    spec = _load_spec(args.spec)
    try:
        spec = _expand_templates(spec)  # resolve scenario-library `template` refs -> absolute overrides
    except ValueError as ex:
        sys.exit(f"ERROR resolving a scenario template: {ex}")
    res = engine.run(spec)  # authoritative — the LLM never recomputes any of this

    result_path = os.path.join(args.outdir, "result.json")
    with open(result_path, "w", encoding="utf-8") as f:
        json.dump(res, f, ensure_ascii=False, indent=2, default=float)

    _print_summary(res)
    pngs = _write_plots(res, spec, args.outdir)
    print("\nwrote: " + ", ".join([result_path] + pngs))


if __name__ == "__main__":
    main()
