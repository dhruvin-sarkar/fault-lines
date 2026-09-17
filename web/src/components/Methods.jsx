import { Sidenote, TextBlock } from "./ui.jsx";
import { useResult } from "./findings/Finding.jsx";
import { blobUrl, reportUrl, repoUrl } from "../lib/data.js";
import { count, fixed, percent, sentence } from "../lib/format.js";
import "../styles/methods.css";

// Fixed in the pre-registration before any run; the ensemble actually scored is read from nulls.json.
const PREREGISTERED_NULLS = 200;
const SWAPS_PER_EDGE = 10;
const PREREGISTRATION_COMMIT = "0e72491";
const WORKERS_DEFAULT = 4;

const SISTER_PROJECT = "https://github.com/dhruvin-sarkar/ConnectomeLens";
const RESULTS_FOLDER = `${repoUrl}/tree/main/results`;

const SENSORY_SUPERCLASSES = ["cb_sensory", "ol_sensory", "vnc_sensory", "sensory_ascending", "sensory_descending"];
const MOTOR_SUPERCLASSES = ["descending_neuron", "cb_motor", "vnc_motor"];

const MAKE_TARGETS = [
  ["make data", "schema, sensory and motor sets, both graphs"],
  ["make analyze", "removal runs and every analysis built on them"],
  ["make validate", "null model and literature validation"],
  ["make context", "comparison with published thresholds"],
  ["make hero", "neuropil impact scores and the hero image"],
  ["make export", "JSON for this site"],
  ["make web", "build the site"],
  ["make paper", "report PDF"],
  ["make test", "unit tests"],
];

/** Number of batches in the removal schedule: ceil(fraction × remaining) until at least `limit` of n is removed. */
function batchCount(n, fraction, limit) {
  let removed = 0;
  let batches = 0;
  while (removed < limit * n && removed < n) {
    removed += Math.min(Math.max(1, Math.ceil(fraction * (n - removed))), n - removed);
    batches += 1;
  }
  return batches;
}

function joinWords(items) {
  return items.map((item, i) => (
    <span key={i}>
      {i > 0 && (i === items.length - 1 ? " and " : ", ")}
      {item}
    </span>
  ));
}

function Part({ id, title, children }) {
  return (
    <section className="mt-part" id={id} aria-labelledby={`${id}-title`}>
      <h3 className="mt-heading" id={`${id}-title`}>
        {title}
      </h3>
      {children}
    </section>
  );
}

function Table({ number, title, note, children }) {
  return (
    <div className="mt-table">
      <div className="table-wrap mt-scroll" tabIndex={0} role="region" aria-label={`Table ${number}: ${title}`}>
        <table className="data">
          <caption className="mt-table-caption">
            <span className="mt-table-number">Table {number}</span>
            <span className="mt-table-title">{title}.</span>
            {note && <> {note}</>}
          </caption>
          {children}
        </table>
      </div>
    </div>
  );
}

function RowTable({ rows, numeric = false }) {
  return (
    <tbody>
      {rows.map(([name, value]) => (
        <tr key={name}>
          <th scope="row">{name}</th>
          <td className={numeric ? "num" : undefined}>{value}</td>
        </tr>
      ))}
    </tbody>
  );
}

/** State of the null ensemble: loading, missing (still computing), or ready with the size that was scored. */
function nullEnsemble(result, strategies) {
  if (result.missing) return { state: "missing" };
  if (!result.data?.strategies) return { state: "loading" };
  const tests = Object.values(result.data.strategies)
    .map((s) => s.auc_flow)
    .filter(Boolean);
  return {
    state: "ready",
    n: result.data.n_nulls,
    alpha: result.data.alpha ?? 0.05 / strategies,
    tests,
    significant: tests.filter((t) => t.significant).length,
    above: tests.filter((t) => !t.significant && t.real > t.null_mean).length,
  };
}

function NullStatus({ ensemble, alpha }) {
  if (ensemble.state === "loading") return null;
  if (ensemble.state === "missing") {
    return (
      <p>
        <strong>Status.</strong> The null ensemble is still being computed. Its hypotheses and parameters are fixed
        above and in the pre-registration. No randomized graph is reported on this site yet, so no comparison with
        degree-preserving randomizations should be read as tested.
      </p>
    );
  }
  const { n, tests, significant, above } = ensemble;
  const floor = 1 / (n + 1);
  if (n !== PREREGISTERED_NULLS) {
    return (
      <p>
        <strong>Deviation from the plan.</strong> The pre-registration fixed {PREREGISTERED_NULLS} randomized graphs;
        this build reports {count(n)}. The registered test needs the full ensemble, so no strategy is read as significant
        or not significant here. With {count(n)} graphs the smallest attainable p is 1 / {count(n + 1)} ={" "}
        {fixed(floor, 4)}
        {floor >= alpha
          ? ", above the corrected threshold, so no strategy could reach significance at this ensemble size."
          : ", below the corrected threshold."}
      </p>
    );
  }
  return (
    <p>
      <strong>Result.</strong> Against {count(n)} randomized graphs,{" "}
      {significant === 0 ? `none of the ${tests.length} strategies has` : `${significant} of ${tests.length} strategies have`}{" "}
      a flow-capacity AUC significantly below that of their randomizations at the corrected threshold of{" "}
      {fixed(alpha, 4)}
      {significant > 0 && significant < tests.length
        ? `; for the other ${tests.length - significant}, the real graph does not differ significantly in the registered direction`
        : ""}
      {above ? `${significant > 0 && significant < tests.length ? ", and for" : "; for"} ${above} of them its AUC lies above the randomized mean` : ""}
      . Nothing in the test was changed after the randomized scores were seen. The per-strategy distributions and
      p-values are in{" "}
      <a href="#null-model">the null-model finding</a>.
    </p>
  );
}

/** A plain statement of whether the cascade-size fits support a power law, from the exported fit results. */
function cascadeVerdict(avalanches) {
  const { primary, sensitivity, plausible_p: cutoff } = avalanches;
  const lognormalOpen = [primary, sensitivity].every((r) => r.comparisons.lognormal.p_value >= cutoff);
  const both = primary.power_law_plausible && sensitivity.power_law_plausible;
  const neither = !primary.power_law_plausible && !sensitivity.power_law_plausible;
  let head;
  let text;
  if (neither) {
    head = "Cascade sizes are not power-law distributed.";
    text = "The bootstrap test rejects a power law in both the primary data and the pooled random trials.";
  } else if (both && !lognormalOpen) {
    head = "Cascade fits favor a power law.";
    text = "A power law is not rejected in either data set, and the lognormal alternative is distinguishable.";
  } else {
    head = "Inconclusive cascade fits.";
    text = both
      ? "A power law is not rejected in either data set."
      : `A power law is ${primary.power_law_plausible ? "not rejected" : "rejected"} in the primary data but ${
      sensitivity.power_law_plausible ? "not rejected" : "rejected"
    } when all random trials are pooled.`;
  }
  if (lognormalOpen) text += " A lognormal fits as well in both, so scale-free cascades are not established.";
  return { head, text };
}

export default function Methods({ meta }) {
  const g = meta.graph;
  const p = meta.protocol;
  const neurons = meta.neurons;
  const nStrategies = meta.strategies.length;
  const strategyLabels = meta.strategies.map((s) => s.label);
  const batchPercent = Math.round(100 * p.batch_fraction_of_remaining);
  const limit = p.auc_range[1];
  const limitPercent = Math.round(100 * limit);
  const minInput = percent(g.edge_min_input_fraction ?? 0.01, 0);
  const batches = batchCount(g.cell_types, p.batch_fraction_of_remaining, limit);

  const literature = useResult("literature.json").data;
  const pairs = useResult("pairs.json").data;
  const structure = useResult("structure.json").data;
  const avalanches = useResult("avalanches.json").data;
  const edges = useResult("edges.json").data;
  const bilateral = useResult("bilateral.json").data;
  const ensemble = nullEnsemble(useResult("nulls.json"), nStrategies);
  const alpha = ensemble.state === "ready" ? ensemble.alpha : 0.05 / nStrategies;

  const curated = literature?.tests?.primary?.sm_betweenness?.n_curated;
  const cascade = avalanches && cascadeVerdict(avalanches);
  const nullsRun = ensemble.state === "ready" ? count(ensemble.n) : "In progress";

  const graphRows = [
    ["Cell types (nodes)", count(g.cell_types)],
    ["Directed edges", count(g.edges)],
    ["Sensory types, S", count(g.sensory_types)],
    ["Descending and motor types, M", count(g.motor_types)],
    ["Sensory-motor pairs", count(g.sensory_motor_pairs)],
    ["Pairs joined by a directed path", count(g.intact_reachable_pairs)],
    ["Flow capacity (edge-disjoint routes)", count(g.intact_flow)],
  ];
  if (bilateral?.nodes != null) {
    graphRows.push(["Hemisphere-resolved graph, nodes", count(bilateral.nodes)]);
    graphRows.push(["Hemisphere-resolved graph, edges", count(bilateral.edges)]);
  }

  return (
    <section className="section" id="methods" aria-labelledby="methods-title">
      <div className="wrap">
        <header className="section-head mt-head">
          <h2 id="methods-title">Methods and limits</h2>
          <p className="lede">
            How the graph was built, what was measured, how the results were checked, and where the conclusions stop.
            The parameters are the ones the pipeline ran with. The full account, with references, is in the{" "}
            <a href={reportUrl}>report</a>, and the code and every result file are in the{" "}
            <a href={repoUrl}>repository</a>.
          </p>
        </header>

        <Part id="methods-data" title="Data">
          <TextBlock
            notes={
              <>
                <Sidenote title="Cell type">
                  A group of neurons with matching morphology and connectivity, named by the dataset annotators.
                  {neurons &&
                    ` In this dataset a type holds between ${count(neurons.per_type_min)} and ${count(
                      neurons.per_type_max,
                    )} neurons.`}
                </Sidenote>
                <Sidenote title="Superclass">
                  The dataset&apos;s coarse annotation of a neuron&apos;s role and location, such as central brain
                  sensory, descending or nerve cord motor.
                </Sidenote>
              </>
            }
          >
            <p>
              The connectome is the adult male central nervous system of <em>Drosophila melanogaster</em>, dataset{" "}
              {meta.dataset} on neuPrint, reconstructed by the HHMI Janelia FlyEM project and Google Research and
              described by Berg et al. (<em>Cell</em>, 2026).{" "}
              {neurons
                ? `Of its ${count(neurons.total)} neurons, ${count(neurons.typed)} carry a cell type annotation. `
                : ""}
              The typed neurons, in {count(g.cell_types)} cell types, are the material for every analysis here.
            </p>
            <p>
              For each typed neuron the pipeline fetched its type, instance, superclass, class, soma side, nerve root
              side and synapse totals; its presynaptic and postsynaptic counts in each neuropil; and every synaptic
              connection it makes onto another typed neuron. The neuropil surface meshes published with the dataset
              supply the outlines of the atlas. The dataset is released under CC-BY 4.0. The raw neuron and connection
              tables are not stored in the repository; the pipeline fetches them again.
            </p>
          </TextBlock>
        </Part>

        <Part id="methods-graph" title="Graph construction">
          <TextBlock
            notes={
              <Sidenote title={`The ${minInput} input rule`}>
                A connection enters the graph only if it supplies at least {minInput} of the receiving type&apos;s input
                synapses. It discards connections that make up a very small share of a type&apos;s input.
              </Sidenote>
            }
          >
            <p>
              Neurons are aggregated by cell type. Each node is a type, and the weight of the directed edge from type A
              to type B is the total number of synapses from neurons of A onto neurons of B. An edge is kept only if it
              supplies at least {minInput} of B&apos;s input synapses from typed neurons, with synapses between neurons of the
              same type counted in that total; self-loops are then dropped. Each type takes the superclass held by the
              majority of its neurons.
            </p>
            <p>
              A second graph resolves hemispheres. Every type is split into one node per side, taken from the soma side
              where it is recorded and from the nerve root side for sensory neurons whose cell bodies lie outside the
              CNS. The same {minInput} rule applies. This graph is used only for the bilateral redundancy analysis.
            </p>
          </TextBlock>

          <Table number={1} title="The graphs and terminal sets" note="Counts on the intact graphs.">
            <thead>
              <tr>
                <th scope="col">Quantity</th>
                <th scope="col" className="num">
                  Value
                </th>
              </tr>
            </thead>
            <RowTable rows={graphRows} numeric />
          </Table>
        </Part>

        <Part id="methods-sets" title="Sensory and motor sets">
          <TextBlock
            notes={
              <Sidenote title="Why these endpoints">
                Behavior needs a signal to travel from the senses to the neurons that command or drive movement, so
                routes are counted only between these two sets.
              </Sidenote>
            }
          >
            <p>
              The sensory set S contains every type whose majority superclass is one of{" "}
              {joinWords(SENSORY_SUPERCLASSES.map((id) => <span className="id">{id}</span>))}: {count(g.sensory_types)}{" "}
              types. The motor set M contains every type whose majority superclass is one of{" "}
              {joinWords(MOTOR_SUPERCLASSES.map((id) => <span className="id">{id}</span>))}: {count(g.motor_types)}{" "}
              descending and motor types.
            </p>
            <p>
              Superclasses still marked as awaiting confirmation, efferent and endocrine neurons, and ascending neurons
              not annotated as sensory belong to neither set. The sets are disjoint. Every type name in both was
              confirmed in a second query against the live database.
            </p>
          </TextBlock>
        </Part>

        <Part id="methods-measures" title="Measures">
          <TextBlock
            notes={
              <>
                <Sidenote title="Edge-disjoint routes">
                  Paths from S to M that share no connection. Two routes may pass through the same cell type, but not
                  along the same edge.
                </Sidenote>
                <Sidenote title="Max-flow min-cut">
                  The largest number of edge-disjoint routes equals the smallest number of connections that must be cut
                  to separate the two sets.
                </Sidenote>
                <Sidenote title="Normalized AUC">
                  The average share of the intact value that survives across the removal range. A curve that never
                  drops scores 1.
                </Sidenote>
              </>
            }
          >
            <p>
              <strong>Flow capacity</strong> is the primary measure. A super source feeds every type in S and every
              type in M drains into a super sink, both through edges of unbounded capacity, while every edge of the
              graph has capacity one. The maximum flow from source to sink is then the number of edge-disjoint routes
              from S to M: {count(g.intact_flow)} in the intact graph.
            </p>
            <p>
              <strong>Reachability</strong>, the secondary measure, counts the sensory-motor pairs joined by at least
              one directed path. A removed sensory or motor type loses all of its routes and pairs. Both measures are
              divided by their intact values.
            </p>
            <p>
              <strong>Fragility</strong>, or AUC, is the trapezoidal area under a normalized curve against the fraction of types
              removed, up to the first batch at which at least {limitPercent}% are gone, divided by that range. Lower
              values mean a more fragile network.
            </p>
            <p>
              <strong>
                The halving point, <i>f</i>
                <sub>c</sub>,
              </strong>{" "}
              is the fraction of types removed at which flow capacity first falls
              below half its intact value, interpolated linearly between the last batch at or above half and the first
              batch below. Runs continue past {limitPercent}% removal, with the same batch rule and random stream, until
              that happens, so every strategy has a value.
            </p>
          </TextBlock>
        </Part>

        <Part id="methods-protocol" title="Removal protocol">
          <TextBlock
            notes={
              <Sidenote title="Adaptive removal">
                Scores are recomputed after every batch, so a type that becomes central once its neighbors are gone is
                taken next. Rankings fixed on the intact graph are often less damaging.
              </Sidenote>
            }
          >
            <p>
              Types are removed in batches. Degree and PageRank scores are weighted by synapse count. Betweenness counts
              shortest paths by number of hops. Sensory-motor betweenness counts only shortest paths that start in S and
              end in M. Random removal is repeated with independent seeds, and the targeted strategies run once, with
              ties broken in seeded random order.
            </p>
          </TextBlock>

          <Table number={2} title="Removal protocol">
            <RowTable
              rows={[
                ["Strategies", `${sentence(strategyLabels.join(", "))} (${nStrategies})`],
                ["Batch size", `${batchPercent}% of the remaining types, rounded up`],
                ["Recomputation", "All scores, after every batch"],
                ["Ties", "Broken in seeded random order"],
                [
                  "Maximum removed",
                  `${limitPercent}% of types (${batches} batches); longer only to reach the halving point`,
                ],
                ["Random trials", `${p.random_trials}, summarized as the mean with a Student t 95% confidence interval`],
                ["Seed", `${p.seed}; each random trial uses the base seed + 1000 × strategy index + trial number`],
              ]}
            />
          </Table>
        </Part>

        <Part id="methods-validation" title="Validation">
          <TextBlock
            notes={
              <>
                <Sidenote title="Degree-preserving swap">
                  Two edges A to B and C to D become A to D and C to B. Every type keeps its number of inputs and
                  outputs, but who connects to whom is randomized.
                </Sidenote>
                <Sidenote title="Empirical p-value">
                  The share of randomized graphs at least as fragile as the real one, with one added to numerator and
                  denominator so it is never zero.
                </Sidenote>
                <Sidenote title="Bonferroni correction">
                  With {nStrategies} strategies tested, each test uses 0.05 / {nStrategies} = {fixed(alpha, 4)}, which
                  keeps the chance of any false positive at 0.05.
                </Sidenote>
              </>
            }
          >
            <p>
              <strong>Pre-registration.</strong> The hypotheses, tests, thresholds and parameters were written into a{" "}
              <a href={blobUrl("results/preregistration.md")}>pre-registered analysis plan</a> and committed (commit{" "}
              {PREREGISTRATION_COMMIT}) before any percolation run on the real graph or on a randomized one. The order
              can be checked in the repository history, and any deviation is reported in the result it affects.
            </p>
            <p>
              <strong>Degree-preserving null model.</strong> Each randomized graph is made with {SWAPS_PER_EDGE} edge
              swaps per edge on simple graphs, which keep every type&apos;s in-degree and out-degree exactly. Each
              type&apos;s outgoing synapse counts are shuffled across its new outgoing edges, so weighted
              out-degree is preserved as well, and S and M keep their labels. Every randomized graph goes through the identical
              protocol, including {p.random_trials} random trials. For each strategy the hypothesis is one-sided: the
              real graph has a lower flow-capacity AUC than its randomizations. The empirical p-value is (1 + randomized
              graphs with AUC at or below the real AUC) / (N + 1).
            </p>
            <NullStatus ensemble={ensemble} alpha={alpha} />
            <p>
              <strong>Literature validation.</strong>{" "}
              {curated != null ? `${count(curated)} cell types` : "A curated set of cell types"} with published
              activation or silencing evidence for a specific behavior were fixed before any score was computed. A
              one-sided Mann-Whitney U test asks whether they rank higher in sensory-motor betweenness than all other
              types{literature?.alpha != null ? `, at a significance level of ${literature.alpha}` : ""}. The test is
              rank-based because centrality scores are heavy-tailed and the two groups differ greatly in size. Flow lost
              on single removal and global betweenness are secondary scores. The motor neuron{" "}
              <span className="id">MN9</span> is a positive control kept out of the primary test, and{" "}
              <span className="id">DNp71</span> in place of <span className="id">DNp09</span> is a sensitivity check.
            </p>
          </TextBlock>

          <Table number={3} title="Null model" note="Pre-registered values beside the ensemble reported in this build.">
            <thead>
              <tr>
                <th scope="col">Parameter</th>
                <th scope="col">Pre-registered</th>
                <th scope="col">This build</th>
              </tr>
            </thead>
            <tbody>
              {[
                ["Randomized graphs, N", count(PREREGISTERED_NULLS), nullsRun],
                ["Swaps per edge", String(SWAPS_PER_EDGE), String(SWAPS_PER_EDGE)],
                ["Random trials per graph", String(p.random_trials), String(p.random_trials)],
                ["Test", "One-sided, real AUC below null", "As registered"],
                ["Threshold", `0.05 / ${nStrategies} = ${fixed(0.05 / nStrategies, 4)}`, fixed(alpha, 4)],
                [
                  "Smallest attainable p",
                  fixed(1 / (PREREGISTERED_NULLS + 1), 4),
                  ensemble.state === "ready" ? fixed(1 / (ensemble.n + 1), 4) : "In progress",
                ],
              ].map(([name, planned, run]) => (
                <tr key={name}>
                  <th scope="row">{name}</th>
                  <td>{planned}</td>
                  <td>{run}</td>
                </tr>
              ))}
            </tbody>
          </Table>
        </Part>

        <Part id="methods-further" title="Further analyses">
          <TextBlock>
            <ul className="mt-list">
              <li>
                <strong>Single removal.</strong> Every type removed on its own, recording the change in flow capacity and
                reachable pairs.
              </li>
              <li>
                <strong>Synergistic pairs.</strong>{" "}
                {pairs
                  ? `The ${count(pairs.pool_size)} types with the highest single-removal flow impact per connection, and all ${count(
                      pairs.pairs_evaluated,
                    )} pairs among them removed together.`
                  : "A pool of types with the highest single-removal flow impact per connection, and every pair among them removed together."}{" "}
                Synergy is the joint impact minus both single impacts.
              </li>
              <li>
                <strong>Bilateral redundancy.</strong> On the hemisphere-resolved graph, the left node, the right node
                and both nodes of each bilateral type removed, compared with one-sided Wilcoxon signed-rank tests.
              </li>
              <li>
                <strong>Brain and nerve cord.</strong> Each type assigned to the compartment holding more than half of
                its synapses, ignoring the neck connective. Each induced subgraph gets its own S and M and the full
                protocol, and the random-trial AUCs are compared with a two-sided Welch t-test.
              </li>
              <li>
                <strong>Cascades.</strong> After each batch, the types newly cut off from every remaining sensory type.
                Sizes are fitted with a discrete power law by maximum likelihood, following Clauset, Shalizi and Newman,
                with a{" "}
                {avalanches ? `${count(avalanches.primary.bootstrap_sims)}-sample ` : ""}
                bootstrap goodness-of-fit test
                {avalanches ? ` (a power law is plausible when p is at least ${avalanches.plausible_p})` : ""} and
                likelihood-ratio comparisons with exponential, lognormal and truncated power-law alternatives.
              </li>
              <li>
                <strong>Classes and neuropils.</strong>{" "}
                {structure
                  ? `Every superclass of at least ${count(structure.superclass_threshold)} types removed at once and compared with ${count(
                      structure.random_draws,
                    )} random sets of the same size.`
                  : "Every sufficiently large superclass removed at once and compared with random sets of the same size."}{" "}
                The same comparison is made for the types anchored in each neuropil.
              </li>
              <li>
                <strong>Connections.</strong> Edges removed in batches of{" "}
                {edges ? `${percent(edges.batch_fraction_of_edges, 0)} of all ${count(edges.edges)} edges` : "a fixed share of all edges"}
                : strongest first, weakest first, or at random
                {edges ? ` (${count(edges.random_trials)} random orders)` : ""}.
              </li>
            </ul>
          </TextBlock>
        </Part>

        <Part id="methods-limits" title="Limitations">
          <TextBlock
            notes={
              <Sidenote title="What the results support">
                Statements about routes in a static wiring diagram at cell-type resolution. Claims about behavior need
                experiments on the animal.
              </Sidenote>
            }
          >
            <ul className="mt-list">
              <li>
                <strong>Cell types, not neurons.</strong> Merging the neurons of a type into one node hides the
                redundancy between them, and removing a type removes all of its neurons at once, which no single lesion
                or genetic line necessarily does.
              </li>
              <li>
                <strong>The {minInput} input threshold is a choice.</strong> It drops weak connections that may still matter,
                and a different cutoff would give a different edge set. The analysis was run at this threshold only.
              </li>
              <li>
                <strong>Every connection counts once.</strong> Flow capacity gives each edge capacity one, so a
                connection of a few synapses counts as much as one of thousands.
              </li>
              <li>
                <strong>The wiring is static.</strong> There is no activity, no synaptic sign, no neuromodulation and no
                plasticity, and a structural route is not necessarily a functional one.
              </li>
              <li>
                <strong>One animal.</strong> The dataset is a single male, so variation between individuals and between
                sexes cannot be estimated.
              </li>
              <li>
                <strong>Structural, not behavioral.</strong> No neuron was manipulated in this project. A critical type
                is critical to routes in the graph; whether the fly depends on it is untested.
              </li>
              <li>
                <strong>A small curated set.</strong> The{" "}
                {curated != null ? `${count(curated)} literature types are` : "literature types are few and"} not a
                random sample: well-studied neurons were found because they are large, accessible or have striking
                phenotypes.
              </li>
              {cascade && (
                <li>
                  <strong>{cascade.head}</strong> {cascade.text}
                </li>
              )}
              {ensemble.state !== "ready" || ensemble.n !== PREREGISTERED_NULLS ? (
                <li>
                  <strong>An incomplete null ensemble.</strong> Until all {PREREGISTERED_NULLS} randomized graphs are
                  scored, the comparison with degree-preserving randomizations is not the registered test.
                </li>
              ) : (
                <li>
                  <strong>What the null model holds fixed.</strong> The randomized graphs keep every type&apos;s in-degree,
                  out-degree and output synapse total, but not its input synapse total or any structure beyond degrees.
                  A significant difference says the fragility is not explained by the degree sequence alone, not which
                  feature of the wiring explains it; a non-significant one does not show that the wiring adds nothing.
                </li>
              )}
            </ul>
          </TextBlock>
        </Part>

        <Part id="methods-reproduce" title="Reproduce">
          <TextBlock
            notes={
              <Sidenote title="Settings">
                WORKERS sets the number of parallel processes (default {WORKERS_DEFAULT}) and NULLS the number of
                randomized graphs (default {PREREGISTERED_NULLS}).
              </Sidenote>
            }
          >
            <p>
              Python dependencies are pinned in requirements.txt. Running make reproduce performs every step from data to
              report in order; the targets can also be run one at a time. Fetching the data needs network access to
              neuPrint. The null model takes most of the running time, since each randomized graph goes through all{" "}
              {nStrategies} strategies and {p.random_trials} random trials. Every random choice draws from generators
              seeded from {p.seed}, so a rerun reproduces the same removal orders.
            </p>
          </TextBlock>
          <div className="mt-code">
            <pre className="cmd mt-scroll" tabIndex={0} role="region" aria-label="Make targets">
              <code>{MAKE_TARGETS.map(([target, what]) => `${target.padEnd(15)}# ${what}`).join("\n")}</code>
            </pre>
          </div>
        </Part>

        <Part id="methods-report" title="Report and files">
          <TextBlock>
            <p>
              The <a href={reportUrl}>report</a> sets out the full methods, every result with its figure, and the
              references; its <a href={blobUrl("paper/report.md")}>Markdown source</a> sits beside it. The numbers on
              this site are exported from the pipeline&apos;s result files, which are in the{" "}
              <a href={RESULTS_FOLDER}>results folder</a> of the <a href={repoUrl}>repository</a> alongside the code
              that produced them.
            </p>
          </TextBlock>
        </Part>
      </div>
    </section>
  );
}

export function Footer({ meta }) {
  return (
    <footer className="footer mf">
      <div className="wrap">
        <div className="footer-grid">
          <div>
            <p className="footer-title">Fault Lines</p>
            <p>
              Attack tolerance and structural robustness of the complete <em>Drosophila</em> male central nervous system
              connectome.
            </p>
          </div>
          <div>
            <p className="footer-heading">How to cite</p>
            <p>
              Sarkar, D. (2026). Fault Lines: attack tolerance and structural robustness of the complete{" "}
              <em>Drosophila</em> male CNS connectome.{" "}
              <a className="mf-nowrap" href={repoUrl}>
                github.com/dhruvin-sarkar/fault-lines
              </a>
            </p>
            <p className="mf-gap">
              Citation metadata: <a href={blobUrl("CITATION.cff")}>CITATION.cff</a>
            </p>
          </div>
          <div>
            <p className="footer-heading">Data</p>
            <p>
              Male CNS connectome, dataset <span className="mf-nowrap">{meta.dataset}</span>, HHMI Janelia FlyEM and
              Google Research, served through neuPrint. Berg et al. (2026), <em>Cell</em> 189(18).{" "}
              <a href="https://doi.org/10.1016/j.cell.2026.08.015">doi:10.1016/j.cell.2026.08.015</a>. Released under{" "}
              <span className="mf-nowrap">CC-BY 4.0</span>.
            </p>
          </div>
          <nav aria-label="Project links">
            <p className="footer-heading">Links</p>
            <ul className="mf-links">
              <li>
                <a href={repoUrl}>Repository</a>
              </li>
              <li>
                <a href={reportUrl}>Report (PDF)</a>
              </li>
              <li>
                <a href={RESULTS_FOLDER}>Result files</a>
              </li>
              <li>
                <a href={blobUrl("results/preregistration.md")}>Pre-registration</a>
              </li>
              <li>
                <a href={SISTER_PROJECT}>ConnectomeLens</a>
                <span className="mf-aside">Sister project on the same connectome</span>
              </li>
            </ul>
          </nav>
        </div>
        <p className="mf-note">
          Code released under the <a href={blobUrl("LICENSE")}>MIT License</a>. Data exported {meta.exported}.
        </p>
      </div>
    </footer>
  );
}
