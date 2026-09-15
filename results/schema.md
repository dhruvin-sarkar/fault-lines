# neuPrint schema: male-cns:v1.0

176422 `:Neuron` nodes, 164506 with a cell type, 11751 distinct types.

## Neuron properties

| property | non-null neurons |
|---|---|
| post | 176422 |
| pre | 176422 |
| downstream | 176422 |
| upstream | 176422 |
| synweight | 176422 |
| bodyId | 176422 |
| roiInfo | 176422 |
| statusLabel | 176243 |
| size | 175313 |
| totalNtPredictions | 174165 |
| predictedNt | 174165 |
| celltypeTotalNtPredictions | 174165 |
| celltypePredictedNt | 174165 |
| consensusNt | 174165 |
| predictedNtConfidence | 173308 |
| status | 172208 |
| superclass | 166700 |
| vfbId | 166686 |
| type | 164506 |
| celltypePredictedNtConfidence | 164445 |
| instance | 161506 |
| somaSide | 150726 |
| group | 147514 |
| flywireType | 143156 |
| somaLocation | 141781 |
| itoleeHl | 37754 |
| supertype | 34096 |
| hemibrainType | 32919 |
| class | 26513 |
| assignedOlHex1 | 23720 |
| assignedOlHex2 | 23720 |
| mancType | 22744 |
| subclass | 21930 |
| somaNeuromere | 21820 |
| trumanHl | 19753 |
| mancBodyid | 18708 |
| rootSide | 17939 |
| mancGroup | 14554 |
| entryNerve | 11835 |
| birthtime | 7904 |
| mancSerial | 5422 |
| fruDsx | 5012 |
| synonyms | 3958 |
| mcnsSerial | 3945 |
| matchingNotes | 3425 |
| dimorphism | 2368 |
| exitNerve | 1005 |
| tosomaLocation | 995 |
| serialMotif | 902 |
| receptorType | 752 |

## Fields used downstream

- cell type: `type`
- superclass (sensory / descending / motor): `superclass`
- sensory modality: `class`
- soma hemisphere: `somaSide`
- nerve-root hemisphere (neurons without a CNS soma): `rootSide`
- hemisphere-suffixed instance name: `instance`
- per-ROI synapse counts: `roiInfo`

## Superclass and class annotations (typed neurons)

| superclass | class | neurons | types |
|---|---|---|---|
| ascending_neuron |  | 1841 | 567 |
| cb_efferent |  | 4 | 1 |
| cb_endocrine |  | 65 | 10 |
| cb_intrinsic |  | 22683 | 5950 |
| cb_intrinsic | Kenyon_Cell | 4064 | 15 |
| cb_intrinsic | CX | 2950 | 292 |
| cb_intrinsic | ALPN | 682 | 180 |
| cb_intrinsic | ALLN | 399 | 79 |
| cb_intrinsic | DAN | 340 | 27 |
| cb_intrinsic | MBON | 97 | 37 |
| cb_intrinsic | SEZPN | 27 | 9 |
| cb_intrinsic | ALIN | 24 | 10 |
| cb_intrinsic | ALON | 14 | 6 |
| cb_motor |  | 106 | 43 |
| cb_sensory | olfactory | 2635 | 53 |
| cb_sensory | mechanosensory | 1705 | 51 |
| cb_sensory | gustatory | 273 | 36 |
| cb_sensory | hygrosensory | 66 | 4 |
| cb_sensory | unknown_sensory | 51 | 10 |
| cb_sensory | thermosensory | 25 | 4 |
| cb_sensory | mechanosensory_tbc | 1 | 1 |
| descending_neuron |  | 1310 | 480 |
| efferent_ascending |  | 8 | 5 |
| efferent_descending |  | 4 | 1 |
| ol_intrinsic |  | 89241 | 259 |
| ol_intrinsic | ol_bilateral | 116 | 12 |
| ol_sensory | visual | 6091 | 10 |
| ol_sensory |  | 7 | 1 |
| sensory_ascending | mechanosensory_proprioceptive | 423 | 16 |
| sensory_ascending | gustatory | 76 | 9 |
| sensory_ascending | unknown_sensory | 28 | 3 |
| sensory_ascending |  | 1 | 1 |
| sensory_ascending_tbc | mechanosensory_proprioceptive | 1 | 1 |
| sensory_descending | unknown_sensory | 12 | 4 |
| visual_centrifugal |  | 562 | 108 |
| visual_projection |  | 9201 | 346 |
| visual_projection_tbc |  | 2 | 2 |
| vnc_efferent |  | 78 | 27 |
| vnc_endocrine |  | 22 | 4 |
| vnc_intrinsic |  | 12967 | 2799 |
| vnc_motor |  | 699 | 142 |
| vnc_sensory | mechanosensory_tactile | 2503 | 56 |
| vnc_sensory | gustatory | 1067 | 15 |
| vnc_sensory | mechanosensory_proprioceptive | 959 | 72 |
| vnc_sensory | unknown_sensory | 958 | 42 |
| vnc_sensory |  | 70 | 3 |
| vnc_sensory | chemosensory | 48 | 2 |

## Laterality encoding (typed neurons)

`somaSide` records the hemisphere of the cell body. Neurons without a soma in the CNS (sensory neurons) carry `rootSide`, the hemisphere of the nerve root they enter through. The `instance` suffix repeats whichever of the two is set.

| somaSide | rootSide | instance_suffix | neurons |
|---|---|---|---|
| R |  | R | 72990 |
| L |  | L | 72805 |
|  | R | R | 6963 |
|  | L | L | 5031 |
|  | R | none | 2305 |
|  | L | none | 2252 |
| L |  | other | 669 |
| R |  | other | 662 |
|  | unknown | other | 411 |
| M |  | M | 357 |
| L | L | L | 24 |
| R | R | R | 12 |
| M |  | R | 9 |
| M |  | L | 9 |
| L |  | M | 2 |
| L | L | none | 2 |
|  |  | L | 1 |
| L | R | L | 1 |
|  |  | R | 1 |

## Top-level ROIs under CNS

- `CV`
- `CentralBrain`
- `Optic(L)`
- `Optic(R)`
- `VNC`

Compartments used for the brain / ventral nerve cord comparison: brain = `CentralBrain`, `Optic(L)`, `Optic(R)`; vnc = `VNC`. `CV` (the neck connective) belongs to neither.
