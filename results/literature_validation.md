# Literature validation

Do cell types that published experiments have shown to be necessary or sufficient for a behavior sit high in the purely structural criticality ranking? The curated list below was compiled from the primary literature, each connectome type name was checked against the male CNS annotations, and the list and test were fixed in `results/preregistration.md` before any score was computed. None of these neurons was tested experimentally in this project.

## Curated cell types

Evidence: S = activating the neurons evokes the behavior; N = silencing or ablating them impairs it.

| type | published name | behavior | evidence | superclass | neurons | sensory-motor betweenness percentile | flow-drop percentile | betweenness percentile | sources |
|---|---|---|---|---|---|---|---|---|---|
| `DNp01` | Giant Fiber | fast looming-evoked escape takeoff | S+N | descending_neuron | 2 | 78.4 | 69.5 | 43.0 | [vonreyn2014]; [lima2005] |
| `MDN` | moonwalker descending neurons | backward walking | S+N | descending_neuron | 4 | 75.1 | 32.3 | 98.9 | [bidaye2014]; [sen2017] |
| `LPLC2` | LPLC2 | looming-evoked escape | S+N | visual_projection | 185 | 92.3 | 32.3 | 94.4 | [klapoetke2017]; [ache2019cb] |
| `LC4` | LC4 | fast looming-evoked escape | S+N | visual_projection | 126 | 79.8 | 32.3 | 93.7 | [vonreyn2017]; [wu2016] |
| `DNp07` | DNp07 | landing | S+N | descending_neuron | 2 | 86.8 | 32.3 | 95.3 | [ache2019nn] |
| `DNp10` | DNp10 | landing | S+N | descending_neuron | 2 | 91.1 | 69.5 | 97.9 | [ache2019nn] |
| `DNp09` | P9 | object-directed walking; pursuit of the female | S+N | descending_neuron | 2 | 47.2 | 32.3 | 83.7 | [bidaye2020] |
| `pIP10` | pIP10 | courtship song | S+N | descending_neuron | 2 | 53.1 | 32.3 | 91.4 | [vonphilipsborn2011]; [lillvis2024] |
| `aSP22` | aSP22 (DNa12) | courtship action sequence | S+N | descending_neuron | 2 | 95.9 | 32.3 | 99.6 | [mckellar2019] |
| `DNa02` | DNa02 | ipsilateral turning while walking | S | descending_neuron | 2 | 85.7 | 32.3 | 98.4 | [yang2024]; [rayshubskiy2025] |
| `EPG` | E-PG compass neurons | menotaxis (holding a heading relative to a sun stimulus) | N | cb_intrinsic | 46 | 9.8 | 32.3 | 99.1 | [giraldo2018] |
| `PFL3` | PFL3 | goal-directed steering | S+N | cb_intrinsic | 24 | 54.2 | 32.3 | 99.9 | [westeinde2024]; [mussellspires2024] |
| `MBON11` | MBON-γ1pedc>α/β | aversive memory expression | N | cb_intrinsic | 2 | 9.8 | 32.3 | 22.3 | [aso2014] |
| `PPL101` | PPL1-γ1pedc | punishment signal for aversive memory | S+N | cb_intrinsic | 2 | 22.6 | 32.3 | 46.0 | [aso2014] |
| `MN9` (positive control) | mn9 motor neuron | proboscis extension | S+N | cb_motor | 2 | 9.8 | 69.5 | 6.0 | [mckellar2020]; [gordon2009] |

Name mapping notes. `MDN` is the connectome type for the moonwalker descending neurons ("DNp50" appears only as a synonym). P9 is scored as `DNp09`, which matches the FlyWire and MANC type of the genetic line used; a second type, `DNp71`, also carries the hemibrain label DNp09 and is tested as a sensitivity check. `aSP22` is the connectome name for the descending neuron published as DNa12. For DNa02, bilateral silencing did not reduce turning, so the evidence is sufficiency only. `MN9` is a motor neuron and thus structurally essential almost by construction; it is kept out of the primary test. Descending neuron nomenclature follows Namiki et al. (2018) [namiki2018].

## Test

One-sided Mann–Whitney U test, alternative that the curated types score higher than all other cell types. A rank-based test is used because centrality scores are heavy-tailed with many ties at zero and the two groups differ in size by three orders of magnitude, so no distributional assumption is appropriate. The AUC (U divided by the product of group sizes) is the probability that a randomly chosen curated type outscores a randomly chosen other type. α = 0.05.

| set | score | n | U | p (one-sided) | AUC | median percentile | result |
|---|---|---|---|---|---|---|---|
| primary (14 types) | sensory-motor betweenness (primary) | 14 | 103535 | 0.045 | 0.630 | 76.8 | significant |
| primary (14 types) | flow capacity lost when removed alone | 14 | 61754 | 0.97 | 0.376 | 32.3 | not significant |
| primary (14 types) | global betweenness | 14 | 136653 | 8.7e-06 | 0.832 | 94.9 | significant |
| with MN9 | sensory-motor betweenness (primary) | 15 | 104667 | 0.1 | 0.595 | 75.1 | not significant |
| with MN9 | flow capacity lost when removed alone | 15 | 69910 | 0.95 | 0.397 | 32.3 | not significant |
| with MN9 | global betweenness | 15 | 137346 | 8.6e-05 | 0.780 | 94.4 | significant |
| DNp71 instead of DNp09 | sensory-motor betweenness (primary) | 14 | 108648 | 0.018 | 0.661 | 79.1 | significant |
| DNp71 instead of DNp09 | flow capacity lost when removed alone | 14 | 61754 | 0.97 | 0.376 | 32.3 | not significant |
| DNp71 instead of DNp09 | global betweenness | 14 | 138303 | 4.8e-06 | 0.842 | 96.5 | significant |

Primary result: the curated types do rank significantly higher in sensory-motor betweenness than other cell types (U = 103535, p = 0.045, AUC = 0.63, median percentile 77).

A positive result shows agreement between a structural ranking and published behavioral experiments for this small, non-random sample of well-studied neurons. Well-studied neurons are not a random draw from the population (they were found because they are large, accessible or have striking phenotypes), so the test cannot show that the ranking identifies essential neurons in general.

![Percentiles of the curated types](literature_rank_plot.png)

## References

- [vonreyn2014] von Reyn CR, Breads P, Peek MY, et al. (2014). A spike-timing mechanism for action selection. Nature Neuroscience 17:962–970. doi:10.1038/nn.3741
- [lima2005] Lima SQ, Miesenböck G (2005). Remote control of behavior through genetically targeted photostimulation of neurons. Cell 121:141–152. doi:10.1016/j.cell.2005.02.004
- [bidaye2014] Bidaye SS, Machacek C, Wu Y, Dickson BJ (2014). Neuronal control of Drosophila walking direction. Science 344:97–101. doi:10.1126/science.1249964
- [sen2017] Sen R, Wu M, Branson K, et al. (2017). Moonwalker descending neurons mediate visually evoked retreat in Drosophila. Current Biology 27:766–771. doi:10.1016/j.cub.2017.02.008
- [klapoetke2017] Klapoetke NC, Nern A, Peek MY, et al. (2017). Ultra-selective looming detection from radial motion opponency. Nature 551:237–241. doi:10.1038/nature24626
- [ache2019cb] Ache JM, Polsky J, Alghailani S, et al. (2019). Neural basis for looming size and velocity encoding in the Drosophila giant fiber escape pathway. Current Biology 29:1073–1081. doi:10.1016/j.cub.2019.01.079
- [vonreyn2017] von Reyn CR, Nern A, Williamson WR, et al. (2017). Feature integration drives probabilistic behavior in the Drosophila escape response. Neuron 94:1190–1204. doi:10.1016/j.neuron.2017.05.036
- [wu2016] Wu M, Nern A, Williamson WR, et al. (2016). Visual projection neurons in the Drosophila lobula link feature detection to distinct behavioral programs. eLife 5:e21022. doi:10.7554/eLife.21022
- [ache2019nn] Ache JM, Namiki S, Lee A, Branson K, Card GM (2019). State-dependent decoupling of sensory and motor circuits underlies behavioral flexibility in Drosophila. Nature Neuroscience 22:1132–1139. doi:10.1038/s41593-019-0413-4
- [bidaye2020] Bidaye SS, Laturney M, Chang AK, et al. (2020). Two brain pathways initiate distinct forward walking programs in Drosophila. Neuron 108:469–485. doi:10.1016/j.neuron.2020.07.032
- [vonphilipsborn2011] von Philipsborn AC, Liu T, Yu JY, et al. (2011). Neuronal control of Drosophila courtship song. Neuron 69:509–522. doi:10.1016/j.neuron.2011.01.011
- [lillvis2024] Lillvis JL, Wang K, Shiozaki HM, et al. (2024). Nested neural circuits generate distinct acoustic signals during Drosophila courtship. Current Biology 34:808–824. doi:10.1016/j.cub.2024.01.015
- [mckellar2019] McKellar CE, Lillvis JL, Bath DE, et al. (2019). Threshold-based ordering of sequential actions during Drosophila courtship. Current Biology 29:426–434. doi:10.1016/j.cub.2018.12.019
- [yang2024] Yang HH, Brezovec BE, Serratosa Capdevila L, et al. (2024). Fine-grained descending control of steering in walking Drosophila. Cell 187:6290–6308. doi:10.1016/j.cell.2024.08.033
- [rayshubskiy2025] Rayshubskiy A, Holtz SL, Bates AS, et al. (2025). Neural circuit mechanisms for steering control in walking Drosophila. eLife 13:RP102230. doi:10.7554/eLife.102230
- [giraldo2018] Giraldo YM, Leitch KJ, Ros IG, et al. (2018). Sun navigation requires compass neurons in Drosophila. Current Biology 28:2845–2852. doi:10.1016/j.cub.2018.07.002
- [westeinde2024] Westeinde EA, Kellogg E, Dawson PM, et al. (2024). Transforming a head direction signal into a goal-oriented steering command. Nature 626:819–826. doi:10.1038/s41586-024-07039-2
- [mussellspires2024] Mussells Pires P, Zhang L, Parache V, Abbott LF, Maimon G (2024). Converting an allocentric goal into an egocentric steering signal. Nature 626:808–818. doi:10.1038/s41586-023-07006-3
- [aso2014] Aso Y, Sitaraman D, Ichinose T, et al. (2014). Mushroom body output neurons encode valence and guide memory-based action selection in Drosophila. eLife 3:e04580. doi:10.7554/eLife.04580
- [mckellar2020] McKellar CE, Siwanowicz I, Dickson BJ, Simpson JH (2020). Controlling motor neurons of every muscle for fly proboscis reaching. eLife 9:e54978. doi:10.7554/eLife.54978
- [gordon2009] Gordon MD, Scott K (2009). Motor control in a Drosophila taste circuit. Neuron 61:373–384. doi:10.1016/j.neuron.2008.12.033
- [namiki2018] Namiki S, Dickinson MH, Wong AM, Korff W, Card GM (2018). The functional organization of descending sensory-motor pathways in Drosophila. eLife 7:e34272. doi:10.7554/eLife.34272
