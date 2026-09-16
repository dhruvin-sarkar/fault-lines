# Hidden bottleneck

## Criteria

A type qualifies if, on the intact graph of 11751 types, it ranks in the bottom half by total degree (number of distinct input and output partner types) and in the bottom half by PageRank, yet in the top 1% by sensory-motor betweenness (the number of shortest sensory-to-motor routes, summed over all reachable pairs, that pass through it). Percentiles are mid-rank. All numbers below come from a single run of `pipeline/hidden_bottleneck.py` on the same graph.

4 types qualify (`results/hidden_bottleneck_candidates.csv`):

| type | superclass | degree (percentile) | PageRank percentile | sensory-motor betweenness (percentile) |
|---|---|---|---|---|
| `ALIN7` | cb_intrinsic | 34 (46) | 10 | 1,881 (99.83) |
| `ALON3` | cb_intrinsic | 29 (30) | 36 | 1,558 (99.72) |
| `GNG354` | cb_intrinsic | 32 (40) | 16 | 952 (99.28) |
| `ANXXX264` | ascending_neuron | 34 (46) | 39 | 865 (99.20) |

## The most extreme case: `ALIN7`

| quantity | value |
|---|---|
| superclass | cb_intrinsic |
| neurons in the type | 2 |
| input / output partner types | 19 / 15 (total 34; median over all types 36) |
| degree percentile | 45.7 |
| input / output synapses (in the graph) | 3,699 / 4,753 |
| PageRank percentile | 9.8 |
| sensory-motor betweenness | 1,881.3 (rank 21 of 11751, percentile 99.83) |
| share of sensory-to-motor shortest routes through it | 0.79% of 237,405 reachable pairs |
| reachable pairs lost if it alone is removed | 0 |
| pairs whose shortest route gets longer if it is removed | 849 |
| flow capacity, intact → without it | 10647 → 10638 |

Strongest inputs: `ORN_VA1v` (cb_sensory, 1066 synapses), `ORN_VA1d` (cb_sensory, 761 synapses), `JO-FV` (cb_sensory, 205 synapses), `BM_InOm` (cb_sensory, 170 synapses), `BM_Vib` (cb_sensory, 154 synapses).

Strongest outputs: `il3LN6` (cb_intrinsic, 1396 synapses), `DL3_lPN` (cb_intrinsic, 506 synapses), `VA1d_adPN` (cb_intrinsic, 454 synapses), `AN01A089` (ascending_neuron, 397 synapses), `VA1v_adPN` (cb_intrinsic, 394 synapses).

## Why it matters

Degree and PageRank are the usual shortcuts for spotting important nodes, and by both this type is unremarkable. It stands out only when paths are counted between the specific start and end points that matter for behavior, sensory neurons and descending or motor neurons.

What that does and does not mean: removing this type alone cuts flow capacity by 9 of 10647 and disconnects 0 sensory-motor pairs, while lengthening the shortest route for 849. Concentrating shortest routes is therefore not the same as being indispensable: parallel routes exist, they are just longer. These are structural measurements on the wiring diagram; whether the fly depends on this type has not been tested.
