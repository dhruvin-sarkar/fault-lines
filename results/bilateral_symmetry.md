# Bilateral redundancy

## Is laterality encoded cleanly?

Yes. neuPrint's male CNS dataset has a dedicated `somaSide` field (L, R or M for midline) for neurons with a cell body in the CNS and a `rootSide` field (L or R) for sensory neurons, which enter through a nerve root. Among 164,506 typed neurons only one has conflicting values (the soma side is used). See `results/schema.md`. No side was inferred from names.

## Procedure

A hemisphere-resolved graph was built from the same neuron-level connectivity, with one node per (type, hemisphere) and the same rule for keeping edges (at least 1% of the target node's input): 23073 nodes (L: 11449, R: 11422, M: 161, unknown: 41) and 490884 edges. Sensory and descending/motor nodes are those whose type is in S or M. Intact flow capacity: 21844.

For each of the 11281 types with both a left and a right node, flow capacity was measured after removing the left node, the right node, and both. Impact = intact flow minus flow after removal. Superadditivity = impact(both) − impact(left) − impact(right). 4449 types have a non-zero impact in at least one of the three removals and enter the tests. Both tests are one-sided Wilcoxon signed-rank tests over the types whose two values differ. A p value below the smallest positive double (about 4.9e-324) is given as p < 1e-323 with its log10 from the normal approximation.

## Results

1. Removing both sides versus the mean of removing one side: W = 9899025 over 4449 types with unequal values, normal approximation z = 57.82, one-sided p < 1e-323, log10 p = -728.2 (significant at 0.05).
2. Removing both sides versus the sum of the two single-side removals (superadditivity): W = 22235.5 over 214 types with unequal values, normal approximation z = 12.66, one-sided p = 5.2e-37 (significant at 0.05).

Of the 4449 informative types, 205 are superadditive (the two sides back each other up), 4235 additive and 9 subadditive (the two sides share a bottleneck, so removing one already removes most of what both carry). 12 types lose no flow when either side is removed alone but do lose flow when both are removed: for these, the contralateral homolog is complete structural insurance.

## Strongest superadditive types

| type | impact, left removed | impact, right removed | impact, both removed | superadditivity |
|---|---|---|---|---|
| `SApp10` | 179 | 162 | 347 | +6 |
| `LgLG1b` | 31 | 40 | 75 | +4 |
| `ORN_DC4` | 21 | 24 | 49 | +4 |
| `SApp` | 324 | 297 | 624 | +3 |
| `LgLG3` | 60 | 59 | 122 | +3 |
| `SNxx04` | 58 | 61 | 122 | +3 |
| `LgLG1a` | 39 | 41 | 83 | +3 |
| `LB1c` | 42 | 32 | 77 | +3 |
| `ANXXX296` | 9 | 9 | 21 | +3 |
| `SNppxx` | 170 | 230 | 402 | +2 |
| `SNta21` | 99 | 106 | 207 | +2 |
| `JO-EV3` | 100 | 86 | 188 | +2 |
| `SNpp60` | 52 | 38 | 92 | +2 |
| `SApp19` | 51 | 30 | 83 | +2 |
| `PhG1c` | 41 | 33 | 76 | +2 |

All types: `results/bilateral_symmetry.csv`.
