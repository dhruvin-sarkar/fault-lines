# Structural avalanche analysis

## What is measured

After each adaptive removal batch, the avalanche size is the number of cell types still in the graph that have just lost every directed path from the remaining sensory types, not counting the types removed in that batch. A large avalanche means one batch of removals silently disconnected many other types.

This asks whether *structural failure cascades* in the wiring diagram are scale-free. It is a different question from the finding that *neural activity* propagates in power-law-distributed avalanches in cortical tissue (Beggs and Plenz, 2003): no activity is simulated here, and a power law in one says nothing about the other.

## Method

Discrete power-law fit by maximum likelihood with x_min chosen to minimize the Kolmogorov–Smirnov distance (Clauset, Shalizi and Newman, 2009), using the `powerlaw` package (Alstott, Bullmore and Plenz, 2014). Goodness of fit by semi-parametric bootstrap; the power law is treated as plausible when p ≥ 0.1. Alternatives compared by Vuong's normalized log-likelihood ratio. No log-log regression is used.

Primary data: every batch within the first 50% of removals for one run per strategy (the five targeted runs and random trial 0). Sensitivity: the five targeted runs plus all 30 random trials.

## Results

### Primary (one run per strategy)

414 removal batches; 185 had no avalanche (size 0) and are excluded from the fit; 229 positive sizes, largest 6046.

| quantity | value |
|---|---|
| exponent α | 2.011 ± 0.120 |
| x_min (KS-minimizing) | 8 |
| sizes ≥ x_min | 71 |
| KS distance D | 0.0607 |
| bootstrap goodness-of-fit p (1000 synthetic sets) | 0.202 |

Likelihood-ratio tests (normalized log-likelihood ratio R; R > 0 favors the power law, R < 0 the alternative; p tests whether the sign of R is significant):

| alternative | R | p |
|---|---|---|
| exponential | +2.628 | 0.009 |
| lognormal | -1.007 | 0.314 |
| truncated power law | +0.002 | 0.997 |

The power law is not rejected by the bootstrap test (p = 0.202; plausible if p ≥ 0.1). The power law is significantly favored over the exponential.

### Sensitivity (targeted runs plus all 30 random trials)

2415 removal batches; 2073 had no avalanche (size 0) and are excluded from the fit; 342 positive sizes, largest 6046.

| quantity | value |
|---|---|
| exponent α | 1.872 ± 0.078 |
| x_min (KS-minimizing) | 4 |
| sizes ≥ x_min | 125 |
| KS distance D | 0.0595 |
| bootstrap goodness-of-fit p (1000 synthetic sets) | 0.036 |

Likelihood-ratio tests (normalized log-likelihood ratio R; R > 0 favors the power law, R < 0 the alternative; p tests whether the sign of R is significant):

| alternative | R | p |
|---|---|---|
| exponential | +2.411 | 0.016 |
| lognormal | -0.316 | 0.752 |
| truncated power law | -0.328 | 0.894 |

The power law is rejected by the bootstrap test (p = 0.036; plausible if p ≥ 0.1). The power law is significantly favored over the exponential.

## Conclusion

The pre-registered primary data set does not reject a power law (p = 0.202), but the larger sensitivity set rejects a power law (p = 0.036), so the result does not survive a change in which runs are pooled. In neither set can a lognormal be distinguished from the power law, so the data do not establish scale-free cascades. The tail is also dominated by a few very large events: the single largest avalanche (6046 types) comes from the sm_betweenness run.

## Per strategy (primary runs)

| strategy | batches | zero-size batches | largest avalanche | types cut off in total |
|---|---|---|---|---|
| random | 69 | 67 | 1 | 2 |
| out_strength | 69 | 2 | 41 | 831 |
| in_strength | 69 | 12 | 27 | 289 |
| betweenness | 69 | 27 | 182 | 523 |
| pagerank | 69 | 49 | 8 | 35 |
| sm_betweenness | 69 | 28 | 6046 | 6919 |

![Avalanche size distribution](avalanche_ccdf.png)
