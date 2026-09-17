"""Place the connectome's critical removal fractions next to published attack-tolerance thresholds of other networks."""

import json

import pandas as pd

from pipeline.common import RESULTS
from pipeline.figures import GRID, INK, INK_SECONDARY, MUTED, STRATEGY_COLORS, apply_style, plt
from pipeline.removal_strategies import STRATEGY_LABELS

REFERENCES = {
    "Albert 2000": "Albert, R., Jeong, H. & Barabási, A.-L. (2000). Error and attack tolerance of complex networks. "
                   "Nature 406, 378–382. https://doi.org/10.1038/35019019",
    "Cohen 2000": "Cohen, R., Erez, K., ben-Avraham, D. & Havlin, S. (2000). Resilience of the Internet to random "
                  "breakdowns. Physical Review Letters 85, 4626–4628. https://doi.org/10.1103/PhysRevLett.85.4626",
    "Cohen 2001": "Cohen, R., Erez, K., ben-Avraham, D. & Havlin, S. (2001). Breakdown of the Internet under intentional "
                  "attack. Physical Review Letters 86, 3682–3685. https://doi.org/10.1103/PhysRevLett.86.3682",
    "Jeong 2001": "Jeong, H., Mason, S. P., Barabási, A.-L. & Oltvai, Z. N. (2001). Lethality and centrality in protein "
                  "networks. Nature 411, 41–42. https://doi.org/10.1038/35075138",
    "Holme 2002": "Holme, P., Kim, B. J., Yoon, C. N. & Han, S. K. (2002). Attack vulnerability of complex networks. "
                  "Physical Review E 65, 056109. https://doi.org/10.1103/PhysRevE.65.056109",
    "Albert 2004": "Albert, R., Albert, I. & Nakarado, G. L. (2004). Structural vulnerability of the North American "
                   "power grid. Physical Review E 69, 025103(R). https://doi.org/10.1103/PhysRevE.69.025103",
    "Achard 2006": "Achard, S., Salvador, R., Whitcher, B., Suckling, J. & Bullmore, E. (2006). A resilient, "
                   "low-frequency, small-world human brain functional network with highly connected association "
                   "cortical hubs. Journal of Neuroscience 26, 63–72. https://doi.org/10.1523/JNEUROSCI.3874-05.2006",
    "Schneider 2011": "Schneider, C. M., Moreira, A. A., Andrade, J. S., Havlin, S. & Herrmann, H. J. (2011). "
                      "Mitigation of malicious attacks on networks. PNAS 108, 3838–3841. "
                      "https://doi.org/10.1073/pnas.1009440108",
    "Joyce 2013": "Joyce, K. E., Hayasaka, S. & Laurienti, P. J. (2013). The human functional brain network "
                  "demonstrates structural and dynamical resilience to targeted attack. PLoS Computational Biology 9, "
                  "e1002885. https://doi.org/10.1371/journal.pcbi.1002885",
}

# Only values printed in the text of the primary source; figure read-offs are described in prose instead.
PUBLISHED = [
    {"network": "Internet, autonomous-system level (6,209 nodes)", "removal": "targeted, by degree",
     "criterion": "largest cluster fragments", "value": 0.03, "qualifier": "≈", "citation": "Albert 2000",
     "location": "main text, Internet paragraph"},
    {"network": "World Wide Web sample (325,729 pages)", "removal": "targeted, by out-degree",
     "criterion": "largest cluster fragments", "value": 0.067, "qualifier": "=", "citation": "Albert 2000",
     "location": "main text and Fig. 3 caption"},
    {"network": "Scale-free model (N = 10,000)", "removal": "targeted, by degree",
     "criterion": "largest cluster fragments", "value": 0.18, "qualifier": "≈", "citation": "Albert 2000",
     "location": "main text, fragmentation paragraph"},
    {"network": "Exponential random model (N = 10,000)", "removal": "targeted, by degree",
     "criterion": "largest cluster fragments", "value": 0.28, "qualifier": "≈", "citation": "Albert 2000",
     "location": "main text, fragmentation paragraph"},
    {"network": "North American power grid (14,099 substations)", "removal": "targeted, by load",
     "criterion": "up to 60% loss of generator-to-substation connectivity", "value": 0.04, "qualifier": "=",
     "citation": "Albert 2004", "location": "main text"},
    {"network": "Human functional brain network (90 regions)", "removal": "targeted, by degree",
     "criterion": "largest cluster halved", "value": 0.40, "qualifier": "≈", "citation": "Achard 2006",
     "location": "Results and Discussion"},
    {"network": "Scale-free comparison network", "removal": "targeted, by degree",
     "criterion": "largest cluster halved", "value": 0.20, "qualifier": "=", "citation": "Achard 2006",
     "location": "Results"},
    {"network": "Human voxel-wise functional network (15,996 voxels)", "removal": "targeted, recalculated centrality",
     "criterion": "first dramatic giant-component reduction", "value": 0.40, "qualifier": "≈",
     "citation": "Joyce 2013", "location": "Results and Discussion"},
    {"network": "Scale-free network, Internet-like exponent (N > 10⁶)", "removal": "random",
     "criterion": "spanning cluster vanishes", "value": 0.99, "qualifier": ">", "citation": "Cohen 2000",
     "location": "abstract"},
]

WITHOUT_THRESHOLD = {
    "Cohen 2001": "Removing the highest-degree sites destroys scale-free networks after a few percent of sites. The "
                  "critical fraction is shown only as a curve against the degree exponent (about 0.06 at exponent 2.5 "
                  "with minimum degree 1, read from Fig. 1); no value is printed for the Internet.",
    "Jeong 2001": "In the yeast protein interaction network, removing the most connected proteins rapidly increases "
                  "the network diameter while random removal does not; no removal fraction is given. The printed "
                  "numbers concern lethality: about 62% of proteins with more than 15 links are essential, against "
                  "about 21% of those with 5 or fewer.",
    "Holme 2002": "Degree and betweenness rankings recalculated during removal are often more harmful than rankings "
                  "fixed on the intact network. Results are curves and values after 1% removal, not thresholds.",
    "Schneider 2011": "Introduces the robustness index R, the area under the largest-component curve during "
                      "recalculated-degree attack; the fragility score here is the same construction applied to flow "
                      "capacity.",
}

GROUP_COLORS = {"this study": STRATEGY_COLORS["sm_betweenness"], "published, targeted": STRATEGY_COLORS["betweenness"],
                "published, random": MUTED}


def comparison_table(thresholds: dict) -> pd.DataFrame:
    """Published thresholds and this study's f_c values in one table, with a display group for each row."""
    ours = [
        {"network": f"Male CNS cell types, {STRATEGY_LABELS[s]}",
         "removal": "random" if s == "random" else f"targeted, adaptive {STRATEGY_LABELS[s]}",
         "criterion": "sensory-to-motor flow capacity halved", "value": v["f_c"], "qualifier": "=",
         "citation": "this study", "location": "results/critical_thresholds.json"}
        for s, v in thresholds["strategies"].items()
    ]
    table = pd.DataFrame(ours + PUBLISHED)
    table["group"] = [
        "this study" if c == "this study" else "published, random" if r == "random" else "published, targeted"
        for c, r in zip(table["citation"], table["removal"])
    ]
    return table


def plot(table: pd.DataFrame) -> None:
    apply_style()
    order = {g: i for i, g in enumerate(GROUP_COLORS)}
    rows = table.assign(rank=table["group"].map(order)).sort_values(["rank", "value"]).reset_index(drop=True)
    fig, ax = plt.subplots(figsize=(10, 0.4 * len(rows) + 1.6), dpi=200)
    positions = range(len(rows) - 1, -1, -1)
    for y, row in zip(positions, rows.itertuples()):
        ax.hlines(y, 0, row.value, color=GRID, linewidth=1, zorder=1)
        ax.plot(row.value, y, "o", markersize=8, color=GROUP_COLORS[row.group], markeredgecolor="white",
                markeredgewidth=1.5, zorder=3)
        prefix = "" if row.qualifier == "=" else row.qualifier
        ax.text(row.value + 0.012, y, f"{prefix}{row.value:.3g}", va="center", fontsize=8, color=INK_SECONDARY)
    ax.set_yticks(list(positions))
    ax.set_yticklabels([f"{r.network} ({r.citation})" for r in rows.itertuples()], fontsize=8)
    ax.set_xlim(0, 1.08)
    ax.set_xlabel("fraction of nodes removed at breakdown (the breakdown criterion differs by study)")
    ax.set_title("Critical removal fractions: this connectome and published networks", loc="left", color=INK)
    for group, color in GROUP_COLORS.items():
        ax.plot([], [], "o", color=color, markersize=7, label=group)
    ax.legend(loc="upper right", frameon=False)
    ax.grid(axis="y", visible=False)
    fig.tight_layout()
    fig.savefig(RESULTS / "network_comparison.png")
    plt.close(fig)


def main() -> None:
    thresholds = json.loads((RESULTS / "critical_thresholds.json").read_text(encoding="utf-8"))
    table = comparison_table(thresholds)
    table.to_csv(RESULTS / "network_comparison.csv", index=False, float_format="%.4f")
    plot(table)

    ours = thresholds["strategies"]
    random_ci = ours["random"]["f_c_ci95"]
    worst = min((s for s in ours if s != "random"), key=lambda s: ours[s]["f_c"])
    lines = [
        "# Comparison with published network fragility",
        "",
        "## The numbers are not measured the same way",
        "",
        "The threshold here is the fraction of cell types removed when the maximum sensory-to-motor flow (the number of "
        "edge-disjoint directed paths from sensory to descending and motor types) falls below half its intact value, "
        "with scores recalculated after every 1% of removals. The classic studies instead track the size of the "
        "largest connected cluster, mostly on undirected graphs and often with rankings fixed on the intact network, "
        "and call the network broken when that cluster disintegrates or halves. A source-to-sink capacity is limited "
        "by the narrowest cut between two designated sets, so it can halve long before a giant component disappears. "
        "The values below therefore sit side by side as context, not as the same quantity measured on different "
        "networks. The closest analogue is the power-grid study, which also measures connectivity from a source set "
        "(generators) to a sink set (distribution substations).",
        "",
        "## This connectome",
        "",
        "| strategy | fraction of cell types removed when flow halves |",
        "|---|---|",
        *[f"| {STRATEGY_LABELS[s]} | {v['f_c']:.3f} |" for s, v in sorted(ours.items(), key=lambda kv: kv[1]["f_c"])
          if s != "random"],
        f"| {STRATEGY_LABELS['random']} | {ours['random']['f_c']:.3f} (95% CI {random_ci[0]:.3f} to {random_ci[1]:.3f}) |",
        "",
        "## Published thresholds (values printed in the primary source)",
        "",
        "| network | removal | breakdown criterion | fraction removed | source, location |",
        "|---|---|---|---|---|",
        *[f"| {r['network']} | {r['removal']} | {r['criterion']} | {'' if r['qualifier'] == '=' else r['qualifier']}"
          f"{r['value']:g} | {r['citation']}, {r['location']} |" for r in PUBLISHED],
        "",
        "![Critical removal fractions](network_comparison.png)",
        "",
        "## Studies without a comparable printed threshold",
        "",
        *[f"- {name}: {text}" for name, text in WITHOUT_THRESHOLD.items()],
        "",
        "## Reading",
        "",
        f"Under the most damaging strategy ({STRATEGY_LABELS[worst]}), sensory-to-motor capacity halves after "
        f"{100 * ours[worst]['f_c']:.1f}% of cell types are removed. That is the range reported for engineered "
        "hub-dominated networks under degree or load attack (the autonomous-system Internet at about 3%, the Web "
        "sample at 6.7%, the power grid losing up to 60% of connectivity at 4%) and well below the roughly 40% "
        f"reported for human functional brain networks. Random removal needs {100 * ours['random']['f_c']:.1f}% of "
        "cell types. Because the criterion, the resolution (cell types rather than neurons or regions), edge direction "
        "and recalculation all differ, the comparison supports only a qualitative statement: sensory-to-motor routing "
        "in this connectome is concentrated enough that targeted removal of a few percent of cell types halves it.",
        "",
        "## References",
        "",
        *[f"- {text}" for text in REFERENCES.values()],
        "",
    ]
    (RESULTS / "network_comparison.md").write_text("\n".join(lines), encoding="utf-8")
    print("\n".join(lines))


if __name__ == "__main__":
    main()
