# Scenario playbook — choosing what-ifs for a goal plan (Phase A)

Load this when a goal-planning conversation goes past the basics — the user names a specific worry
(a crash, inflation, losing a job), a tailwind (a raise, an inheritance, side income), or asks "what if…".
It tells you which what-ifs to run and how to keep the picture **balanced** (a range, not a wall of crashes).

## The point: show a RANGE, not doom
A good plan shows the user their **floor and ceiling**, not five ways to fail. Always pair downside with
upside. If the baseline is already healthy, lead with that and the upside — don't manufacture alarm
(that's the skill's default-innocent voice). A crash scenario on a wildly over-funded plan just confirms
"you're crash-proof" — say so plainly rather than dressing it up as a warning.

## Default panel (run these unless the user steers otherwise)
The what-ifs go in the `whatifs` list; **baseline always runs**. Reference a template by name:
```
"whatifs": [ { "name": "upside", "template": "bull_run" }, { "template": "crash_at_goal" } ]
```
- **Retirement or accumulation goal:** `bull_run` (things go well) + `crash_at_goal` (the classic stress).
  For retirement also add `longevity_100` (living long is the real retirement risk).
- **Home / education / one-off target:** `bull_run` + `crash_at_goal` + one of `save_less_20` / `save_more_20`
  (savings discipline is the lever they actually control).
Show all chosen scenarios in the recap, one line each, before you transfer.

## Template library (in the bundle as `scenario_library.json`)
Values resolve against the user's OWN baseline, so they work in any market:

| band | template | means |
|---|---|---|
| 🟢 upside | `bull_run` | returns +2.5pts |
| 🟢 upside | `save_more_20` | save 20% more |
| 🟢 upside | `pull_forward_5` | hit the goal 5 years sooner |
| 🔴 downside | `crash_at_goal` | a −35% crash right at the goal year |
| 🔴 downside | `gfc_2008` | a 2008-style −37% crash |
| 🔴 downside | `high_inflation` | inflation +3pts (returns +1) |
| 🔴 downside | `lost_decade` | returns flat at 2% |
| 🔴 downside | `job_loss_2yr` | two years of zero saving, starting now |
| 🔴 downside | `save_less_20` | save 20% less |
| ⚪ neutral | `push_back_5` | give the goal 5 more years |
| ⚪ neutral | `longevity_100` | plan to age 100 (retirement) |

You may tweak a template inline (template as a base, then override one field):
```
{ "name": "crash_then_save", "template": "crash_at_goal", "overrides": { "annual_savings": "*1.2" } }
```

## Amount-specific scenarios — NOT templates (add the raw event with the user's real number)
A windfall or a stream of income depends on the user's actual figure, so gather it and add the event
directly to `life_events` (or a what-if's `add_events`):
- **A windfall** (inheritance, RSU vesting, bonus, sale proceeds): `{ "type": "windfall", "age": <when>, "amount": <NOMINAL $, negative if an outflow> }`
- **A recurring stream** (rental income, part-time work, alimony, support payments): `{ "type": "recurring_cashflow", "start": <age>, "end": <age>, "annual": <NOMINAL $/yr>, "growth": 0.02 }` (negative `annual` = a recurring drain)

## Progressive disclosure — don't turn intake into a form
Default to the simple panel. Only go deeper when the user's situation or question calls for it:
- user worries about a crash → make sure `crash_at_goal` (or `gfc_2008`) is in;
- high-inflation market or the user raises it → add `high_inflation`;
- user mentions a possible inheritance / RSU / bonus → add a `windfall` event (ask the amount + rough timing);
- rental property, side gig, a pension not yet modeled → add `recurring_cashflow` (or `income_streams` if/when available);
- user asks "could I do it sooner / what if I save more" → `pull_forward_5` / `save_more_20`.
Never run more than ~4–5 what-ifs; a plan with 10 lines is noise, not insight.

## Audit rule (unchanged)
Every scenario is a deterministic engine path (fixed seed). You pick which scenarios run and name them in
the recap; the engine computes every number. You never hand-estimate a scenario's outcome.
