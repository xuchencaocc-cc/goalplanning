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
    "recurring_cashflow",
}
WHATIF_OVERRIDE_KEYS = {
    "annual_savings", "income_growth", "by_age", "add_events", "remove_events",
    "retirement", "plan_to_age", "annual_spend", "runs",
    "assumptions", "market_scenario",
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


def _is_delta(v) -> bool:
    """A '+x' / '-x' / '*x' relative-delta string (only valid inside a what-if template/override)."""
    if not isinstance(v, str) or v[:1] not in ("+", "-", "*"):
        return False
    try:
        float(v[1:])
        return True
    except ValueError:
        return False


def _check_assumptions_block(a, path: str, allow_delta: bool) -> None:
    """Validate an `assumptions` block. Top-level must be absolute numbers; a what-if override may also
    use '+x'/'-x'/'*x' deltas (the resolver applies them to the baseline). A bad value is an ERROR
    (not just a range WARN) because the engine does `a.update(...)` then arithmetic on it — a string crashes."""
    if not isinstance(a, dict):
        err(f"'{path}' must be an object.")
        return
    ranges = {"nominal_return": (0, 0.5), "inflation": (-0.1, 0.5)}
    for k in ("nominal_return", "inflation", "return_std", "income_growth"):
        if k not in a:
            continue
        v = a[k]
        if _is_num(v):
            if k == "return_std" and v < 0:
                err(f"{path}.return_std must be non-negative.")
            elif k in ranges and not (ranges[k][0] < v < ranges[k][1]):
                warn(f"{path}.{k}={v!r} looks off (expected a fraction like 0.07 / 0.03).")
        elif allow_delta and _is_delta(v):
            continue
        else:
            tail = " or a '+x'/'-x'/'*x' delta" if allow_delta else ""
            err(f"{path}.{k}={v!r} must be a number{tail} (a string breaks the engine's math).")


def _check_market_block(mkt, path: str) -> None:
    """Validate a `market_scenario` block (top-level or what-if override). Values are always absolute."""
    if not isinstance(mkt, dict):
        err(f"'{path}' must be an object.")
        return
    mode = mkt.get("mode")
    if mode is not None and mode not in ("monte_carlo", "sequence_risk"):
        err(f"{path}.mode must be 'monte_carlo' or 'sequence_risk'; got {mode!r}.")
    for k in ("runs", "crash_year", "depth", "seed"):
        if k in mkt and not _is_num(mkt[k]):
            err(f"{path}.{k} must be a number, got {mkt[k]!r} (a string crashes monte_carlo).")
    if _is_num(mkt.get("runs")) and mkt["runs"] < 1:
        err(f"{path}.runs must be a positive integer.")


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


_LIB = None
_LIB_LOADED = False


def _load_library():
    """Scenario library that sits next to this script in the bundle (../references/)."""
    global _LIB, _LIB_LOADED
    if _LIB_LOADED:
        return _LIB
    _LIB_LOADED = True
    p = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "references", "scenario_library.json")
    try:
        with open(p, encoding="utf-8") as f:
            _LIB = json.load(f)
    except Exception:  # noqa: BLE001
        _LIB = None
    return _LIB


def _check_template(name, wp: str) -> None:
    if not isinstance(name, str):
        err(f"{wp}.template must be a string.")
        return
    lib = _load_library()
    if lib is None:
        warn(f"{wp}.template={name!r} — scenario_library.json not found next to lint; cannot verify the name.")
        return
    if name not in lib:
        known = ", ".join(k for k in lib if not k.startswith("_"))
        err(f"{wp}.template={name!r} is not in scenario_library.json. Known: {known}.")


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

    # --- assumptions (optional; top-level must be absolute numbers, no deltas) ---
    if "assumptions" in spec:
        _check_assumptions_block(spec["assumptions"], "assumptions", allow_delta=False)

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
    if "market_scenario" in spec:
        _check_market_block(spec["market_scenario"], "market_scenario")

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
    if not isinstance(w, dict):
        err(f"{wp} must be an object.")
        return
    template = w.get("template")
    if template is None and "overrides" not in w:
        err(f"{wp} must have 'overrides' or a 'template'.")
        return
    if template is not None:
        _check_template(template, wp)
    name = w.get("name")
    if name is None and template is None:
        err(f"{wp} must have a 'name'.")
    elif name is not None and (not isinstance(name, str) or not name.isascii()):
        err(f"{wp}.name must be a short ASCII/Latin slug (e.g. no_house, retire_45); "
            f"non-ASCII names render as tofu boxes in the chart legend.")
    ov = w.get("overrides", {})
    if not isinstance(ov, dict):
        err(f"{wp}.overrides must be an object.")
        return
    for k in ov:
        if k not in WHATIF_OVERRIDE_KEYS:
            warn(f"{wp}.overrides has unrecognized key {k!r} (engine will ignore it).")
    # Bound-check override scalars. A what-if override value may be ABSOLUTE or a '+x'/'-x'/'*x' delta
    # (scenarios.md documents inline tweaks like annual_savings: "*1.2"); the resolver handles deltas and
    # _guard_resolved bound-checks the resolved by_age/plan_to_age, so here we only reject outright-invalid
    # values and can bound-check only when the override is already an absolute number.
    if "by_age" in ov and not _is_delta(ov["by_age"]):
        _check_age(f"{wp}.overrides.by_age", ov["by_age"])
        if _is_int(ov["by_age"]) and _is_int(start.get("age")) and ov["by_age"] <= start["age"]:
            err(f"{wp}.overrides.by_age ({ov['by_age']}) must be greater than start.age ({start.get('age')}).")
    if "plan_to_age" in ov and not _is_delta(ov["plan_to_age"]):
        _check_age(f"{wp}.overrides.plan_to_age", ov["plan_to_age"])
    if "annual_savings" in ov and not _is_delta(ov["annual_savings"]):
        _check_money(f"{wp}.overrides.annual_savings", ov["annual_savings"])
    if "annual_spend" in ov and not _is_delta(ov["annual_spend"]):
        _check_money(f"{wp}.overrides.annual_spend", ov["annual_spend"])
    if "income_growth" in ov and not _is_delta(ov["income_growth"]) and not _is_num(ov["income_growth"]):
        err(f"{wp}.overrides.income_growth must be a number or a '+x'/'-x'/'*x' delta.")
    if "runs" in ov and (not _is_num(ov["runs"]) or ov["runs"] < 1):
        err(f"{wp}.overrides.runs must be a positive integer.")
    if "remove_events" in ov and not isinstance(ov["remove_events"], list):
        err(f"{wp}.overrides.remove_events must be a list of event-type strings.")
    if "assumptions" in ov:
        _check_assumptions_block(ov["assumptions"], f"{wp}.overrides.assumptions", allow_delta=True)
    if "market_scenario" in ov:
        _check_market_block(ov["market_scenario"], f"{wp}.overrides.market_scenario")
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
        elif t == "recurring_cashflow":
            if "start" not in e:
                err(f"{ep} (type recurring_cashflow) is missing required field 'start'.")
            if "end" not in e:
                err(f"{ep} (type recurring_cashflow) is missing required field 'end'.")
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
