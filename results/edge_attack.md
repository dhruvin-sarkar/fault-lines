# Removing connections instead of cell types

Flow capacity counts edge-disjoint routes, so in this metric every connection between two cell types counts once whatever its synapse count. Ordering connections by strength therefore tests something specific: whether the connections carrying the most synapses are also the ones carrying the routing.

Connections are removed in batches of 1% of the 243,439 connections, up to half of them, with flow capacity and sensory-motor reachability measured after every batch. The random order is drawn 5 times; the figure shows the first draw.

| order | connections removed when flow halves |
|---|---|
| strongest connections first | 26.8% |
| weakest connections first | not reached by 50% |
| random connections | 47.6% (mean of 5 trials, range 47.2% to 48.0%) |

Removing the strongest connections first halves routing capacity after 26.8% of them are gone, against a mean of 47.6% for random connections (47.2% to 48.0% over 5 random orders); removing the weakest first never halves it within the first 50%. Synapse count and routing capacity are related but not the same: a heavy connection can be redundant, and a thin one can be the only way across.

![Flow capacity under connection removal](edge_attack.png)
