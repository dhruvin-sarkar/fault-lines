import { Fragment } from "react";
import Thresholds from "./findings/Thresholds.jsx";
import NullModel from "./findings/NullModel.jsx";
import Literature from "./findings/Literature.jsx";
import Regions from "./findings/Regions.jsx";
import Classes from "./findings/Classes.jsx";
import Silenced from "./findings/Silenced.jsx";
import Connections from "./findings/Connections.jsx";
import Compartments from "./findings/Compartments.jsx";
import Avalanches from "./findings/Avalanches.jsx";
import Structure from "./findings/Structure.jsx";
import Pairs from "./findings/Pairs.jsx";
import Bilateral from "./findings/Bilateral.jsx";
import Bottleneck from "./findings/Bottleneck.jsx";
import SectionBoundary from "./SectionBoundary.jsx";
import { HeadingLevel, Sidenote } from "./ui.jsx";
import { useResult } from "./findings/Finding.jsx";
import { count, pClause, percent, superclassName } from "../lib/format.js";
import "../styles/findings-index.css";

const PARTS = [
  {
    title: "How fragile is it, and is that real?",
    chapters: [
      ["thresholds", Thresholds],
      ["null-model", NullModel],
      ["literature", Literature],
    ],
  },
  {
    title: "Where does the damage land?",
    chapters: [
      ["regions", Regions],
      ["classes", Classes],
      ["silenced", Silenced],
      ["connections", Connections],
      ["brain-nerve-cord", Compartments],
      ["avalanches", Avalanches],
    ],
  },
  {
    title: "What does the structure explain?",
    chapters: [
      ["structure", Structure],
      ["pairs", Pairs],
      ["bilateral", Bilateral],
      ["bottleneck", Bottleneck],
    ],
  },
];

const NEUROPIL_NAMES = {
  GNG: "the gnathal ganglia",
  SAD: "the saddle",
  VES: "the vest",
  ANm: "the abdominal neuromeres",
  IntTct: "the intermediate tectulum",
  LegNp: "a leg neuropil",
};

const neuropilName = (name) => NEUROPIL_NAMES[name.split("(")[0]] ?? name;

const ranked = (items, key) => [...items].sort((a, b) => b[key] - a[key])[0];

function fastestStrategy(fractions, ids) {
  return ids.filter((id) => id !== "random" && fractions[id] != null).reduce((a, id) => (fractions[id] < fractions[a] ? id : a));
}

/** Each key result as { id, value, title, note }, in page order; results not exported are left out. */
function useKeyResults({ meta, percolation }) {
  const regions = useResult("regions.json").data;
  const structure = useResult("structure.json").data;
  const edges = useResult("edges.json").data;
  const compartments = useResult("compartments.json").data;
  const avalanches = useResult("avalanches.json").data;
  const pairs = useResult("pairs.json").data;
  const bottleneck = useResult("bottleneck.json").data;
  const nulls = useResult("nulls.json").data;

  const labels = Object.fromEntries(meta.strategies.map((s) => [s.id, s.label]));
  const ids = meta.strategies.map((s) => s.id);
  const rows = [];

  const strategies = percolation.strategies;
  const fractions = Object.fromEntries(ids.map((id) => [id, strategies[id]?.critical_fraction]));
  const first = fastestStrategy(fractions, ids);
  const random = strategies.random;
  const opening = { first, fc: fractions[first], random: random.critical_fraction };
  rows.push({
    id: "thresholds",
    value: percent(opening.fc),
    title: `of cell types removed halves sensory-to-motor flow, ranked by ${labels[first]}`,
    note: random.critical_fraction_ci95
      ? `Random removal needs ${percent(random.critical_fraction)} (95% CI ${percent(random.critical_fraction_ci95[0])} to ${percent(random.critical_fraction_ci95[1])}).`
      : `Random removal needs ${percent(random.critical_fraction)}.`,
  });

  // A significance count is a key result only for the ensemble size fixed in advance.
  if (nulls?.strategies && nulls.n_nulls === nulls.n_preregistered) {
    const tests = ids.filter((id) => nulls.strategies[id]).map((id) => nulls.strategies[id].auc_flow);
    const yes = tests.filter((t) => t.verdict === "more_fragile").length;
    rows.push({
      id: "null-model",
      value: `${yes} of ${tests.length}`,
      title: `removal orders under which the real graph is significantly more fragile than ${count(nulls.n_nulls)} degree-preserving randomizations`,
      note: `One-sided tests at a Bonferroni threshold of ${nulls.alpha.toFixed(4)}; the smallest attainable p is ${nulls.p_floor.toFixed(4)}.`,
    });
  }

  let region = null;
  if (regions?.length) {
    region = ranked(regions, "flow_drop");
    rows.push({
      id: "regions",
      value: percent(region.flow_drop),
      title: `of flow lost when the ${count(region.types)} types anchored in ${neuropilName(region.neuropil)} are removed`,
      note: `Random sets of the same size lose ${percent(region.random_mean)}.`,
    });
  }

  let superclass = null;
  if (structure?.superclass_impact?.length) {
    superclass = ranked(structure.superclass_impact, "excess_over_random");
    rows.push({
      id: "classes",
      value: percent(superclass.flow_drop),
      title: `of flow lost when all ${count(superclass.types)} ${superclassName(superclass.superclass)} types are removed`,
      note: `Random sets of the same size lose ${percent(superclass.random_mean)}.`,
    });
  }

  if (edges?.orders?.strongest) {
    const { strongest, weakest, random: shuffled } = edges.orders;
    rows.push({
      id: "connections",
      value: percent(strongest.critical_fraction),
      title: "of connections removed, strongest first, halves flow",
      note: [
        shuffled && `Random connections take ${percent(shuffled.critical_fraction)}.`,
        weakest && weakest.critical_fraction == null && "Removing the weakest first never halves it within half the connections.",
      ]
        .filter(Boolean)
        .join(" "),
    });
  }

  if (compartments?.compartments?.brain && compartments.compartments.vnc) {
    const { brain, vnc } = compartments.compartments;
    const brainFirst = fastestStrategy(brain.f_c, ids);
    const cordFirst = fastestStrategy(vnc.f_c, ids);
    rows.push({
      id: "brain-nerve-cord",
      value: percent(brain.f_c[brainFirst]),
      title: `of brain types removed halves flow within the brain, ranked by ${labels[brainFirst]}`,
      note: `The nerve cord halves at ${percent(vnc.f_c[cordFirst])}, ranked by ${labels[cordFirst]}. At random: brain ${percent(brain.f_c.random)}, nerve cord ${percent(vnc.f_c.random)}.`,
    });
  }

  if (avalanches?.primary) {
    const { primary, sensitivity, per_strategy: perStrategy = {} } = avalanches;
    const source = Object.entries(perStrategy).find(([, s]) => s.max_size === primary.max_size)?.[0];
    let note = null;
    if (sensitivity && primary.power_law_plausible !== sensitivity.power_law_plausible) {
      const [kept, rejected] = primary.power_law_plausible ? [primary, sensitivity] : [sensitivity, primary];
      note = `A power law is not rejected for cascade sizes in one pooling of runs (${pClause(kept.bootstrap_p)}) and is rejected in the other (${pClause(rejected.bootstrap_p)}).`;
    } else if (sensitivity) {
      note = primary.power_law_plausible
        ? "A power law is not rejected for cascade sizes in either pooling of runs."
        : "A power law is rejected for cascade sizes in both poolings of runs.";
    }
    rows.push({
      id: "avalanches",
      value: count(primary.max_size),
      title: `types cut off from all sensory input by one removal batch${source ? `, under ${labels[source] ?? source}` : ""}`,
      note,
    });
  }

  if (structure?.types_in_deepest_core) {
    const strength = structure.degree_tails?.find((t) => t.measure.startsWith("out-strength"));
    rows.push({
      id: "structure",
      value: percent(structure.types_in_deepest_core / structure.types),
      title: `of cell types share the deepest core of the graph, k = ${structure.max_coreness}`,
      note: strength
        ? `Output synapses per type run from a median of ${count(strength.median)} to a maximum of ${count(strength.max)}.`
        : null,
    });
  }

  if (pairs?.pairs_with_positive_synergy != null) {
    rows.push({
      id: "pairs",
      value: count(pairs.pairs_with_positive_synergy),
      title: "pairs of cell types cost more flow together than their two losses added up",
      note: `${count(pairs.pairs_evaluated)} pairs were tested; the largest excess is ${count(pairs.max_synergy)} routes.`,
    });
  }

  if (bottleneck?.n_candidates != null) {
    const ex = bottleneck.example;
    const pct = 100 - bottleneck.criteria.sm_betweenness_percentile_at_least;
    rows.push({
      id: "bottleneck",
      value: count(bottleneck.n_candidates),
      title: `${bottleneck.n_candidates === 1 ? "type" : "types"} in the bottom half by partners and PageRank ${bottleneck.n_candidates === 1 ? "sits" : "sit"} in the top ${pct}% by sensory-motor betweenness`,
      note: ex
        ? `${ex.cell_type} lies on ${percent(ex.share_of_shortest_routes, 2)} of shortest routes; removing it costs ${count(ex.intact_flow - ex.flow_after_removal)} of ${count(ex.intact_flow)} routes.`
        : null,
    });
  }

  return { rows, opening, region, superclass, labels };
}

function Lede({ opening, region, superclass, labels }) {
  const byOutStrength = opening.first === "out_strength";
  return (
    <p className="lede fi-lede">
      Removing <strong>{percent(opening.fc)}</strong> of cell types, the ones{" "}
      {byOutStrength ? "that send the most synapses" : `ranked highest by ${labels[opening.first]}`}, halves the
      connectome&apos;s capacity to route from sensory to descending and motor cell types. Removed at random, it
      takes{" "}
      <strong>{percent(opening.random)}</strong>.
      {region && superclass && (
        <>
          {" "}
          The loss is uneven: the {count(region.types)} types anchored in {neuropilName(region.neuropil)} take{" "}
          {percent(region.flow_drop)} of that capacity with them, and the {count(superclass.types)}{" "}
          {superclassName(superclass.superclass)} types take {percent(superclass.flow_drop)}, well beyond random sets
          of the same size.
        </>
      )}
    </p>
  );
}

export default function Findings(props) {
  const { rows, ...lede } = useKeyResults(props);
  const { meta } = props;

  return (
    <section className="section" id="findings" aria-labelledby="findings-title">
      <div className="wrap">
        <header>
          <h2 id="findings-title" className="chapter-title fi-title">
            Losing a few percent of cell types halves the routing
          </h2>
          <div className="text-grid">
            <Lede {...lede} />
            <div className="notes">
              {meta.graph && (
                <Sidenote title="Reading the results">
                  Each result below links to its chapter. Shares of flow are of the {count(meta.graph.intact_flow)}{" "}
                  routes the intact graph can run at once.
                </Sidenote>
              )}
            </div>
          </div>
          <nav aria-label="Key results">
            <ul className="key-results fi-keys">
              {rows.map((row) => (
                <li key={row.id}>
                  <a href={`#${row.id}`}>
                    <span className="key-value">{row.value}</span>
                    <span className="fi-key-text">
                      <span className="key-title">{row.title}</span>
                      {row.note && <span className="fi-key-note">{row.note}</span>}
                    </span>
                  </a>
                </li>
              ))}
            </ul>
          </nav>
        </header>

        {PARTS.map((part) => (
          <Fragment key={part.title}>
            <h3 className="fi-part">{part.title}</h3>
            <HeadingLevel level={4}>
              {part.chapters.map(([id, Chapter]) => (
                <SectionBoundary key={id} id={id} as="finding">
                  <Chapter {...props} />
                </SectionBoundary>
              ))}
            </HeadingLevel>
          </Fragment>
        ))}
      </div>
    </section>
  );
}
