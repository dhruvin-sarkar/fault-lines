"""Test whether cell types with published behavioral necessity or sufficiency rank high in structural criticality."""

import json

import numpy as np
import pandas as pd
from scipy import stats

from pipeline.build_type_graph import load_type_graph
from pipeline.common import RESULTS
from pipeline.figures import INK, INK_SECONDARY, MUTED, STRATEGY_COLORS, apply_style, plt
from pipeline.hidden_bottleneck import percentile_ranks
from pipeline.identify_sensory_motor_sets import load_sensory_motor_sets
from pipeline.removal_strategies import intact_scores
from pipeline.single_removal import load_single_removal

ALPHA = 0.05

# Evidence: S = activation sufficient to evoke the behavior, N = silencing or ablation impairs it.
CURATED = [
    ("DNp01", "Giant Fiber", "fast looming-evoked escape takeoff", "S+N", ["vonreyn2014", "lima2005"]),
    ("MDN", "moonwalker descending neurons", "backward walking", "S+N", ["bidaye2014", "sen2017"]),
    ("LPLC2", "LPLC2", "looming-evoked escape", "S+N", ["klapoetke2017", "ache2019cb"]),
    ("LC4", "LC4", "fast looming-evoked escape", "S+N", ["vonreyn2017", "wu2016"]),
    ("DNp07", "DNp07", "landing", "S+N", ["ache2019nn"]),
    ("DNp10", "DNp10", "landing", "S+N", ["ache2019nn"]),
    ("DNp09", "P9", "object-directed walking; pursuit of the female", "S+N", ["bidaye2020"]),
    ("pIP10", "pIP10", "courtship song", "S+N", ["vonphilipsborn2011", "lillvis2024"]),
    ("aSP22", "aSP22 (DNa12)", "courtship action sequence", "S+N", ["mckellar2019"]),
    ("DNa02", "DNa02", "ipsilateral turning while walking", "S", ["yang2024", "rayshubskiy2025"]),
    ("EPG", "E-PG compass neurons", "menotaxis (holding a heading relative to a sun stimulus)", "N", ["giraldo2018"]),
    ("PFL3", "PFL3", "goal-directed steering", "S+N", ["westeinde2024", "mussellspires2024"]),
    ("MBON11", "MBON-γ1pedc>α/β", "aversive memory expression", "N", ["aso2014"]),
    ("PPL101", "PPL1-γ1pedc", "punishment signal for aversive memory", "S+N", ["aso2014"]),
]
POSITIVE_CONTROL = ("MN9", "mn9 motor neuron", "proboscis extension", "S+N", ["mckellar2020", "gordon2009"])
ALTERNATIVE_P9 = "DNp71"

REFERENCES = {
    "vonreyn2014": "von Reyn CR, Breads P, Peek MY, et al. (2014). A spike-timing mechanism for action selection. Nature Neuroscience 17:962–970. doi:10.1038/nn.3741",
    "lima2005": "Lima SQ, Miesenböck G (2005). Remote control of behavior through genetically targeted photostimulation of neurons. Cell 121:141–152. doi:10.1016/j.cell.2005.02.004",
    "bidaye2014": "Bidaye SS, Machacek C, Wu Y, Dickson BJ (2014). Neuronal control of Drosophila walking direction. Science 344:97–101. doi:10.1126/science.1249964",
    "sen2017": "Sen R, Wu M, Branson K, et al. (2017). Moonwalker descending neurons mediate visually evoked retreat in Drosophila. Current Biology 27:766–771. doi:10.1016/j.cub.2017.02.008",
    "klapoetke2017": "Klapoetke NC, Nern A, Peek MY, et al. (2017). Ultra-selective looming detection from radial motion opponency. Nature 551:237–241. doi:10.1038/nature24626",
    "ache2019cb": "Ache JM, Polsky J, Alghailani S, et al. (2019). Neural basis for looming size and velocity encoding in the Drosophila giant fiber escape pathway. Current Biology 29:1073–1081. doi:10.1016/j.cub.2019.01.079",
    "vonreyn2017": "von Reyn CR, Nern A, Williamson WR, et al. (2017). Feature integration drives probabilistic behavior in the Drosophila escape response. Neuron 94:1190–1204. doi:10.1016/j.neuron.2017.05.036",
    "wu2016": "Wu M, Nern A, Williamson WR, et al. (2016). Visual projection neurons in the Drosophila lobula link feature detection to distinct behavioral programs. eLife 5:e21022. doi:10.7554/eLife.21022",
    "ache2019nn": "Ache JM, Namiki S, Lee A, Branson K, Card GM (2019). State-dependent decoupling of sensory and motor circuits underlies behavioral flexibility in Drosophila. Nature Neuroscience 22:1132–1139. doi:10.1038/s41593-019-0413-4",
    "bidaye2020": "Bidaye SS, Laturney M, Chang AK, et al. (2020). Two brain pathways initiate distinct forward walking programs in Drosophila. Neuron 108:469–485. doi:10.1016/j.neuron.2020.07.032",
    "vonphilipsborn2011": "von Philipsborn AC, Liu T, Yu JY, et al. (2011). Neuronal control of Drosophila courtship song. Neuron 69:509–522. doi:10.1016/j.neuron.2011.01.011",
    "lillvis2024": "Lillvis JL, Wang K, Shiozaki HM, et al. (2024). Nested neural circuits generate distinct acoustic signals during Drosophila courtship. Current Biology 34:808–824. doi:10.1016/j.cub.2024.01.015",
    "mckellar2019": "McKellar CE, Lillvis JL, Bath DE, et al. (2019). Threshold-based ordering of sequential actions during Drosophila courtship. Current Biology 29:426–434. doi:10.1016/j.cub.2018.12.019",
    "yang2024": "Yang HH, Brezovec BE, Serratosa Capdevila L, et al. (2024). Fine-grained descending control of steering in walking Drosophila. Cell 187:6290–6308. doi:10.1016/j.cell.2024.08.033",
    "rayshubskiy2025": "Rayshubskiy A, Holtz SL, Bates AS, et al. (2025). Neural circuit mechanisms for steering control in walking Drosophila. eLife 13:RP102230. doi:10.7554/eLife.102230",
    "giraldo2018": "Giraldo YM, Leitch KJ, Ros IG, et al. (2018). Sun navigation requires compass neurons in Drosophila. Current Biology 28:2845–2852. doi:10.1016/j.cub.2018.07.002",
    "westeinde2024": "Westeinde EA, Kellogg E, Dawson PM, et al. (2024). Transforming a head direction signal into a goal-oriented steering command. Nature 626:819–826. doi:10.1038/s41586-024-07039-2",
    "mussellspires2024": "Mussells Pires P, Zhang L, Parache V, Abbott LF, Maimon G (2024). Converting an allocentric goal into an egocentric steering signal. Nature 626:808–818. doi:10.1038/s41586-023-07006-3",
    "aso2014": "Aso Y, Sitaraman D, Ichinose T, et al. (2014). Mushroom body output neurons encode valence and guide memory-based action selection in Drosophila. eLife 3:e04580. doi:10.7554/eLife.04580",
    "mckellar2020": "McKellar CE, Siwanowicz I, Dickson BJ, Simpson JH (2020). Controlling motor neurons of every muscle for fly proboscis reaching. eLife 9:e54978. doi:10.7554/eLife.54978",
    "gordon2009": "Gordon MD, Scott K (2009). Motor control in a Drosophila taste circuit. Neuron 61:373–384. doi:10.1016/j.neuron.2008.12.033",
    "namiki2018": "Namiki S, Dickinson MH, Wong AM, Korff W, Card GM (2018). The functional organization of descending sensory-motor pathways in Drosophila. eLife 7:e34272. doi:10.7554/eLife.34272",
}
SCORES = {
    "sm_betweenness": "sensory-motor betweenness (primary)",
    "flow_drop": "flow capacity lost when removed alone",
    "betweenness": "global betweenness",
}


def rank_test(scores: pd.Series, members: list[str]) -> dict:
    """One-sided Mann-Whitney U: do ``members`` score higher than every other type?"""
    inside = scores[scores.index.isin(members)]
    outside = scores[~scores.index.isin(members)]
    u, p = stats.mannwhitneyu(inside, outside, alternative="greater", method="asymptotic")
    auc = u / (len(inside) * len(outside))
    return {"n_curated": int(len(inside)), "n_other": int(len(outside)), "U": float(u), "p_value": float(p),
            "auc": float(auc), "rank_biserial": float(2 * auc - 1),
            "median_percentile": float(percentile_ranks(scores)[inside.index].median())}


def main() -> None:
    graph = load_type_graph()
    sources, targets = load_sensory_motor_sets()
    table = intact_scores(graph, sources, targets).merge(load_single_removal()[["cell_type", "flow_drop", "pairs_lost"]],
                                                         on="cell_type")
    table["superclass"] = graph.vs["superclass"]
    table["n_neurons"] = graph.vs["n_neurons"]
    table = table.set_index("cell_type")
    curated = [c[0] for c in CURATED]
    missing = [t for t in curated + [POSITIVE_CONTROL[0], ALTERNATIVE_P9] if t not in table.index]
    if missing:
        raise RuntimeError(f"Curated types absent from the graph: {missing}")

    sets = {
        "primary": curated,
        "with_positive_control": curated + [POSITIVE_CONTROL[0]],
        "DNp71_for_DNp09": [ALTERNATIVE_P9 if t == "DNp09" else t for t in curated],
    }
    results = {name: {score: rank_test(table[score], members) for score in SCORES} for name, members in sets.items()}
    percentiles = pd.DataFrame({score: percentile_ranks(table[score]) for score in SCORES})

    (RESULTS / "literature_validation.json").write_text(json.dumps({
        "alpha": ALPHA, "tests": results,
        "curated_types": {t: {"published_name": name, "behavior": behavior, "evidence": evidence,
                              "superclass": table.loc[t, "superclass"], "n_neurons": int(table.loc[t, "n_neurons"]),
                              **{f"{s}_percentile": float(percentiles.loc[t, s]) for s in SCORES},
                              **{s: float(table.loc[t, s]) for s in SCORES}}
                          for t, name, behavior, evidence, _ in CURATED + [POSITIVE_CONTROL]},
    }, indent=2) + "\n", encoding="utf-8")

    apply_style()
    fig, ax = plt.subplots(figsize=(8.5, 5.4), dpi=200)
    order = sorted(CURATED + [POSITIVE_CONTROL], key=lambda c: percentiles.loc[c[0], "sm_betweenness"])
    y = np.arange(len(order))
    for j, (score, color) in enumerate([("sm_betweenness", STRATEGY_COLORS["sm_betweenness"]),
                                        ("flow_drop", STRATEGY_COLORS["pagerank"]),
                                        ("betweenness", STRATEGY_COLORS["betweenness"])]):
        ax.scatter([percentiles.loc[c[0], score] for c in order], y + (j - 1) * 0.22, s=36, color=color,
                   label=SCORES[score], zorder=3)
    ax.axvline(50, color=MUTED, linewidth=1, linestyle="--")
    ax.set_yticks(y, [f"{c[0]}{' (control)' if c is POSITIVE_CONTROL else ''}" for c in order], fontsize=8.5, color=INK)
    ax.set_xlim(0, 100)
    ax.set_xlabel("percentile among all cell types (higher = more critical)")
    ax.set_title("Behaviorally validated cell types in the structural rankings", loc="left", pad=28)
    ax.legend(loc="lower center", bbox_to_anchor=(0.5, 1.02), ncol=3, fontsize=8, frameon=False)
    p = results["primary"]["sm_betweenness"]
    fig.text(0.01, 0.01, f"Primary test (sensory-motor betweenness, one-sided Mann-Whitney U, n = {p['n_curated']} vs "
             f"{p['n_other']}): U = {p['U']:.0f}, p = {p['p_value']:.2g}, AUC = {p['auc']:.2f}.", fontsize=8, color=INK_SECONDARY)
    fig.tight_layout(rect=(0, 0.03, 1, 1))
    fig.savefig(RESULTS / "literature_rank_plot.png")
    plt.close(fig)

    def verdict(r: dict) -> str:
        return "significant" if r["p_value"] < ALPHA else "not significant"

    lines = [
        "# Literature validation",
        "",
        "Do cell types that published experiments have shown to be necessary or sufficient for a behavior sit high in "
        "the purely structural criticality ranking? The curated list below was compiled from the primary literature, "
        "each connectome type name was checked against the male CNS annotations, and the list and test were fixed in "
        "`results/preregistration.md` before any score was computed. None of these neurons was tested experimentally "
        "in this project.",
        "",
        "## Curated cell types",
        "",
        "Evidence: S = activating the neurons evokes the behavior; N = silencing or ablating them impairs it.",
        "",
        "| type | published name | behavior | evidence | superclass | neurons | sensory-motor betweenness percentile | flow-drop percentile | betweenness percentile | sources |",
        "|---|---|---|---|---|---|---|---|---|---|",
    ]
    for t, name, behavior, evidence, refs in CURATED + [POSITIVE_CONTROL]:
        label = f"`{t}`" + (" (positive control)" if t == POSITIVE_CONTROL[0] else "")
        lines.append(f"| {label} | {name} | {behavior} | {evidence} | {table.loc[t, 'superclass']} | {int(table.loc[t, 'n_neurons'])} | "
                     f"{percentiles.loc[t, 'sm_betweenness']:.1f} | {percentiles.loc[t, 'flow_drop']:.1f} | "
                     f"{percentiles.loc[t, 'betweenness']:.1f} | {'; '.join(f'[{r}]' for r in refs)} |")
    lines += [
        "",
        "Name mapping notes. `MDN` is the connectome type for the moonwalker descending neurons (\"DNp50\" appears only "
        "as a synonym). P9 is scored as `DNp09`, which matches the FlyWire and MANC type of the genetic line used; a "
        "second type, `DNp71`, also carries the hemibrain label DNp09 and is tested as a sensitivity check. `aSP22` is "
        "the connectome name for the descending neuron published as DNa12. For DNa02, bilateral silencing did not "
        "reduce turning, so the evidence is sufficiency only. `MN9` is a motor neuron and thus structurally essential "
        "almost by construction; it is kept out of the primary test. Descending neuron nomenclature follows Namiki et "
        "al. (2018) [namiki2018].",
        "",
        "## Test",
        "",
        "One-sided Mann–Whitney U test, alternative that the curated types score higher than all other cell types. A "
        "rank-based test is used because centrality scores are heavy-tailed with many ties at zero and the two groups "
        "differ in size by three orders of magnitude, so no distributional assumption is appropriate. The AUC "
        "(U divided by the product of group sizes) is the probability that a randomly chosen curated type outscores a "
        f"randomly chosen other type. α = {ALPHA}.",
        "",
        "| set | score | n | U | p (one-sided) | AUC | median percentile | result |",
        "|---|---|---|---|---|---|---|---|",
    ]
    set_labels = {"primary": "primary (14 types)", "with_positive_control": "with MN9", "DNp71_for_DNp09": "DNp71 instead of DNp09"}
    for name in sets:
        for score, label in SCORES.items():
            r = results[name][score]
            lines.append(f"| {set_labels[name]} | {label} | {r['n_curated']} | {r['U']:.0f} | {r['p_value']:.2g} | "
                         f"{r['auc']:.3f} | {r['median_percentile']:.1f} | {verdict(r)} |")
    p = results["primary"]["sm_betweenness"]
    lines += [
        "",
        f"Primary result: the curated types {'do' if p['p_value'] < ALPHA else 'do not'} rank significantly higher in "
        f"sensory-motor betweenness than other cell types (U = {p['U']:.0f}, p = {p['p_value']:.2g}, AUC = {p['auc']:.2f}, "
        f"median percentile {p['median_percentile']:.0f}).",
        "",
        "A positive result shows agreement between a structural ranking and published behavioral experiments for this "
        "small, non-random sample of well-studied neurons. Well-studied neurons are not a random draw from the "
        "population (they were found because they are large, accessible or have striking phenotypes), so the test "
        "cannot show that the ranking identifies essential neurons in general.",
        "",
        "![Percentiles of the curated types](literature_rank_plot.png)",
        "",
        "## References",
        "",
        *[f"- [{key}] {text}" for key, text in REFERENCES.items()],
        "",
    ]
    (RESULTS / "literature_validation.md").write_text("\n".join(lines), encoding="utf-8")
    print("\n".join(lines[-len(REFERENCES) - 12:-len(REFERENCES) - 3]))


if __name__ == "__main__":
    main()
