# Pre-registered analysis plan

Written on 2026-09-15, after the cell-type graph was built and before any percolation run on the real graph or any randomized graph. The commit that adds this file precedes every commit containing a percolation, null-model or downstream result, so the order can be checked in the repository history. Nothing below is changed after results are seen. Any deviation is reported as a deviation in the corresponding results file.

## Graph and terminal sets

- Graph: 11,751 cell types, 243,439 directed edges (a type-to-type connection is kept when it supplies at least 1% of the target type's input synapses; self-loops dropped). Built by `pipeline/build_type_graph.py`.
- S: 368 primary sensory types; M: 665 descending and motor types (`results/sensory_motor_sets.md`).

## Metrics

- `flow_capacity`: maximum S→M flow with unit capacity on graph edges and unbounded supersource/supersink edges, which equals the number of edge-disjoint S→M paths. This is the primary metric.
- `reachability`: number of (s, m) pairs joined by a directed path. Secondary metric.
- Both curves are normalized by their value on the intact graph. A removed sensory or motor type loses all of its pairs and paths.

## Removal protocol

Six strategies: random, weighted out-degree, weighted in-degree, betweenness (hop-count shortest paths), weighted PageRank, and sensory-motor betweenness (shortest paths from S to M only). Each batch removes ceil(1% of the remaining types) with the highest current score, ties broken in seeded random order, and all scores are recomputed on the reduced graph before the next batch. Removal continues until at least 50% of types are gone (69 batches on this graph).

Fragility score: normalized AUC = trapezoidal area under the normalized curve against the fraction removed, over the batches up to the first point with at least 50% removed, divided by that fraction range. Lower means more fragile. Random removal is summarized as the mean over 30 trials with a Student-t 95% confidence interval.

Expected sanity check (Phase 4): every targeted strategy has a lower AUC than random removal, for both metrics.

## Null-model test (headline)

For each of the six strategies k, the hypothesis is directional:

> **H_k**: the real graph's flow-capacity AUC under strategy k is **lower** (the real network is more fragile) than the flow-capacity AUC of degree-preserving randomized graphs under the same strategy.

- Null graphs: N = 200 randomizations of the type graph with 10 × |E| in/out-degree-preserving edge swaps each (`igraph.Graph.rewire`, simple graphs), seeds 20260915 + 100000 + i. Out-strength is preserved by reassigning each type's outgoing synapse counts to its new outgoing edges. S and M keep their type labels.
- Each null graph receives exactly the same protocol as the real graph, including 30 random-removal trials whose mean AUC is that graph's random-strategy score.
- Empirical one-sided p-value: p_k = (1 + #{null AUC ≤ real AUC}) / (1 + N).
- Six tests, Bonferroni-corrected threshold α = 0.05 / 6 = 0.0083. With N = 200 the smallest attainable p is 1/201 = 0.0050.
- Secondary (reported, not the headline): the same one-sided test on reachability AUC.
- Also reported: null mean, SD, range and z-score of the real AUC.
- No change of direction, tail, N, metric, AUC range, or protocol after the null distribution is seen, and no rerun with different parameters. A non-significant result is reported as such.

## Critical thresholds

f_c for each strategy: the fraction of types removed at which flow capacity first falls below 50% of its intact value. Primary value: linear interpolation between the last batch at or above 50% and the first batch below. The batch-level fraction (first batch below 50%) is also reported. Runs continue past 50% removal, with the same batch rule and random stream, until flow is below half of intact, so every strategy has a value. Random: f_c per trial, mean and 95% CI over 30 trials.

## Avalanche analysis

Avalanche size for a batch: the number of types still present that have lost every directed path from the remaining sensory types because of that batch (newly unreachable, not counting types removed in the batch).

- Primary distribution: all batches of one run per strategy (the targeted runs and random trial 0), pooled over the first 50% of removals. Sensitivity: all 30 random trials pooled with the targeted runs.
- Zero-size avalanches are excluded from the fit and counted separately.
- Fit: Clauset–Shalizi–Newman discrete power law via the `powerlaw` package, with x_min chosen by minimizing the Kolmogorov–Smirnov distance.
- Goodness of fit: semi-parametric bootstrap with 1,000 synthetic datasets. The power law is plausible if p ≥ 0.1.
- Comparisons: log-likelihood ratio tests (normalized, Vuong) against exponential, lognormal and truncated power law.
- A rejected power law is a valid result.

## Literature validation

Curated set: 14 cell types with published activation and/or silencing evidence for a specific behavior, fixed before scoring:

`DNp01`, `MDN`, `LPLC2`, `LC4`, `DNp07`, `DNp10`, `DNp09`, `pIP10`, `aSP22`, `DNa02`, `EPG`, `PFL3`, `MBON11`, `PPL101`.

Citations are in `results/literature_validation.md`. The motor neuron `MN9` is a positive control and is excluded from the primary test.

- Criticality score: sensory-motor betweenness on the intact graph, the score behind the domain-specific strategy.
- Test: one-sided Mann–Whitney U, alternative that the curated types have higher scores than all other types. Justification: the test is rank-based and makes no distributional assumption, which suits heavy-tailed centrality scores and very unequal group sizes. α = 0.05.
- Secondary scores (reported, same test): drop in flow capacity when the type is removed alone, and global betweenness.
- Sensitivity: `DNp71` in place of `DNp09` (both carry the hemibrain DNp09 label), and `MN9` included.

## Brain versus ventral nerve cord

A type is brain-dominant if more than half of its synapses (pre plus post, summed over its neurons) that fall in the brain (`CentralBrain`, `Optic(L)`, `Optic(R)`) or the ventral nerve cord (`VNC`) are in the brain, and VNC-dominant otherwise. Synapses in the neck connective (`CV`) are ignored. Types with no synapses in either compartment are excluded. Ties (exactly 50%) are excluded.

Each induced subgraph gets its own S and M (the types of S and M that fall in it) and the full protocol with 30 random trials. No direction is hypothesized. The comparison is descriptive, per strategy. For random removal, the 30 trial AUCs of the two subgraphs are compared with a two-sided Welch t-test.

## Synthetic-lethal pairs

- Single-removal impact I(v) = intact flow − flow with v removed, for every type.
- Candidate pool: the 250 types with the highest I(v) / total degree (in plus out edges in the intact graph), ties broken by higher sensory-motor betweenness. Every one of the 31,125 pairs in the pool is evaluated.
- Synergy(u, v) = I(u, v) − I(u) − I(v); pairs are ranked by synergy.

## Bilateral redundancy

- Graph: nodes are (type, hemisphere), with hemisphere from `somaSide` and, for neurons without a CNS soma, `rootSide`. The same 1% input threshold applies.
- Eligible types have both a left and a right node.
- For each eligible type, flow impact is measured on removing the left node, the right node, and both.
- Test 1: one-sided Wilcoxon signed-rank, impact(both) > mean(impact(left), impact(right)).
- Test 2: one-sided Wilcoxon signed-rank, impact(both) > impact(left) + impact(right). This is superadditivity, meaning each side insures the other.
- Both at α = 0.05, over eligible types whose impacts are not all zero.

## Hidden bottleneck

Candidates are types in the bottom half of all types by total degree and by PageRank, and in the top 1% by sensory-motor betweenness, all computed on the intact graph in one script. The most extreme example is the candidate with the highest sensory-motor betweenness.
