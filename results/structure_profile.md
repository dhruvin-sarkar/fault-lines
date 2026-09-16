# Structure the attacks act on

Three descriptive measurements on the intact cell-type graph that frame the removal results. A heavy degree tail is the classic reason targeted removal outperforms random removal; the core decomposition shows how much of the graph is densely interconnected; and removing whole superclasses tests whether routing depends on particular classes of neuron more than on their size.

## Degree tails

Maximum-likelihood power-law fits with x_min chosen by the Kolmogorov-Smirnov criterion (Clauset, Shalizi and Newman 2009). A fitted exponent alone is not evidence of a scale-free network, so the last column reports whether a lognormal, exponential or truncated power law fits better.

| measure | types | median | maximum | exponent | x_min | types in tail | likelihood ratio |
|---|---|---|---|---|---|---|---|
| out-degree (partner types) | 11,112 | 16 | 389 | 2.97 | 27 | 2,975 | favors lognormal, truncated power law |
| in-degree (partner types) | 11,750 | 21 | 46 | 2.90 | 13 | 10,949 | favors exponential, lognormal, truncated power law |
| out-strength (synapses) | 11,112 | 1975 | 2,362,060 | 1.96 | 12616 | 712 | favors truncated power law |

## Core layers

The k-core decomposition of the undirected projection reaches k = 23, and 9,367 of 11,751 cell types sit in that deepest core. Coreness and out-strength rise together (Spearman rho = 0.24, p = 1.1e-157).

## Losing a whole class

Every cell type of one superclass removed at once, for the 13 superclasses with at least 20 types. The null is 200 random sets of the same size, and p is the fraction of those random sets that lose at least as much flow.

| superclass | types | neurons | flow lost | same-size random | p |
|---|---|---|---|---|---|
| descending_neuron | 480 | 1,310 | 66.4% | 8.2% | 0.005 |
| vnc_sensory | 169 | 5,598 | 50.1% | 2.9% | 0.005 |
| cb_intrinsic | 6,605 | 31,280 | 49.3% | 82.4% | 1.000 |
| vnc_intrinsic | 2,777 | 12,943 | 47.0% | 42.9% | 0.040 |
| ascending_neuron | 563 | 1,865 | 34.7% | 9.7% | 0.005 |
| cb_sensory | 158 | 4,756 | 32.5% | 2.7% | 0.005 |
| vnc_motor | 142 | 699 | 16.6% | 2.4% | 0.005 |
| sensory_ascending | 26 | 536 | 13.6% | 0.4% | 0.005 |
| ol_intrinsic | 271 | 89,358 | 0.6% | 4.7% | 1.000 |
| cb_motor | 43 | 106 | 0.4% | 0.7% | 0.776 |
| visual_projection | 346 | 9,202 | 0.4% | 5.9% | 1.000 |
| visual_centrifugal | 108 | 562 | 0.1% | 1.8% | 1.000 |
| vnc_efferent | 27 | 78 | 0.0% | 0.4% | 1.000 |
