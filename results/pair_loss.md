# Sensory-motor pairs that lose their only path

Removing a single cell type disconnects a sensory-motor pair (s, m) when the pair is reachable in the intact graph and no directed path from s to m avoids the removed type. The intact graph joins 237,405 of the 368 x 665 = 244,720 sensory-motor type pairs.

## Procedure

1. For each of the 368 sensory types s, the dominator tree of the graph rooted at s is computed. A type v other than s and m lies on every path from s to m exactly when v is an ancestor of m in that tree, so the ancestors between m and s are the types whose removal alone disconnects (s, m).
2. Pairs in which the removed type is the sensory source or the motor target are its own pairs: a sensory type loses every motor type it reaches, a motor type every sensory type that reaches it.
3. Own pairs plus other pairs reproduce `pairs_lost` in `results/single_removal_impacts.csv`, computed there by deleting each type and recomputing reachability, for all 11,751 types. For every type with other pairs, the exact set of pairs was also confirmed by deleting it and comparing reachability.

## Result

1,024 types disconnect at least one pair when removed alone. For 356 of them (sensory types) and 665 (descending or motor types) every lost pair is one of their own. 3 types disconnect pairs between two other types, 1,995 such pairs in total. All counts: `results/pair_loss.csv`; the other pairs themselves: `results/pair_loss.json`.

| type (superclass) | set | pairs lost | own pairs | other pairs | sensory types cut | motor types cut |
|---|---|---|---|---|---|---|
| `SNpp17` (vnc_sensory) | sensory | 1,330 | 665 | 665 | 1 | 665 |
| `AMMC029` (cb_intrinsic) | other | 665 | 0 | 665 | 1 | 665 |
| `ANXXX264` (ascending_neuron) | other | 665 | 0 | 665 | 1 | 665 |

## Which pairs

Removing `SNpp17` cuts `SNpp22` off from all 665 motor types it reaches: `CB0429`, `DNa01`, `DNa02`, `DNa03`, `DNa04`, `DNa05`, `DNa06`, `DNa07`, `DNa08`, `DNa09`, and 655 more.

Removing `AMMC029` cuts `JO-EV4` off from all 665 motor types it reaches: `CB0429`, `DNa01`, `DNa02`, `DNa03`, `DNa04`, `DNa05`, `DNa06`, `DNa07`, `DNa08`, `DNa09`, and 655 more.

Removing `ANXXX264` cuts `SNta02` off from all 665 motor types it reaches: `CB0429`, `DNa01`, `DNa02`, `DNa03`, `DNa04`, `DNa05`, `DNa06`, `DNa07`, `DNa08`, `DNa09`, and 655 more.

Motor types are listed descending neurons first, then central brain motor and nerve cord motor types, each by name.

Reachability asks only whether some path exists, so a pair counts as lost only when its last route is gone. These are structural statements about the type-level wiring diagram, not predictions of behavior.
