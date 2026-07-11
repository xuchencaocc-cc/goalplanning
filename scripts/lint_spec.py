#!/usr/bin/env python3
"""
lint_spec.py — mechanical validator for a goal_planning scenario_spec.

Run this on ./spec.json BEFORE run_plan.py. It catches the ways an assembled
spec goes wrong (missing block, a money field written as a string like "$10M",
a non-integer age, an unknown or under-specified life-event, a what-if whose
override would make the engine emit a silently-wrong number, etc.) so a bad
spec fails LOUD here instead of crashing the engine or producing a wrong plan.

Exit code 0 = OK to run (warnings allowed). Exit code 1 = at least one ERROR;
do NOT run the engine — fix the spec (re-confirm with the user if a number
must change).

Usage:  python3 lint_spec.py <spec.json>

Contract is derived from engine.py's actual reads + references/spec_schema.json.
"""
from __future__ import annotations

import json
import os
import sys

# Life-event types the engine understands (engine.apply_events / _events_for).
EVENT_TYPES = {
    "home_purchase", "home_sale", "child", "career_change",
    "startup", "gap_year", "sabbatical", "derisk", "eldercare", "windfall",
}
WHATIF_OVERRIDE_KEYS = {
    "annual_savings", "income_growth", "by_age", "add_events", "remove_events",
    "retirement", "plan_to_age", "annual_spend", "runs",
}

errors: list[str] = []
warns: list[str] = []


def err(msg: str) -> None:
    errors.append(msg)


def warn(msg: str) -> None:
    warns.append(msg)


def _is_num(x) -> bool:
    return isinstance(x, (int, float)) and not isinstance(x, bool)


def _is_int(x) -> bool:
    return isinstance(x, int) and not isinstance(x, bool)


def _check_money(path: str, val) -> None:
    """Monetary fields must be raw numbers, never strings like '$10M' or '1,000,000'."""
    if isinstance(val, str):
        err(f"{path} is a string ({val!r}); must be a raw number (write 10000000, not \"$10M\").")
    elif not _is_num(val):
        err(f"{path} must be a number, got {type(val).__name__}.")


def _check_age(path: str, val) -> None:
    """Ages feed range()/array indexing in the engine — must be whole integers, not floats or strings."""
    if isinstance(val, str):
        err(f"{path} is a string ({val!r}); must be an integer age (write 40, not \"40\").")
    elif isinstance(val, bool) or not _is_int(val):
        if isinstance(val, float):
            err(f"{path}={val} must be a whole-number integer age (a float breaks the engine's year loop).")
        else:
            err(f"{path} must be an integer age, got {type(val).__name__}.")


def _has_any(e: dict, *keys: str) -> bool:
    return any(k in e for k in keys)


def check(spec: dict) -> None:
    if not isinstance(spec, dict):
        err("top-level spec must be a JSON object.")
        return

    # --- start ---
    start = spec.get("start")
    if not isinstance(start, dict):
        err("missing 'start' block { age, assets }.")
        start = {}
    else:
        _check_age("start.age", start.get("age"))
        _check_money("start.assets", start.get("assets"))
        if _is_num(start.get("assets")) and start["assets"] < 0:
            err("start.assets is negative.")

    # --- target ---
    target = spec.get("target")
    if not isinstance(target, dict):
        err("missing 'target' block { amount, by_age, ... }.")
        target = {}
    else:
        _check_money("target.amount", target.get("amount"))
        _check_age("target.by_age", target.get("by_age"))
        if _is_num(target.get("amount")) and target["amount"] <= 0:
            err("target.amount must be > 0.")
        ms = target.get("min_success", 0.9)
        if not _is_num(ms) or not (0 < ms <= 1):
            err(f"target.min_success must be in (0, 1]; got {ms!r}.")
        if _is_int(start.get("age")) and _is_int(target.get("by_age")) and target["by_age"] <= start["age"]:
            err(f"target.by_age ({target.get('by_age')}) must be greater than start.age ({start.get('age')}).")

    # --- contributions (optional) ---
    contrib = spec.get("contributions", {})
    if contrib:
        if not isinstance(contrib, dict):
            err("'contributions' must be an object.")
        else:
            if "annual_savings" in contrib:
                _check_money("contributions.annual_savings", contrib["annual_savings"])
            if "income_growth" in contrib and not _is_num(contrib["income_growth"]):
                err("contributions.income_growth must be a number (e.g. 0.03).")

    # --- assumptions (optional; sanity ranges are warnings, not blocks) ---
    a = spec.get("assumptions", {})
    if a and not isinstance(a, dict):
        err("'assumptions' must be an object.")
    elif isinstance(a, dict):
        nr = a.get("nominal_return")
        if nr is not None and (not _is_num(nr) or not (0 < nr < 0.5)):
            warn(f"assumptions.nominal_return={nr!r} looks off (expected a fraction like 0.07).")
        inf = a.get("inflation")
        if inf is not None and (not _is_num(inf) or not (-0.1 < inf < 0.5)):
            warn(f"assumptions.inflation={inf!r} looks off (expected a fraction like 0.03).")
        rs = a.get("return_std")
        if rs is not None and (not _is_num(rs) or rs < 0):
            err("assumptions.return_std must be a non-negative number.")

    # --- retirement (optional; only for retire-type goals) ---
    ret = spec.get("retirement")
    if ret is not None:
        if not isinstance(ret, dict):
            err("'retirement' must be an object { annual_spend, plan_to_age }.")
        else:
            _check_money("retirement.annual_spend", ret.get("annual_spend"))
            pta = ret.get("plan_to_age")
            _check_age("retirement.plan_to_age", pta)
            if _is_int(pta) and _is_int(target.get("by_age")) and pta <= target["by_age"]:
                err(f"retirement.plan_to_age ({pta}) must be greater than target.by_age ({target.get('by_age')}).")

    # --- market_scenario (optional) ---
    mkt = spec.get("market_scenario", {})
    if mkt:
        if not isinstance(mkt, dict):
            err("'market_scenario' must be an object.")
        else:
            mode = mkt.get("mode")
            if mode is not None and mode not in ("monte_carlo", "sequence_risk"):
                err(f"market_scenario.mode must be 'monte_carlo' or 'sequence_risk'; got {mode!r}.")
            if "runs" in mkt and (not _is_num(mkt["runs"]) or mkt["runs"] < 1):
                err("market_scenario.runs must be a positive integer.")

    # --- life_events ---
    _check_events(spec.get("life_events", []), "life_events")

    # --- whatifs ---
    whatifs = spec.get("whatifs", [])
    if whatifs and not isinstance(whatifs, list):
        err("'whatifs' must be a list.")
    else:
        for i, w in enumerate(whatifs or []):
            _check_whatif(w, f"whatifs[{i}]", start, ret)


def _check_whatif(w, wp: str, start: dict, ret) -> None:
    if not isinstance(w, dict) or "name" not in w or "overrides" not in w:
        err(f"{wp} must be an object with 'name' and 'overrides'.")
        return
    name = w.get("name")
    if not isinstance(name, str) or not name.isascii():
        err(f"{wp}.name must be a short ASCII/Latin slug (e.g. no_house, retire_45); "
            f"non-ASCII names render as tofu boxes in the chart legend.")
    ov = w["overrides"]
    if not isinstance(ov, dict):
        err(f"{wp}.overrides must be an object.")
        return
    for k in ov:
        if k not in WHATIF_OVERRIDE_KEYS:
            warn(f"{wp}.overrides has unrecognized key {k!r} (engine will ignore it).")
    # Bound-check override scalars the same way the top-level fields are checked,
    # so an absurd what-if (e.g. by_age <= start.age) fails loud instead of
    # producing a silently-plausible engine number.
    if "by_age" in ov:
        _check_age(f"{wp}.overrides.by_age", ov["by_age"])
        if _is_int(ov["by_age"]) and _is_int(start.get("age")) and ov["by_age"] <= start["age"]:
            err(f"{wp}.overrides.by_age ({ov['by_age']}) must be greater than start.age ({start.get('age')}).")
    if "plan_to_age" in ov:
        _check_age(f"{wp}.overrides.plan_to_age", ov["plan_to_age"])
    if "annual_savings" in ov:
        _check_money(f"{wp}.overrides.annual_savings", ov["annual_savings"])
    if "annual_spend" in ov:
        _check_money(f"{wp}.overrides.annual_spend", ov["annual_spend"])
    if "runs" in ov and (not _is_num(ov["runs"]) or ov["runs"] < 1):
        err(f"{wp}.overrides.runs must be a positive integer.")
    if "remove_events" in ov and not isinstance(ov["remove_events"], list):
        err(f"{wp}.overrides.remove_events must be a list of event-type strings.")
    _check_events(ov.get("add_events", []), f"{wp}.overrides.add_events")


def _check_events(events, path: str) -> None:
    if events and not isinstance(events, list):
        err(f"'{path}' must be a list.")
        return
    for i, e in enumerate(events or []):
        ep = f"{path}[{i}]"
        if not isinstance(e, dict):
            err(f"{ep} must be an object.")
            continue
        t = e.get("type")
        if t not in EVENT_TYPES:
            err(f"{ep}.type={t!r} is not a known event type ({', '.join(sorted(EVENT_TYPES))}).")
            continue
        # Per-type required fields, matching what engine.apply_events actually
        # reads (and, for window events, the fields it dereferences unguarded).
        if t in ("home_purchase", "home_sale", "career_change"):
            if "age" not in e:
                err(f"{ep} (type {t}) is missing required field 'age'.")
        elif t == "child":
            if "born_age" not in e:
                err(f"{ep} (type child) is missing required field 'born_age'.")
        elif t in ("startup", "gap_year", "sabbatical"):
            # engine: s=get('start',get('age')), en=get('end',get('age')); a missing
            # 'end' with no 'age' -> en=None -> 'age <= None' TypeError crashes the run.
            if not _has_any(e, "start", "age"):
                err(f"{ep} (type {t}) needs 'start' (or 'age').")
            if not _has_any(e, "end", "age"):
                err(f"{ep} (type {t}) needs 'end' (or 'age') — a missing end crashes the engine.")
        elif t == "derisk":
            if "nominal_return" not in e:
                err(f"{ep} (type derisk) is missing required field 'nominal_return'.")
            if not _has_any(e, "start", "age"):
                err(f"{ep} (type derisk) needs 'start' (or 'age').")
        elif t == "eldercare":
            if "start" not in e:
                err(f"{ep} (type eldercare) is missing required field 'start'.")
            if "end" not in e:
                err(f"{ep} (type eldercare) is missing required field 'end'.")
        elif t == "windfall":
            if "age" not in e:
                err(f"{ep} (type windfall) is missing required field 'age'.")
            if not _has_any(e, "amount", "cashflow"):
                err(f"{ep} (type windfall) needs 'amount' (or 'cashflow').")
        # No monetary/age field may be a string.
        for k, v in e.items():
            if k == "type":
                continue
            if isinstance(v, str):
                err(f"{ep}.{k} is a string ({v!r}); event amounts/ages must be raw numbers.")


def main() -> None:
    if len(sys.argv) < 2:
        sys.exit("usage: python3 lint_spec.py <spec.json>")
    path = sys.argv[1]
    if not os.path.exists(path):
        sys.exit(f"ERROR: spec file not found: {path}")
    try:
        with open(path, encoding="utf-8") as f:
            spec = json.load(f)
    except json.JSONDecodeError as ex:
        sys.exit(f"ERROR: {path} is not valid JSON: {ex}")

    check(spec)

    for w in warns:
        print(f"WARN  {w}")
    for e in errors:
        print(f"ERROR {e}")

    if errors:
        print(f"\nFAILED: {len(errors)} error(s), {len(warns)} warning(s). Do NOT run the engine — fix the spec.")
        sys.exit(1)
    print(f"OK: spec valid ({len(warns)} warning(s)).")


if __name__ == "__main__":
    main()
