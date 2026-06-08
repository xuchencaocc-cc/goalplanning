---
name: goal_planning
description: Long-horizon goal & retirement planning with what-if scenarios, sequence-of-returns risk,
  Monte Carlo, and solve-for — gather inputs and define scenarios in chat, then download a deterministic,
  auditable engine in the sandbox and run it. Trigger on "can I retire at X", "am I on track", "what if
  I buy a house / save more / the market does Y", "how much do I need to save to…". Spending habits →
  spending_insight; current-state risk → cashflow_health.
metadata:
  execution_mode: sandbox
---

# Goal Planning

Two phases — the sandbox is one-way (once inside you can't ask the user). In chat: build a complete
scenario_spec. Then enter the sandbox to download the engine and compute. Multi-round exploration is in
chat — each round is one closed round-trip.

## Phase A — in chat: assemble a complete scenario_spec

### Step 1 — build the story (extract → ask → assume → confirm)
The user can only give ~30%. Extend it to a coherent ~70% they can react to — never a form.
1. **Extract** — injected finance profile (age, income, household, goals, risk) + Plaid tools
   (get_net_worth, get_savings_rate) for hard numbers.
2. **Ask** — only a few things you can't infer: the target (retire age / target number / desired
   retirement life) and any big plans already on their mind. Keep it short.
3. **Assume → 70%** — from profile + answers, fill in the rest: likely life events (kids' education,
   existing mortgage, RSU if tech, a derisk at retirement), per-phase parameters, market assumptions
   (assumptions.md). Two rules on the assumed 40%: **Coherent** — every assumption follows from
   profile/answers, never contradicts them. **Visible** — mark what you assumed vs what they told you,
   so they can correct just that.
4. **Confirm → iterate** — narrate the 70% story back in one paragraph (events + key assumptions).
   OK → assemble the spec. Not OK → re-ask only the part they pushed back on.

### Step 2 — assemble scenario_spec
Self-contained JSON (schema + supported life events in references/spec_schema.json + assumptions.md).
Pin every parameter — the sandbox won't come back to ask. Include baseline + any what-ifs (a what-if
may add events via `overrides.add_events`) + optional solve_for.

## Phase B — in the sandbox: download the engine, then run it
The authoritative engine lives in references/ — **download and run it; never rewrite it.**
1. Fetch & unpack:
     curl -fsSL -o /tmp/gp_refs.zip "<ZIP_URL>"
     unzip -o /tmp/gp_refs.zip -d ./references
2. Write the Phase-A scenario_spec to ./spec.json
3. Run:  python references/engine.py ./spec.json     → success rate / paths / solve
4. Plot with references/plots.py (fan_chart + compare) → PNGs, then upload them.
If the download fails or references/engine.py is missing, tell the user and STOP — never fabricate an
engine or hand-compute the numbers.

## Hard rule (Evidence)
Every figure = engine/tool output or an injected-profile fact. You never project/compound/percentage
yourself — the engine does. Always state the assumptions used.

## Boundaries
Read-only, educational, under the system prompt's compliance/disclaimer rules — projections are
illustrative, not guarantees; no specific investment/tax/legal directives. Surface missing inputs.
