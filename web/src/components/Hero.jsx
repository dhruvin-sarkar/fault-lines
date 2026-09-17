import { useMemo, useState } from "react";
import Atlas from "./Atlas.jsx";
import { Segmented } from "./ui.jsx";
import { blobUrl } from "../lib/data.js";
import { count, percent } from "../lib/format.js";
import "../styles/hero.css";

const LEAD = "out_strength";
const REPORT_PDF = blobUrl("paper/report.pdf");
const NUMBER_WORDS = ["no", "one", "two", "three", "four", "five", "six", "seven", "eight", "nine", "ten"];

export default function Hero({ meta, percolation, types, atlas }) {
  const [view, setView] = useState("halved");
  const intact = percolation.intact_flow;
  const lead = percolation.strategies[LEAD];
  const random = percolation.strategies.random;
  const attacks = meta.strategies.filter((s) => percolation.strategies[s.id]).length;

  const map = useMemo(() => {
    const removed = types.removed[LEAD];
    const silenced = types.silenced[LEAD];
    const batch = lead.flow.findIndex((v) => v < intact / 2);
    // Every type removed up to the break is drawn as removed in that batch, so all of them glow rather than fade.
    const removedAt = removed.map((b) => (b > 0 && b <= batch ? batch : -1));
    let placed = 0;
    let gone = 0;
    let cut = 0;
    for (let i = 0; i < types.x.length; i += 1) {
      if (types.x[i] == null) continue;
      placed += 1;
      if (removedAt[i] > 0) gone += 1;
      else if (silenced[i] >= 0 && silenced[i] <= batch) cut += 1;
    }
    return { batch, removedAt, silenced, placed, gone, cut };
  }, [types, lead, intact]);

  const halved = view === "halved";

  return (
    <section className="hero" aria-labelledby="hero-title">
      <div className="wrap hero-frame">
        <div className="hero-plate-copy">
          <h1 id="hero-title" className="hero-title">
            Fault Lines
          </h1>
          <p className="hero-deck">
            How much of a fly&apos;s nervous system can be lost before its senses no longer reach the neurons that move it?
          </p>
          <p className="hero-answer">
            In the male <i>Drosophila</i> connectome, removing the cell types with the most output synapses first halves the
            routes from sensory to motor neurons after <strong>{percent(lead.critical_fraction)}</strong> of{" "}
            {count(meta.graph.cell_types)} types are gone. In random order it takes{" "}
            <span className="hero-random">{percent(random.critical_fraction)}</span>, averaged over{" "}
            {count(meta.protocol.random_trials)} runs.
          </p>
          <p className="hero-links">
            <a href="#collapse">Watch the {NUMBER_WORDS[attacks] ?? count(attacks)} attacks</a>
            <a href={REPORT_PDF}>Read the report</a>
          </p>
        </div>

        <div className="hero-atlas">
          <div className="hero-layer" aria-hidden={halved}>
            <Atlas
              tone="field"
              types={types}
              atlas={atlas}
              label={`Map of the male central nervous system with ${count(map.placed)} cell types, all intact.`}
            />
          </div>
          <div className={`hero-layer hero-layer-top ${halved ? "is-shown" : ""}`} aria-hidden={!halved}>
            <Atlas
              tone="field"
              types={types}
              atlas={atlas}
              batch={map.batch}
              removedAt={map.removedAt}
              silencedAt={map.silenced}
              label={`Map of the male central nervous system once sensory-to-motor routes have halved: ${count(
                map.gone,
              )} cell types removed and ${count(map.cut)} left without sensory input.`}
            />
          </div>
        </div>

        <div className="hero-toggle">
          <Segmented
            label="Network shown"
            value={view}
            onChange={setView}
            options={[
              { value: "intact", label: "Intact" },
              { value: "halved", label: "Routes halved" },
            ]}
          />
        </div>

        <p className="hero-caption">
          <span className={halved ? "is-hidden" : ""}>
            Each point is a cell type, placed where it makes synapses. All {count(map.placed)} are intact.
          </span>
          <span className={halved ? "" : "is-hidden"}>
            Each point is a cell type, placed where it makes synapses. Red: {count(map.gone)} removed. Dim:{" "}
            {count(map.cut)} with no sensory input.
          </span>
        </p>
      </div>
    </section>
  );
}
