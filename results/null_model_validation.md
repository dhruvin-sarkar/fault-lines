# Null-model validation

## Hypothesis (stated before any randomized graph was scored)

For each of the six removal strategies k:

> **H_k**: the real graph's flow-capacity AUC under strategy k is **lower** (the real network is more fragile) than the flow-capacity AUC of degree-preserving randomized graphs under the same strategy.

The test is one-sided in that direction for every strategy. Empirical p-value: p_k = (1 + number of randomized graphs with AUC ≤ real AUC) / (1 + N), with N = 200 randomized graphs. Six tests at a Bonferroni-corrected threshold of α = 0.05 / 6 = 0.0083; the smallest attainable p is 1 / 201 = 0.0050. The same one-sided test on reachability AUC is secondary. The full plan, including every protocol parameter, was committed in `results/preregistration.md` (commit `0e72491`) before any percolation run.

## Procedure

1. 200 randomized versions of the cell-type graph (11751 types, 243439 edges), each with 10 × |E| in/out-degree-preserving edge swaps (`igraph.Graph.rewire`, simple graphs). Every type keeps its exact in-degree and out-degree; each type's outgoing synapse counts are shuffled across its new outgoing edges, preserving out-strength. Sensory and motor types keep their labels.
2. On every randomized graph, the identical removal protocol as on the real graph: six adaptive strategies, 1% of remaining types per batch with scores recomputed after each batch, up to 50% removed, 30 random-removal trials averaged into that graph's random-strategy AUC. Curves are normalized by the randomized graph's own intact flow capacity and reachable pairs.
3. One-sided empirical p-value per strategy, in the direction stated above.

## Result: flow-capacity AUC (primary)

| strategy | real AUC | randomized mean ± sd | randomized range | randomized ≤ real | z | p | significant at 0.0083 |
|---|---|---|---|---|---|---|---|
| random | 0.5699 | 0.5751 ± 0.0005 | 0.5740 to 0.5763 | 0 / 200 | -11.5 | 0.0050 | yes |
| weighted out-degree | 0.1971 | 0.2023 ± 0.0014 | 0.1978 to 0.2070 | 0 / 200 | -3.6 | 0.0050 | yes |
| weighted in-degree | 0.3696 | 0.5930 ± 0.0099 | 0.5591 to 0.6213 | 0 / 200 | -22.7 | 0.0050 | yes |
| betweenness | 0.3151 | 0.3451 ± 0.0034 | 0.3338 to 0.3536 | 0 / 200 | -8.9 | 0.0050 | yes |
| PageRank | 0.4406 | 0.5902 ± 0.0080 | 0.5663 to 0.6074 | 0 / 200 | -18.7 | 0.0050 | yes |
| sensory-motor betweenness | 0.2326 | 0.3525 ± 0.0118 | 0.3219 to 0.3947 | 0 / 200 | -10.1 | 0.0050 | yes |

## Result: reachability AUC (secondary)

| strategy | real AUC | randomized mean ± sd | randomized range | randomized ≤ real | z | p | below 0.0083 |
|---|---|---|---|---|---|---|---|
| random | 0.5860 | 0.5859 ± 0.0003 | 0.5850 to 0.5867 | 115 / 200 | 0.3 | 0.5771 | no |
| weighted out-degree | 0.3495 | 0.3572 ± 0.0028 | 0.3486 to 0.3654 | 1 / 200 | -2.7 | 0.0100 | no |
| weighted in-degree | 0.4840 | 0.6385 ± 0.0138 | 0.5991 to 0.6711 | 0 / 200 | -11.2 | 0.0050 | yes |
| betweenness | 0.2674 | 0.4997 ± 0.0063 | 0.4821 to 0.5141 | 0 / 200 | -36.6 | 0.0050 | yes |
| PageRank | 0.4612 | 0.6404 ± 0.0119 | 0.6078 to 0.6770 | 0 / 200 | -15.1 | 0.0050 | yes |
| sensory-motor betweenness | 0.2555 | 0.3709 ± 0.0089 | 0.3455 to 0.3994 | 0 / 200 | -12.9 | 0.0050 | yes |

## Reading

- **random**: real 0.570 vs randomized 0.575 ± 0.000 (p = 0.0050). H is supported: the real graph is significantly more fragile than its degree-preserving randomizations.
- **weighted out-degree**: real 0.197 vs randomized 0.202 ± 0.001 (p = 0.0050). H is supported: the real graph is significantly more fragile than its degree-preserving randomizations.
- **weighted in-degree**: real 0.370 vs randomized 0.593 ± 0.010 (p = 0.0050). H is supported: the real graph is significantly more fragile than its degree-preserving randomizations.
- **betweenness**: real 0.315 vs randomized 0.345 ± 0.003 (p = 0.0050). H is supported: the real graph is significantly more fragile than its degree-preserving randomizations.
- **PageRank**: real 0.441 vs randomized 0.590 ± 0.008 (p = 0.0050). H is supported: the real graph is significantly more fragile than its degree-preserving randomizations.
- **sensory-motor betweenness**: real 0.233 vs randomized 0.353 ± 0.012 (p = 0.0050). H is supported: the real graph is significantly more fragile than its degree-preserving randomizations.

![Null distributions](null_distribution.png)
