# Removing connections instead of cell types

Flow capacity counts edge-disjoint routes, so in this metric every connection between two cell types counts once whatever its synapse count. Ordering connections by strength therefore tests something specific: whether the connections carrying the most synapses are also the ones carrying the routing.

Connections are removed in batches of 1% of the 243,439 connections, up to half of them, with flow capacity and sensory-motor reachability measured after every batch.

| order | connections removed when flow halves |
|---|---|
| strongest connections first | 26.8% |
| weakest connections first | not reached by 50% |
| random connections | 47.4% |

Removing the strongest connections first halves routing capacity after 26.8% of them are gone, against 47.4% for random connections; removing the weakest first never halves it within the first 50%. Synapse count and routing capacity are related but not the same: a heavy connection can be redundant, and a thin one can be the only way across.

![Flow capacity under connection removal](edge_attack.png)
