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
    res = engine.run(spec)  # authoritative — the LLM never recomputes any of this

    result_path = os.path.join(args.outdir, "result.json")
    with open(result_path, "w", encoding="utf-8") as f:
        json.dump(res, f, ensure_ascii=False, indent=2, default=float)

    _print_summary(res)
    pngs = _write_plots(res, spec, args.outdir)
    print("\nwrote: " + ", ".join([result_path] + pngs))


if __name__ == "__main__":
    main()
