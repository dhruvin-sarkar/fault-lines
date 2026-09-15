# Critical removal thresholds

f_c is the fraction of cell types removed at which sensory-to-motor flow capacity (edge-disjoint S→M paths; 10647 in the intact graph) first falls below 50% of its intact value. The same cutoff is applied to every strategy. The primary value interpolates linearly between the last removal batch at or above the cutoff and the first batch below it; the batch-level value is the fraction removed at that first batch. Random removal: mean over 30 trials with a Student-t 95% confidence interval.

| strategy | f_c (interpolated) | f_c (first batch below) |
|---|---|---|
| weighted out-degree | 0.0411 | 0.0492 |
| betweenness | 0.0904 | 0.0960 |
| sensory-motor betweenness | 0.0961 | 0.1051 |
| weighted in-degree | 0.1387 | 0.1407 |
| PageRank | 0.1875 | 0.1910 |
| random | 0.2832 (95% CI 0.2774–0.2890) | 0.2870 (95% CI 0.2811–0.2929) |

Under weighted out-degree removal, sensory-to-motor flow capacity halves after removing 4.1% of cell types; under random removal it takes 28.3%.

Check: every targeted strategy's f_c lies below the lower bound of the random-removal confidence interval: yes.
