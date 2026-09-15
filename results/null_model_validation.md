# Null-model validation

## Hypothesis (stated before any randomized graph was scored)

For each of the six removal strategies k:

> **H_k**: the real graph's flow-capacity AUC under strategy k is **lower** (the real network is more fragile) than the flow-capacity AUC of degree-preserving randomized graphs under the same strategy.

The test is one-sided in that direction for every strategy. Empirical p-value: p_k = (1 + number of randomized graphs with AUC ≤ real AUC) / (1 + N), with N = 200 randomized graphs. Six tests at a Bonferroni-corrected threshold of α = 0.05 / 6 = 0.0083; the smallest attainable p is 1 / 201 = 0.0050. The same one-sided test on reachability AUC is secondary. The full plan, including every protocol parameter, was committed in `results/preregistration.md` (commit `0e72491`) before any percolation run.
