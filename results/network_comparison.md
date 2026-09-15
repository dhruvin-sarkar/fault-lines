# Comparison with published network fragility

## The numbers are not measured the same way

The threshold here is the fraction of cell types removed when the maximum sensory-to-motor flow (the number of edge-disjoint directed paths from sensory to descending and motor types) falls below half its intact value, with scores recalculated after every 1% of removals. The classic studies instead track the size of the largest connected cluster, mostly on undirected graphs and often with rankings fixed on the intact network, and call the network broken when that cluster disintegrates or halves. A source-to-sink capacity is limited by the narrowest cut between two designated sets, so it can halve long before a giant component disappears. The values below therefore sit side by side as context, not as the same quantity measured on different networks. The closest analogue is the power-grid study, which also measures connectivity from a source set (generators) to a sink set (distribution substations).

## This connectome

| strategy | fraction of cell types removed when flow halves |
|---|---|
| weighted out-degree | 0.041 |
| betweenness | 0.090 |
| sensory-motor betweenness | 0.096 |
| weighted in-degree | 0.139 |
| PageRank | 0.187 |
| random | 0.283 (95% CI 0.277–0.289) |

## Published thresholds (values printed in the primary source)

| network | removal | breakdown criterion | fraction removed | source, location |
|---|---|---|---|---|
| Internet, autonomous-system level (6,209 nodes) | targeted, by degree | largest cluster fragments | ≈0.03 | Albert 2000, main text, Internet paragraph |
| World Wide Web sample (325,729 pages) | targeted, by out-degree | largest cluster fragments | 0.067 | Albert 2000, main text and Fig. 3 caption |
| Scale-free model (N = 10,000) | targeted, by degree | largest cluster fragments | ≈0.18 | Albert 2000, main text, fragmentation paragraph |
| Exponential random model (N = 10,000) | targeted, by degree | largest cluster fragments | ≈0.28 | Albert 2000, main text, fragmentation paragraph |
| North American power grid (14,099 substations) | targeted, by load | up to 60% loss of generator-to-substation connectivity | 0.04 | Albert 2004, main text |
| Human functional brain network (90 regions) | targeted, by degree | largest cluster halved | ≈0.4 | Achard 2006, Results and Discussion |
| Scale-free comparison network | targeted, by degree | largest cluster halved | 0.2 | Achard 2006, Results |
| Human voxel-wise functional network (15,996 voxels) | targeted, recalculated centrality | first dramatic giant-component reduction | ≈0.4 | Joyce 2013, Results and Discussion |
| Scale-free network, Internet-like exponent (N > 10⁶) | random | spanning cluster vanishes | >0.99 | Cohen 2000, abstract |

![Critical removal fractions](network_comparison.png)

## Studies without a comparable printed threshold

- Cohen 2001: Removing the highest-degree sites destroys scale-free networks after a few percent of sites. The critical fraction is shown only as a curve against the degree exponent (about 0.06 at exponent 2.5 with minimum degree 1, read from Fig. 1); no value is printed for the Internet.
- Jeong 2001: In the yeast protein interaction network, removing the most connected proteins rapidly increases the network diameter while random removal does not; no removal fraction is given. The printed numbers concern lethality: about 62% of proteins with more than 15 links are essential, against about 21% of those with 5 or fewer.
- Holme 2002: Degree and betweenness rankings recalculated during removal are often more harmful than rankings fixed on the intact network. Results are curves and values after 1% removal, not thresholds.
- Schneider 2011: Introduces the robustness index R, the area under the largest-component curve during recalculated-degree attack; the fragility score here is the same construction applied to flow capacity.

## Reading

Under the most damaging strategy (weighted out-degree), sensory-to-motor capacity halves after 4.1% of cell types are removed. That is the range reported for engineered hub-dominated networks under degree or load attack (the autonomous-system Internet at about 3%, the Web sample at 6.7%, the power grid losing up to 60% of connectivity at 4%) and well below the roughly 40% reported for human functional brain networks. Random removal needs 28.3% of cell types. Because the criterion, the resolution (cell types rather than neurons or regions), edge direction and recalculation all differ, the comparison supports only a qualitative statement: sensory-to-motor routing in this connectome is concentrated enough that targeted removal of a few percent of cell types halves it.

## References

- Albert, R., Jeong, H. & Barabási, A.-L. (2000). Error and attack tolerance of complex networks. Nature 406, 378–382. https://doi.org/10.1038/35019019
- Cohen, R., Erez, K., ben-Avraham, D. & Havlin, S. (2000). Resilience of the Internet to random breakdowns. Physical Review Letters 85, 4626–4628. https://doi.org/10.1103/PhysRevLett.85.4626
- Cohen, R., Erez, K., ben-Avraham, D. & Havlin, S. (2001). Breakdown of the Internet under intentional attack. Physical Review Letters 86, 3682–3685. https://doi.org/10.1103/PhysRevLett.86.3682
- Jeong, H., Mason, S. P., Barabási, A.-L. & Oltvai, Z. N. (2001). Lethality and centrality in protein networks. Nature 411, 41–42. https://doi.org/10.1038/35075138
- Holme, P., Kim, B. J., Yoon, C. N. & Han, S. K. (2002). Attack vulnerability of complex networks. Physical Review E 65, 056109. https://doi.org/10.1103/PhysRevE.65.056109
- Albert, R., Albert, I. & Nakarado, G. L. (2004). Structural vulnerability of the North American power grid. Physical Review E 69, 025103(R). https://doi.org/10.1103/PhysRevE.69.025103
- Achard, S., Salvador, R., Whitcher, B., Suckling, J. & Bullmore, E. (2006). A resilient, low-frequency, small-world human brain functional network with highly connected association cortical hubs. Journal of Neuroscience 26, 63–72. https://doi.org/10.1523/JNEUROSCI.3874-05.2006
- Schneider, C. M., Moreira, A. A., Andrade, J. S., Havlin, S. & Herrmann, H. J. (2011). Mitigation of malicious attacks on networks. PNAS 108, 3838–3841. https://doi.org/10.1073/pnas.1009440108
- Joyce, K. E., Hayasaka, S. & Laurienti, P. J. (2013). The human functional brain network demonstrates structural and dynamical resilience to targeted attack. PLoS Computational Biology 9, e1002885. https://doi.org/10.1371/journal.pcbi.1002885
