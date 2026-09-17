# Synthetic-lethal cell-type pairs

In genetics, two genes are synthetic lethal when losing either alone is tolerated but losing both is not. The structural analogue here: two cell types whose joint removal cuts sensory-to-motor flow capacity by more than the sum of what each removal does alone, because each provides the other's detour.

## Procedure

1. Single-removal impact I(v) = intact flow (10647 edge-disjoint S→M paths) minus flow with type v removed, for all 11751 types.
2. Candidate pool: the 250 types with the largest I(v) per incident edge (in plus out edges of the intact graph), a heuristic for types that carry a lot of flow for how connected they are; ties broken by higher sensory-motor betweenness. 250 pool members have I(v) > 0. Pool with scores: `results/synthetic_lethal_pool.csv`.
3. Every pair in the pool, 31125 of 31125 (all), removed together: joint impact I(u, v) = intact flow − flow without both; synergy = I(u, v) − I(u) − I(v).

585 pairs have positive synergy, 39 negative (their individual impacts overlap), the rest zero. All pairs: `results/synthetic_lethal_pairs.csv`.

## Top 25 pairs by synergy

Every row can be checked from its own numbers: joint impact = intact flow − flow after; synergy = joint impact − I(a) − I(b).

| type a (superclass) | type b (superclass) | I(a) | I(b) | flow after removing both | joint impact | synergy |
|---|---|---|---|---|---|---|
| `SNppxx` (vnc_sensory) | `SNta29` (vnc_sensory) | 216 | 155 | 10264 | 383 | +12 |
| `SNppxx` (vnc_sensory) | `SNta37` (vnc_sensory) | 216 | 107 | 10315 | 332 | +9 |
| `SNppxx` (vnc_sensory) | `SNpp52` (vnc_sensory) | 216 | 85 | 10337 | 310 | +9 |
| `SNta29` (vnc_sensory) | `SNta20` (vnc_sensory) | 155 | 82 | 10401 | 246 | +9 |
| `SNppxx` (vnc_sensory) | `SNta38` (vnc_sensory) | 216 | 85 | 10338 | 309 | +8 |
| `SNta29` (vnc_sensory) | `SNta37` (vnc_sensory) | 155 | 107 | 10377 | 270 | +8 |
| `SNta29` (vnc_sensory) | `SNta30` (vnc_sensory) | 155 | 53 | 10431 | 216 | +8 |
| `SNppxx` (vnc_sensory) | `SNta20` (vnc_sensory) | 216 | 82 | 10342 | 305 | +7 |
| `SNppxx` (vnc_sensory) | `SNpp51` (vnc_sensory) | 216 | 47 | 10377 | 270 | +7 |
| `SApp` (sensory_ascending) | `SApp10` (sensory_ascending) | 310 | 166 | 10165 | 482 | +6 |
| `SNppxx` (vnc_sensory) | `SNxx33` (vnc_sensory) | 216 | 116 | 10309 | 338 | +6 |
| `SNppxx` (vnc_sensory) | `SNpp45` (vnc_sensory) | 216 | 64 | 10361 | 286 | +6 |
| `SNpp50` (vnc_sensory) | `SNta29` (vnc_sensory) | 59 | 155 | 10427 | 220 | +6 |
| `SNta37` (vnc_sensory) | `SNta20` (vnc_sensory) | 107 | 82 | 10452 | 195 | +6 |
| `SApp` (sensory_ascending) | `SApp06,SApp15` (sensory_ascending) | 310 | 97 | 10235 | 412 | +5 |
| `SApp` (sensory_ascending) | `SNpp35` (vnc_sensory) | 310 | 19 | 10313 | 334 | +5 |
| `SNppxx` (vnc_sensory) | `SNta21` (vnc_sensory) | 216 | 103 | 10323 | 324 | +5 |
| `SApp08` (sensory_ascending) | `SApp10` (sensory_ascending) | 112 | 166 | 10364 | 283 | +5 |
| `SNppxx` (vnc_sensory) | `SNpp50` (vnc_sensory) | 216 | 59 | 10367 | 280 | +5 |
| `SNxx33` (vnc_sensory) | `SNta29` (vnc_sensory) | 116 | 155 | 10371 | 276 | +5 |
| `SNppxx` (vnc_sensory) | `SNta30` (vnc_sensory) | 216 | 53 | 10373 | 274 | +5 |
| `SNppxx` (vnc_sensory) | `SNta25` (vnc_sensory) | 216 | 52 | 10374 | 273 | +5 |
| `SNppxx` (vnc_sensory) | `SNta28` (vnc_sensory) | 216 | 46 | 10380 | 267 | +5 |
| `SNpp45` (vnc_sensory) | `SNta29` (vnc_sensory) | 64 | 155 | 10423 | 224 | +5 |
| `SNta29` (vnc_sensory) | `SNta28` (vnc_sensory) | 155 | 46 | 10441 | 206 | +5 |

Flow capacity counts edge-disjoint paths, so a positive synergy means the two types sit on alternative routes that can substitute for each other. It is a structural statement about the wiring diagram, not a prediction of what silencing both types would do to a fly.
