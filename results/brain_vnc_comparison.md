# Brain versus ventral nerve cord

## Classification rule

For every cell type, the synapses of all its neurons (presynaptic plus postsynaptic sites) are counted in two compartments of the neuPrint ROI hierarchy: the brain (`CentralBrain`, `Optic(L)`, `Optic(R)`) and the ventral nerve cord (`VNC`). A type is **brain-dominant** if more than half of those synapses are in the brain and **VNC-dominant** if more than half are in the VNC. Synapses in the neck connective (`CV`) are not counted. No type lacks synapses in both compartments or has exactly half in each, so no types are left out. Per-type counts: `results/type_compartments.csv`.

Brain-dominant: 8123 types. VNC-dominant: 3628 types. Each subgraph is the induced subgraph of the whole-CNS type graph (edges keep the whole-CNS 1% input threshold), with its own sensory set S and descending/motor set M: the members of S and M whose types fall in that compartment. Descending and motor types by compartment: brain 498, nerve cord 167.

| | brain-dominant | VNC-dominant |
|---|---|---|
| cell types | 8123 | 3628 |
| edges | 157374 | 66700 |
| sensory types (S) | 182 | 186 |
| descending/motor types (M) | 498 | 167 |
| intact flow capacity | 3765 | 3066 |
| intact reachable S-M pairs | 88644 of 90636 | 29714 of 31062 |

## Fragility

Same protocol as the whole CNS: six adaptive strategies, 1% of remaining types per batch, AUC over the first 50% of removals, 30 random trials. No direction was hypothesized; the comparison is descriptive.

| strategy | brain AUC (flow) | VNC AUC (flow) | brain AUC (reachability) | VNC AUC (reachability) | brain f_c | VNC f_c |
|---|---|---|---|---|---|---|
| random | 0.572 (0.564 to 0.579) | 0.579 (0.573 to 0.586) | 0.583 (0.576 to 0.590) | 0.577 (0.568 to 0.585) | 0.284 | 0.288 |
| weighted out-degree | 0.257 | 0.276 | 0.422 | 0.390 | 0.063 | 0.093 |
| weighted in-degree | 0.504 | 0.228 | 0.556 | 0.365 | 0.253 | 0.066 |
| betweenness | 0.544 | 0.477 | 0.619 | 0.524 | 0.255 | 0.206 |
| PageRank | 0.664 | 0.251 | 0.530 | 0.309 | 0.313 | 0.102 |
| sensory-motor betweenness | 0.151 | 0.363 | 0.195 | 0.324 | 0.059 | 0.126 |

Random removal, brain versus VNC (Welch two-sided t-test over 30 trials each): flow AUC t = -1.54, p = 0.13; reachability AUC t = 1.10, p = 0.27.

Caveat: the two subgraphs differ in size, density and in the composition of S and M, and the targeted strategies are single deterministic runs, so differences in AUC describe these two graphs rather than estimating a population effect.

![Brain and VNC percolation curves](brain_vnc_curves.png)
