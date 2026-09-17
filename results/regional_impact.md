# Regional impact

Each cell type is anchored to the neuropil holding the largest share of its synapses (pre plus post), excluding aggregate compartments and unassigned remainders. For every neuropil, all types anchored in it are removed together and the loss of sensory-to-motor flow capacity is compared with random sets of the same number of types. The table is `regional_impact.csv`, one row per neuropil (91 neuropils).

| column | meaning |
|---|---|
| neuropil | anchor neuropil |
| intact_flow | flow capacity of the intact graph |
| n_types | cell types anchored in the neuropil |
| n_sensory, n_motor | of those, types in the sensory set and in the descending or motor set |
| flow_after | flow capacity with every anchored type removed |
| flow_drop | share of intact flow capacity lost |
| random_mean, random_sd | mean and standard deviation of the share lost over 200 same-size random sets |
| excess_over_random | flow_drop minus random_mean |
| p_value | one-sided empirical p = (1 + k) / (1 + 200), k = random sets losing at least as much flow |

With 200 random sets the smallest attainable p is 1/201 = 0.0050. A Bonferroni correction across the 91 neuropils requires p < 0.05/91 = 0.00055, which no neuropil can reach with this number of draws. 14 neuropils have p < 0.05 and 8 reach the minimum, but these p-values are uncorrected and serve to rank regions, not to establish significance for any one of them. This analysis is exploratory.
