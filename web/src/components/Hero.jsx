import { useId, useMemo, useState } from "react";
import Atlas from "./Atlas.jsx";
import { reportUrl } from "../lib/data.js";
import { count, numberWord, percent } from "../lib/format.js";
import "../styles/hero.css";

const LEAD = "out_strength";
const MAX_FRACTION = 0.5;

/** Per-batch state of the removal scale under the lead strategy, computed once from the shared data. */
function buildScale(percolation, atlas) {
  const lead = percolation.strategies[LEAD];
  const replay = atlas.replay[LEAD];
  const fractions = lead.fraction_removed;
  let last = fractions.length - 1;
  while (last > 0 && fractions[last - 1] >= MAX_FRACTION) last -= 1;

  const steps = [];
  for (let i = 0; i <= last; i += 1) {
    const share = lead.flow[i] / percolation.intact_flow;
    const removed = replay.removed_types[i];
    const silenced = replay.silenced_types[i];
    steps.push({
      fraction: fractions[i],
      share,
      halved: share < 0.5,
      valueText: `${percent(fractions[i])} of types removed, flow at ${percent(share)} of intact`,
      mapLabel:
        i === 0
          ? "Map of the male central nervous system with every cell type intact."
          : `Map of the male central nervous system with ${percent(fractions[i])} of cell types removed: ${count(
              removed,
            )} removed and ${count(silenced)} left without sensory input.`,
    });
  }

  const halving = Math.max(0, steps.findIndex((s) => s.halved));
  // Position of the interpolated halving fraction on the batch index scale the slider moves along.
  const a = fractions[halving - 1] ?? 0;
  const b = fractions[halving];
  const mark = halving > 0 ? halving - 1 + (lead.critical_fraction - a) / (b - a || 1) : 0;
  return { steps, last, halving, mark: mark / last };
}

export default function Hero({ meta, percolation, types, atlas }) {
  const scale = useMemo(() => buildScale(percolation, atlas), [percolation, atlas]);
  const [batch, setBatch] = useState(scale.halving);
  const id = useId();
  const lead = percolation.strategies[LEAD];
  const random = percolation.strategies.random;
  const attacks = meta.strategies.filter((s) => percolation.strategies[s.id]).length;
  const step = scale.steps[batch];

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
            routes from sensory to descending and motor cell types after <strong>{percent(lead.critical_fraction)}</strong> of{" "}
            {count(meta.graph.cell_types)} types are gone. In random order it takes{" "}
            <span className="hero-random">{percent(random.critical_fraction)}</span>, averaged over{" "}
            {count(meta.protocol.random_trials)} runs.
          </p>
          <p className="hero-links">
            <a href="#collapse">Watch the {numberWord(attacks)} attacks</a>
            <a href={reportUrl}>Read the report</a>
          </p>
        </div>

        <div className="hero-stage">
          <div className="hero-atlas">
            <Atlas
              tone="field"
              types={types}
              atlas={atlas}
              batch={batch}
              removedAt={types.removed[LEAD]}
              silencedAt={types.silenced[LEAD]}
              ghostAlpha={0}
              label={step.mapLabel}
            />
          </div>

          <div className="hero-scrub">
            <div className="hero-scrub-read">
              <label htmlFor={id}>
                Types removed <span className="hero-scrub-value" aria-hidden="true">{percent(step.fraction)}</span>
              </label>
              <span className="hero-readout" aria-hidden="true">
                Flow capacity <span className={step.halved ? "is-halved" : ""}>{percent(step.share)}</span> of intact
              </span>
            </div>
            <div className="hero-scrub-track" style={{ "--at": batch / scale.last, "--mark": scale.mark }}>
              <span className="hero-scrub-rail" aria-hidden="true" />
              <span className="hero-scrub-mark" aria-hidden="true" />
              <input
                id={id}
                type="range"
                min={0}
                max={scale.last}
                step={1}
                value={batch}
                aria-valuetext={step.valueText}
                onChange={(event) => setBatch(Number(event.target.value))}
              />
            </div>
          </div>

          <p className="hero-caption">
            Each point is a cell type, placed where it makes synapses. Red: removed at this step. Dim: cut off from sensory
            input. The slider steps through removal batches and opens on the first below half, at{" "}
            {percent(scale.steps[scale.halving].fraction)}; the tick marks {percent(lead.critical_fraction)}, where flow
            crosses half.
          </p>
        </div>
      </div>
    </section>
  );
}
