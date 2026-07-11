"""
plots.py — charts for goal_planning results (matplotlib; writes PNGs).

fan_chart(result, start_age, goal_amount=None) -> Monte-Carlo percentile fan for one scenario
compare(results, start_age)                    -> baseline vs what-ifs (median net-worth paths)

matplotlib is chosen over plotly: it's always present in the sandbox and writes a static PNG
with no browser. Switch to plotly only if an interactive HTML artifact is required.
"""
from __future__ import annotations
import matplotlib
matplotlib.use("Agg")  # headless: write files, no display
import matplotlib.pyplot as plt


def _ages(series, start_age):
    return list(range(start_age, start_age + len(series)))


def fan_chart(result, start_age, goal_amount=None, title="Net worth — Monte Carlo", path="fan.png"):
    pct = result["percentiles_by_year"]
    ages = _ages(pct[50], start_age)
    fig, ax = plt.subplots(figsize=(9, 5))
    ax.fill_between(ages, pct[10], pct[90], alpha=0.18, label="10–90%")
    ax.fill_between(ages, pct[25], pct[75], alpha=0.32, label="25–75%")
    ax.plot(ages, pct[50], lw=2.2, label="median")
    if goal_amount:
        ax.axhline(goal_amount, ls="--", lw=1, label="goal")
    ax.axhline(0, color="black", lw=0.8)
    ax.set_xlabel("Age"); ax.set_ylabel("Net worth ($, real)")
    ax.set_title(title); ax.legend(loc="upper left")
    ax.ticklabel_format(style="plain", axis="y")
    fig.savefig(path, dpi=120, bbox_inches="tight")
    plt.close(fig)
    return path


def compare(results, start_age, title="Scenarios — median net worth", path="compare.png"):
    fig, ax = plt.subplots(figsize=(9, 5))
    for name, r in results.items():
        med = r["percentiles_by_year"][50]
        ax.plot(_ages(med, start_age), med, lw=2, label=name)
    ax.axhline(0, color="black", lw=0.8)
    ax.set_xlabel("Age"); ax.set_ylabel("Net worth ($, real, median)")
    ax.set_title(title); ax.legend(loc="upper left")
    ax.ticklabel_format(style="plain", axis="y")
    fig.savefig(path, dpi=120, bbox_inches="tight")
    plt.close(fig)
    return path
