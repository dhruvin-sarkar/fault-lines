"""Test whether structural failure cascades during adaptive removal follow a power law (Clauset-Shalizi-Newman)."""

import argparse
import json
import warnings

import numpy as np
import powerlaw

from pipeline.common import RESULTS, SEED
from pipeline.figures import INK, INK_SECONDARY, MUTED, STRATEGY_COLORS, apply_style, plt
from pipeline.removal_strategies import STRATEGIES
from pipeline.run_percolation import RANDOM_TRIALS, TARGETED, auc_window, load_all_runs

BOOTSTRAP_SIMS = 1000
ALTERNATIVES = ("exponential", "lognormal", "truncated_power_law")
PLAUSIBLE_P = 0.1


def run_avalanches(run: dict) -> np.ndarray:
    """Avalanche sizes of the batches that fall within the first 50% of removals."""
    return np.asarray(run["avalanche"][: auc_window(run["fraction_removed"]) - 1], dtype=int)


def fit_power_law(sizes: np.ndarray) -> powerlaw.Fit:
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        return powerlaw.Fit(sizes, discrete=True, verbose=False)


def bootstrap_p_value(sizes: np.ndarray, fit: powerlaw.Fit, n_sims: int, seed: int) -> float:
    """Semi-parametric bootstrap goodness-of-fit p-value (Clauset, Shalizi and Newman 2009, section 4.1).

    Each synthetic dataset has the empirical size; with probability n_tail / n a value is drawn from the fitted
    power law above x_min, otherwise uniformly from the observed values below x_min. The synthetic data are refit
    with x_min re-estimated, and p is the fraction of synthetic KS distances at least as large as the observed one.
    """
    rng = np.random.default_rng(seed)
    np.random.seed(seed % 2**32)
    body = sizes[sizes < fit.xmin]
    n = len(sizes)
    exceed = 0
    for _ in range(n_sims):
        n_tail = rng.binomial(n, fit.n_tail / n)
        tail = fit.power_law.generate_random(n_tail) if n_tail else np.array([])
        synthetic = np.concatenate([rng.choice(body, n - n_tail) if len(body) else np.array([]), tail])
        exceed += int(fit_power_law(synthetic).power_law.D >= fit.power_law.D)
    return exceed / n_sims


def analyse(sizes: np.ndarray, n_sims: int, seed: int) -> tuple[dict, powerlaw.Fit]:
    positive = sizes[sizes > 0]
    fit = fit_power_law(positive)
    comparisons = {}
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        for alternative in ALTERNATIVES:
            ratio, p = fit.distribution_compare("power_law", alternative, normalized_ratio=True)
            comparisons[alternative] = {"loglikelihood_ratio": float(ratio), "p_value": float(p)}
    result = {
        "batches": int(len(sizes)),
        "zero_size": int(np.sum(sizes == 0)),
        "fitted": int(len(positive)),
        "max_size": int(positive.max()),
        "alpha": float(fit.power_law.alpha),
        "alpha_se": float(fit.power_law.sigma),
        "xmin": float(fit.xmin),
        "n_tail": int(fit.n_tail),
        "ks_distance": float(fit.power_law.D),
        "bootstrap_sims": n_sims,
        "bootstrap_p": bootstrap_p_value(positive, fit, n_sims, seed),
        "comparisons": comparisons,
    }
    result["power_law_plausible"] = bool(result["bootstrap_p"] >= PLAUSIBLE_P)
    return result, fit


def verdict(r: dict) -> str:
    favored = [a for a, c in r["comparisons"].items() if c["loglikelihood_ratio"] < 0 and c["p_value"] < PLAUSIBLE_P]
    disfavored = [a for a, c in r["comparisons"].items() if c["loglikelihood_ratio"] > 0 and c["p_value"] < PLAUSIBLE_P]
    parts = [
        f"The power law is {'not rejected' if r['power_law_plausible'] else 'rejected'} by the bootstrap test "
        f"(p = {r['bootstrap_p']:.3f}; plausible if p ≥ {PLAUSIBLE_P})."
    ]
    if favored:
        parts.append(f"The likelihood-ratio tests significantly favor the {', '.join(a.replace('_', ' ') for a in favored)} "
                     "over the power law.")
    if disfavored:
        parts.append(f"The power law is significantly favored over the {', '.join(a.replace('_', ' ') for a in disfavored)}.")
    if not favored and not disfavored:
        parts.append("None of the likelihood-ratio tests distinguishes the power law from the alternatives at p < 0.1.")
    return " ".join(parts)


def conclusion(primary: dict, sensitivity: dict, per_strategy: dict) -> str:
    """Overall reading of the primary and sensitivity fits."""
    largest = max(per_strategy, key=lambda s: per_strategy[s]["max_size"])
    agree = primary["power_law_plausible"] == sensitivity["power_law_plausible"]
    lognormal_open = all(r["comparisons"]["lognormal"]["p_value"] >= PLAUSIBLE_P for r in (primary, sensitivity))
    if agree and primary["power_law_plausible"]:
        text = "Both data sets are consistent with a power law."
    elif agree:
        text = "Both data sets reject a power law."
    else:
        def status(r: dict) -> str:
            return f"{'does not reject' if r['power_law_plausible'] else 'rejects'} a power law (p = {r['bootstrap_p']:.3f})"

        text = (f"The pre-registered primary data set {status(primary)}, but the larger sensitivity set "
                f"{status(sensitivity)}, so the result does not survive a change in which runs are pooled.")
    if lognormal_open:
        text += " In neither set can a lognormal be distinguished from the power law, so the data do not establish scale-free cascades."
    text += (f" The tail is also dominated by a few very large events: the single largest avalanche ({per_strategy[largest]['max_size']} "
             f"types) comes from the {largest} run.")
    return text


def plot(primary_sizes: dict[str, np.ndarray], fit: powerlaw.Fit, result: dict) -> None:
    apply_style()
    fig, ax = plt.subplots(figsize=(7.5, 5.2), dpi=200)
    pooled = np.concatenate(list(primary_sizes.values()))
    pooled = pooled[pooled > 0]
    values = np.sort(pooled)
    ccdf = 1 - np.arange(len(values)) / len(values)
    ax.loglog(values, ccdf, marker="o", linestyle="none", markersize=4, color=MUTED, alpha=0.8,
              label=f"observed avalanches (n = {len(values)})")
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        tail_share = result["n_tail"] / result["fitted"]
        x = np.unique(values[values >= fit.xmin])
        ax.loglog(x, tail_share * fit.power_law.ccdf(x), color=STRATEGY_COLORS["sm_betweenness"],
                  label=f"power law, α = {result['alpha']:.2f} ± {result['alpha_se']:.2f}, x_min = {result['xmin']:.0f}")
        ax.loglog(x, tail_share * fit.lognormal.ccdf(x), color=STRATEGY_COLORS["betweenness"], linestyle="--",
                  label="lognormal (same x_min)")
        ax.loglog(x, tail_share * fit.exponential.ccdf(x), color=STRATEGY_COLORS["pagerank"], linestyle=":",
                  label="exponential (same x_min)")
    ax.set_xlabel("avalanche size (cell types newly cut off from every sensory type)")
    ax.set_ylabel("P(size ≥ x)")
    ax.set_title("Structural cascade sizes during adaptive removal", loc="left", color=INK)
    ax.text(0.02, 0.04, f"KS D = {result['ks_distance']:.3f}, bootstrap p = {result['bootstrap_p']:.3f} "
            f"({result['bootstrap_sims']} synthetic sets)", transform=ax.transAxes, fontsize=8.5, color=INK_SECONDARY)
    ax.legend(loc="upper right")
    fig.tight_layout()
    fig.savefig(RESULTS / "avalanche_ccdf.png")
    plt.close(fig)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sims", type=int, default=BOOTSTRAP_SIMS)
    args = parser.parse_args()

    runs = load_all_runs()
    primary = {s: run_avalanches(runs[(s, 0)]) for s in STRATEGIES}
    sensitivity = [run_avalanches(runs[(s, 0)]) for s in TARGETED] + [
        run_avalanches(runs[("random", t)]) for t in range(RANDOM_TRIALS)
    ]
    primary_result, primary_fit = analyse(np.concatenate(list(primary.values())), args.sims, SEED)
    sensitivity_result, _ = analyse(np.concatenate(sensitivity), args.sims, SEED + 1)
    per_strategy = {s: {"batches": int(len(v)), "zero_size": int(np.sum(v == 0)), "max_size": int(v.max()),
                        "total_cut_off": int(v.sum())} for s, v in primary.items()}
    summary = {"primary": primary_result, "sensitivity_all_random_trials": sensitivity_result, "per_strategy": per_strategy}
    (RESULTS / "avalanche_analysis.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    plot(primary, primary_fit, primary_result)

    def block(name: str, r: dict) -> list[str]:
        rows = [f"| {a.replace('_', ' ')} | {c['loglikelihood_ratio']:+.3f} | {c['p_value']:.3f} |" for a, c in r["comparisons"].items()]
        return [
            f"### {name}",
            "",
            f"{r['batches']} removal batches; {r['zero_size']} had no avalanche (size 0) and are excluded from the fit; "
            f"{r['fitted']} positive sizes, largest {r['max_size']}.",
            "",
            "| quantity | value |",
            "|---|---|",
            f"| exponent α | {r['alpha']:.3f} ± {r['alpha_se']:.3f} |",
            f"| x_min (KS-minimizing) | {r['xmin']:.0f} |",
            f"| sizes ≥ x_min | {r['n_tail']} |",
            f"| KS distance D | {r['ks_distance']:.4f} |",
            f"| bootstrap goodness-of-fit p ({r['bootstrap_sims']} synthetic sets) | {r['bootstrap_p']:.3f} |",
            "",
            "Likelihood-ratio tests (normalized log-likelihood ratio R; R > 0 favors the power law, R < 0 the alternative; "
            "p tests whether the sign of R is significant):",
            "",
            "| alternative | R | p |",
            "|---|---|---|",
            *rows,
            "",
            verdict(r),
            "",
        ]

    lines = [
        "# Structural avalanche analysis",
        "",
        "## What is measured",
        "",
        "After each adaptive removal batch, the avalanche size is the number of cell types still in the graph that "
        "have just lost every directed path from the remaining sensory types, not counting the types removed in that "
        "batch. A large avalanche means one batch of removals silently disconnected many other types.",
        "",
        "This asks whether *structural failure cascades* in the wiring diagram are scale-free. It is a different "
        "question from the finding that *neural activity* propagates in power-law-distributed avalanches in cortical "
        "tissue (Beggs and Plenz, 2003): no activity is simulated here, and a power law in one says nothing about the "
        "other.",
        "",
        "## Method",
        "",
        "Discrete power-law fit by maximum likelihood with x_min chosen to minimize the Kolmogorov–Smirnov distance "
        "(Clauset, Shalizi and Newman, 2009), using the `powerlaw` package (Alstott, Bullmore and Plenz, 2014). "
        "Goodness of fit by semi-parametric bootstrap; the power law is treated as plausible when p ≥ 0.1. "
        "Alternatives compared by Vuong's normalized log-likelihood ratio. No log-log regression is used.",
        "",
        "Primary data: every batch within the first 50% of removals for one run per strategy (the five targeted runs "
        "and random trial 0). Sensitivity: the five targeted runs plus all 30 random trials.",
        "",
        "## Results",
        "",
        *block("Primary (one run per strategy)", primary_result),
        *block(f"Sensitivity (targeted runs plus all {RANDOM_TRIALS} random trials)", sensitivity_result),
        "## Conclusion",
        "",
        conclusion(primary_result, sensitivity_result, per_strategy),
        "",
        "## Per strategy (primary runs)",
        "",
        "| strategy | batches | zero-size batches | largest avalanche | types cut off in total |",
        "|---|---|---|---|---|",
        *[f"| {s} | {v['batches']} | {v['zero_size']} | {v['max_size']} | {v['total_cut_off']} |" for s, v in per_strategy.items()],
        "",
        "![Avalanche size distribution](avalanche_ccdf.png)",
        "",
    ]
    (RESULTS / "avalanche_analysis.md").write_text("\n".join(lines), encoding="utf-8")
    print(json.dumps({k: v for k, v in primary_result.items() if k != "comparisons"}, indent=1))
    print(verdict(primary_result))


if __name__ == "__main__":
    main()
