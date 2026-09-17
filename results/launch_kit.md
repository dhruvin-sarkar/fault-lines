# Launch kit

Drafts for announcing the project. Every number below comes from `results/` and matches the technical report. Links: demo <https://dhruvin-sarkar.github.io/fault-lines/>, code <https://github.com/dhruvin-sarkar/fault-lines>.

## Thread (7 posts)

**1** (attach `assets/hero.png`)
HHMI Janelia and Google Research released the complete connectome of a male fruit fly's central nervous system, brain and nerve cord together. How much of it can be lost before the senses stop reaching the neurons that move the body? Removing the 4.1% of cell types with the most output synapses halves sensory-to-motor routing. Random loss needs 28.3%.

**2** (attach `results/percolation_curves.png`)
I reduced the connectome to 11,751 cell types and 243,439 connections and measured routing as flow capacity: the number of edge-disjoint paths from 368 sensory types to 665 descending and motor types, 10,647 when intact. Six removal orders were fixed in a pre-registration before any run. All five targeted orders fall below the random interval (27.7% to 28.9%).

**3**
Routing thins long before anything is cut off. When flow halves, at most 37 of 11,751 types have lost every path from sensory input, whatever the order. Then, under sensory-motor betweenness, a single batch cuts off 6,046 types at once. Once half of all types are gone, 5,306 of the 5,846 survivors have no sensory path, against 1 in the first random trial.

**4** (attach `results/brain_vnc_curves.png`)
Which cell types are critical depends on the circuit. Run separately, the brain loses half its routing after 5.9% of types by sensory-motor betweenness, the nerve cord only after 12.6%. Weighted in-degree does the reverse: 25.3% in the brain, 6.6% in the nerve cord. Under random removal they do not differ significantly (Welch t = −1.54, p = 0.13).

**5**
A few more results. Removing all 480 descending neuron types costs 66.4% of routing, against 8.2% for random sets of the same size. Removing the strongest connections first halves it after 26.8% of connections, against 47.6% at random. And 14 cell types with published behavioral evidence rank high in sensory-motor betweenness (p = 0.045, or 0.10 with the motor neuron control).

**6**
Caveats: the literature result is modest and weakens to p = 0.10 with the motor neuron control included; cascade sizes are not robustly power-law (bootstrap p = 0.202 and 0.036); against 200 degree-preserving randomized graphs the real wiring is significantly more fragile under all six orders, though p = 0.005 is the smallest a 200-graph test can give and the test does not say which features of the wiring are responsible. This is a static wiring diagram at cell-type resolution. It says nothing about what a fly would do. Not peer reviewed.

**7** (attach `assets/readme/fault-lines-poster.png`)
Atlas, attack replays and every finding: https://dhruvin-sarkar.github.io/fault-lines/
Code, report and `make reproduce`: https://github.com/dhruvin-sarkar/fault-lines
Data: HHMI Janelia FlyEM and Google Research, Berg et al., Cell 2026, doi:10.1016/j.cell.2026.08.015

## Show HN

**Title:** Show HN: How much of a fly's nervous system can you remove before sensing stops reaching movement?

**Text:**

HHMI Janelia FlyEM and Google Research published the connectome of an entire male *Drosophila* central nervous system, brain and ventral nerve cord together (Berg et al., Cell 2026). Because it contains both the sensory neurons that enter the CNS and the descending and motor neurons that leave it, you can extend attack-tolerance analyses, including percolation on the FlyWire brain (Lin et al., Nature 2024), to routing from sensory input to motor output: how much wiring can be lost before sensory input no longer reaches motor output?

I built a cell-type graph from neuPrint's `male-cns:v1.0` (11,751 types, 243,439 connections that each supply at least 1% of the target's input) and measured routing as maximum flow with unit capacities, which by Menger's theorem is the number of edge-disjoint paths from 368 sensory types to 665 descending and motor types. The intact graph has 10,647. Then I removed types in six orders, 1% of the remaining types per batch with every score recomputed, under a plan committed to the repository before the first run.

Removing the types with the most output synapses first halves flow capacity after 4.1% of types. Random removal needs 28.3% (95% CI 27.7% to 28.9%, 30 runs). That is the range printed for the AS-level Internet and a Web sample under degree attack, though the breakdown criteria differ, so the comparison is only qualitative.

Other pieces:

- the collapse has two phases: at the half-flow point at most 37 types are disconnected, then one batch of sensory-motor betweenness removal cuts off 6,046
- the brain and nerve cord have different weak points under the same protocol
- removing connections strongest first halves flow after 26.8% of them, against 47.6% at random
- four low-degree types, such as `ALIN7`, carry a top 1% share of sensory-to-motor shortest routes, yet removing `ALIN7` costs only 9 of 10,647 paths
- a static React site that replays each attack on an atlas of all 11,751 cell types

What it does not show: anything about behavior, activity, synaptic sign or electrical synapses. Cascade sizes are not robustly power-law, the literature check is modest (p = 0.045, and 0.10 with the pre-registered control included), and the pre-registered null model finds the real graph significantly more fragile than 200 degree-preserving randomizations under all six orders, which rules out the degree sequence alone as the explanation but does not say what the explanation is. Everything reproduces with `make reproduce` from public neuPrint data.

Demo: https://dhruvin-sarkar.github.io/fault-lines/
Code and report: https://github.com/dhruvin-sarkar/fault-lines

## Reddit (r/neuroscience)

**Title:** Attack tolerance of the complete male Drosophila CNS connectome: sensory-to-motor routing halves after removing 4.1% of cell types by output synapses, versus 28.3% at random

**Body:**

The male CNS connectome from HHMI Janelia FlyEM and Google Research (Berg et al., *Cell* 2026, doi:10.1016/j.cell.2026.08.015) covers brain and nerve cord in one animal. I used it to run a pre-registered percolation study on sensory-to-motor routing.

**Setup.** I built a type-level graph from neuPrint's `male-cns:v1.0`:

- 11,751 cell types from 164,506 typed neurons; 243,439 directed connections, each at least 1% of the target type's input
- sources: 368 sensory types; sinks: 665 descending and motor types, all from superclass annotations
- primary metric: flow capacity, the number of edge-disjoint sensory-to-motor paths (10,647 intact); secondary: connected sensory-motor pairs (237,405 of 244,720)
- six removal orders (random, weighted out-degree, weighted in-degree, betweenness, PageRank, and betweenness restricted to sensory-to-motor paths), 1% of the remaining types per batch with scores recomputed, 30 random runs

Hypotheses, tests and every protocol parameter were committed before any percolation run.

**Results:**

- flow halves after 4.1% of types by weighted out-degree, 9.0% by betweenness, 9.6% by sensory-motor betweenness, 13.9% by weighted in-degree, 18.7% by PageRank and 28.3% at random (95% CI 27.7% to 28.9%)
- at each order's half-flow point at most 37 types are disconnected from all sensory input; under sensory-motor betweenness one batch later cuts off 6,046 types
- brain and nerve cord run separately: sensory-motor betweenness halves brain flow after 5.9% and nerve cord flow after 12.6%; weighted in-degree gives 25.3% and 6.6%
- removing all 480 descending neuron types costs 66.4% of flow (same-size random sets: 8.2%); ascending neurons, neither source nor sink, cost 34.7% (9.7%)
- the gnathal ganglia hold the most routes: removing their 1,237 anchored types costs 34.7% against 20.6% for random sets (exploratory, uncorrected)
- strongest connections first halve flow after 26.8% of connections, random order after 47.6%; weakest first never halves it within 50%
- 14 cell types with published activation or silencing evidence rank above other types in sensory-motor betweenness: one-sided Mann-Whitney p = 0.045, AUC 0.63
- left and right hemisphere copies: 205 of 4,449 informative types lose more flow with both sides removed than the two single-side losses add up to (one-sided Wilcoxon p = 5.2e-37); for 12, one side fully covers the other

**Caveats I would flag first:**

- The literature result depends on the pre-registered exclusion of the motor neuron control MN9. With it included, p = 0.10, and the 14 cell types are a small, non-random sample.
- Structural cascade sizes do not robustly follow a power law (bootstrap p = 0.202 in the primary set, 0.036 with all random runs pooled), and a lognormal fits as well.
- Degree-preserving null model (200 randomized graphs, same protocol, one-sided tests at 0.05 / 6 = 0.0083): the real graph is significantly more fragile under all six orders, but p = 0.005 is the floor for 200 graphs, and the randomizations keep degrees and output synapse totals only, so the test does not say which features of the wiring matter.
- Unit capacities ignore synapse counts, types of one neuron count the same as types of thousands, and removing a type from a graph is not silencing it in a fly.

I'd welcome criticism of the flow-capacity metric and the terminal set definitions in particular.

Demo (atlas, attack replays, findings): https://dhruvin-sarkar.github.io/fault-lines/
Code and technical report: https://github.com/dhruvin-sarkar/fault-lines

## awesome-fly entry (draft)

For a pull request to `cobanov/awesome-fly`, following its `CONTRIBUTING.md`:

> **[Fault Lines](https://github.com/dhruvin-sarkar/fault-lines)**: pre-registered attack-tolerance study of the male CNS connectome (male-cns v1.0), measuring how sensory-to-motor flow capacity collapses under random and targeted removal of cell types and connections; static site with an atlas that replays each attack. Complete, including a pre-registered degree-preserving null model.
