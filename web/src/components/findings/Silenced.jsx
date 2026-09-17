import { useEffect, useMemo, useState } from "react";
import Atlas, { atlasAspect } from "../Atlas.jsx";
import { ChartFrame, Row, Tooltip, XAxis, YAxis } from "../Chart.jsx";
import { Figure, Segmented, Sidenote, Slider, TextBlock } from "../ui.jsx";
import { Finding } from "./Finding.jsx";
import { LineLabels, inkColor, labelRoom, sentence, xTicks } from "./marks.jsx";
import { count, indexAt, percent, strategyLabel } from "../../lib/format.js";
import { usePlayhead, useReducedMotion, useWidth } from "../../lib/hooks.js";
import { line, linear, niceTicks } from "../../lib/scales.js";
import "../../styles/findings-b.css";

const MAPPED = ["sm_betweenness", "out_strength", "random"];
const LOG_TICKS = [0, 10, 100, 1000, 10000];
const TIP_HALF = 130;
const SCALES = [
  { value: "linear", label: "Linear" },
  { value: "log", label: "Logarithmic" },
];

const color = inkColor;
const dash = (id) => (id === "random" ? "6 5" : undefined);

/** Count scale that keeps zero on the axis: linear, or log10(1 + v). */
function countScale(max, height, logarithmic) {
  if (!logarithmic) {
    const ticks = niceTicks([0, max], 4);
    const step = ticks[1] - ticks[0];
    const top = ticks.at(-1) >= max ? ticks.at(-1) : ticks.at(-1) + step;
    const s = linear([0, top], [height, 0]);
    s.ticks = niceTicks([0, top], 4);
    return s;
  }
  const top = LOG_TICKS.find((t) => t >= max) ?? LOG_TICKS.at(-1);
  const span = Math.log10(1 + top);
  const s = (v) => height - (Math.log10(1 + Math.max(0, v)) / span) * height;
  s.domain = [0, top];
  s.ticks = LOG_TICKS.filter((t) => t <= top);
  return s;
}

export default function Silenced({ meta, percolation, types, atlas }) {
  const replay = atlas.replay;
  const strategies = useMemo(() => meta.strategies.filter((s) => replay[s.id]), [meta, replay]);
  const labels = Object.fromEntries(strategies.map((s) => [s.id, strategyLabel(s.id)]));
  const fractions = replay[strategies[0].id].fraction_removed;
  const last = fractions.length - 1;

  const story = useMemo(() => {
    const remainingAt = (id, b) => meta.graph.cell_types - replay[id].removed_types[b];
    const worst = strategies.reduce(
      (a, s) => (replay[s.id].silenced_types[last] > replay[a].silenced_types[last] ? s.id : a),
      strategies[0].id,
    );
    const series = replay[worst].silenced_types;
    let jump = 1;
    for (let b = 1; b <= last; b += 1) if (series[b] - series[b - 1] > series[jump] - series[jump - 1]) jump = b;
    const fc = percolation.strategies[worst]?.critical_fraction;
    return {
      worst,
      share: series[last] / remainingAt(worst, last),
      atEnd: series[last],
      remaining: remainingAt(worst, last),
      fc,
      atFc: fc == null ? null : series[indexAt(fractions, fc)],
      jump,
      jumpSize: series[jump] - series[jump - 1],
      batchSize: replay[worst].removed_types[jump] - replay[worst].removed_types[jump - 1],
      randomEnd: replay.random?.silenced_types[last],
    };
  }, [meta, percolation, replay, strategies, fractions, last]);

  const { step, setStep, playing, setPlaying } = usePlayhead(fractions.length, useReducedMotion() ? 320 : 110);
  useEffect(() => setStep(last), [last, setStep]);

  const pick = (b) => {
    setPlaying(false);
    setStep(b);
  };

  const toggle = () => {
    if (playing) {
      setPlaying(false);
      return;
    }
    if (step >= last) setStep(0);
    setPlaying(true);
  };

  const endShare = percent(fractions[last], 0);
  const trials = meta.protocol?.random_trials;

  return (
    <Finding
      id="silenced"
      title="Cut off, still present"
      stat={percent(story.share)}
      statLabel={`of the cell types still present have no path from any sensory type once ${labels[story.worst]} has removed ${endShare} of types`}
    >
      <TextBlock
        notes={
          <>
            <Sidenote title="Cut off">
              A remaining cell type with no directed path from any of the {count(meta.graph.sensory_types)} sensory
              types. Removed types are not counted.
            </Sidenote>
            <Sidenote title="One run each">
              Counts and maps follow one run per strategy
              {trials != null ? `; for random removal, the first of ${count(trials)} trials` : ""}.
            </Sidenote>
          </>
        }
      >
        <p>
          A cell type can stay in the graph and still be unreachable. If no directed path leads to it from any sensory
          type, nothing sensed can reach it through the wiring. After every removal batch we count those types among
          the ones not yet removed.
        </p>
        <p>
          Under {labels[story.worst]}, flow capacity halves at {percent(story.fc)} removed while{" "}
          {story.atFc === 0 ? "no remaining type is yet cut off" : `${count(story.atFc)} remaining types are cut off`}.
          The loss stays hidden until {percent(fractions[story.jump])} removed, when one batch of{" "}
          {count(story.batchSize)} removals cuts off {count(story.jumpSize)} types at once. Once {endShare} of types
          are gone, {count(story.atEnd)} of the {count(story.remaining)} still present have no sensory input
          {story.randomEnd != null &&
            `; under random removal, ${count(story.randomEnd)} ${story.randomEnd === 1 ? "does" : "do"}`}
          .
        </p>
      </TextBlock>

      <SilencedChart strategies={strategies} replay={replay} fractions={fractions} step={step} onPick={pick} />

      <Figure
        variant="field"
        title="Where the cut-off types are"
        controls={
          <button type="button" className="btn fb-play" aria-pressed={playing} onClick={toggle}>
            <svg viewBox="0 0 14 14" aria-hidden="true">
              {playing ? <path d="M3 2h3v10H3zM8 2h3v10H8z" fill="currentColor" /> : <path d="M3 1.5v11l9.5-5.5z" fill="currentColor" />}
            </svg>
            {playing ? "Pause" : step >= last ? "Replay removal" : "Play removal"}
          </button>
        }
        caption={
          <>
            One point per cell type, placed in the neuropil that holds most of its synapses. Each map follows one
            strategy up to the level set below. Types still reached from sensory input glow; a removed type flares red
            in the batch that takes it and then goes dark; a type still present but unreachable from every sensory
            type dims to grey. Play the removal batch by batch, drag the slider, or click the chart above to set the
            level.
          </>
        }
      >
        <Maps types={types} atlas={atlas} labels={labels} step={step} fractions={fractions} replay={replay} />
        <div className="fb-replay">
          <Slider
            label="Types removed"
            min={0}
            max={last}
            value={step}
            onChange={pick}
            format={(b) => percent(fractions[b])}
            valueText={(b) => `${percent(fractions[b])} of cell types removed`}
          />
          <ul className="legend fb-key" aria-label="Map key">
            <li>
              <span className="fb-square" style={{ background: "var(--field-live)" }} />
              Reached from sensory input
            </li>
            <li>
              <span className="fb-square" style={{ background: "var(--field-ink-3)" }} />
              Cut off
            </li>
            <li>
              <span className="fb-square" style={{ background: "var(--signal-glow)" }} />
              Removed in this batch
            </li>
          </ul>
        </div>
      </Figure>

      <details className="more">
        <summary>Counts as a table</summary>
        <div className="table-wrap">
          <table className="data">
            <thead>
              <tr>
                <th className="num">Removed</th>
                <th className="num">Types left</th>
                {strategies.map((s) => (
                  <th key={s.id} className="num">
                    {strategyLabel(s.id)}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {fractions.map((f, b) =>
                b % 5 === 0 || b === last ? (
                  <tr key={f}>
                    <td className="num">{percent(f)}</td>
                    <td className="num">{count(meta.graph.cell_types - replay[strategies[0].id].removed_types[b])}</td>
                    {strategies.map((s) => (
                      <td key={s.id} className="num">
                        {count(replay[s.id].silenced_types[b])}
                      </td>
                    ))}
                  </tr>
                ) : null,
              )}
            </tbody>
          </table>
        </div>
      </details>
    </Finding>
  );
}

function SilencedChart({ strategies, replay, fractions, step, onPick }) {
  const [scale, setScale] = useState("linear");
  const [hover, setHover] = useState(null);
  const [sizer, width] = useWidth();
  const narrow = width < 620;
  const logarithmic = scale === "log";
  const margin = { top: 32, right: labelRoom(strategies.map((s) => strategyLabel(s.id)), narrow), bottom: 46, left: 54 };
  const max = Math.max(...strategies.map((s) => Math.max(...replay[s.id].silenced_types)));
  const last = fractions.length - 1;
  const xMax = Math.max(0.5, fractions[last]);
  const quiet = strategies.filter((s) => Math.max(...replay[s.id].silenced_types) < max / 10).length;

  return (
    <Figure
      title="Types cut off from all sensory input as removal proceeds"
      controls={<Segmented label="Vertical scale" options={SCALES} value={scale} onChange={setScale} />}
      caption={
        <>
          Each line counts the remaining types that no sensory type can reach, after each batch of removals. The
          logarithmic scale separates the {count(quiet)} strategies that stay low. Hover to read every strategy at one
          level; click to move the maps below to it. The dashed vertical line marks the level the maps show.
        </>
      }
    >
      <div ref={sizer} className="fb-hit" onClick={() => hover != null && onPick(hover)}>
        <ChartFrame
          height={narrow ? 340 : 400}
          margin={margin}
          label={`Line chart of remaining cell types cut off from all sensory input against the share of types removed, ${strategies.length} removal strategies`}
          onPointer={(x, _y, inner) => setHover(indexAt(fractions, Math.max(0, Math.min(xMax, (x / inner.width) * xMax))))}
          onLeave={() => setHover(null)}
          overlay={({ width: full, height, margin: m }) => {
            if (hover == null) return null;
            const w = full - m.left - m.right;
            const x = m.left + (fractions[hover] / xMax) * w;
            const flip = x > m.left + w / 2;
            const left = Math.max(TIP_HALF, Math.min(full - TIP_HALF, x + (flip ? -TIP_HALF - 12 : TIP_HALF + 12)));
            const rows = strategies.map((s) => ({ ...s, v: replay[s.id].silenced_types[hover] })).sort((a, b) => b.v - a.v);
            return (
              <Tooltip x={left} y={m.top + height * 0.75} width={full}>
                <strong className="fb-tip-head">{percent(fractions[hover])} of types removed</strong>
                {rows.map((r) => (
                  <Row key={r.id} label={sentence(strategyLabel(r.id))} value={count(r.v)} color={color(r.id)} />
                ))}
                <span className="fb-tip-note">Click to show this level on the maps</span>
              </Tooltip>
            );
          }}
        >
          {(inner) => {
            const xs = linear([0, xMax], [0, inner.width]);
            const ys = countScale(max, inner.height, logarithmic);
            const marker = xs(fractions[step]);
            return (
              <>
                <YAxis
                  scale={ys}
                  ticks={ys.ticks}
                  width={inner.width}
                  format={count}
                  title={logarithmic ? "Types cut off, logarithmic" : "Types cut off"}
                />
                <XAxis
                  scale={xs}
                  ticks={xTicks(xMax, narrow)}
                  height={inner.height}
                  width={inner.width}
                  format={(v) => percent(v, 0)}
                  title="Cell types removed"
                />
                <line className="fb-marker" x1={marker} x2={marker} y1={0} y2={inner.height} />
                {strategies.map((s) => {
                  const d = line(replay[s.id].silenced_types.map((v, i) => [xs(fractions[i]), ys(v)]));
                  return (
                    <path
                      key={s.id}
                      className="fb-series"
                      d={d}
                      style={{ d: `path("${d}")`, stroke: color(s.id), strokeDasharray: dash(s.id) }}
                    />
                  );
                })}
                {hover != null && (
                  <g>
                    <line className="fb-crosshair" x1={xs(fractions[hover])} x2={xs(fractions[hover])} y1={0} y2={inner.height} />
                    {strategies.map((s) => (
                      <circle
                        key={s.id}
                        className="fb-point"
                        cx={xs(fractions[hover])}
                        cy={ys(replay[s.id].silenced_types[hover])}
                        r={4}
                        style={{ fill: color(s.id) }}
                      />
                    ))}
                  </g>
                )}
                <LineLabels
                  width={inner.width}
                  height={inner.height}
                  narrow={narrow}
                  items={strategies.map((s) => ({
                    id: s.id,
                    label: sentence(strategyLabel(s.id)),
                    y: ys(replay[s.id].silenced_types[last]),
                    stroke: color(s.id),
                    dash: dash(s.id),
                  }))}
                />
              </>
            );
          }}
        </ChartFrame>
      </div>
    </Figure>
  );
}

function Maps({ types, atlas, labels, step, fractions, replay }) {
  const aspect = useMemo(() => atlasAspect(types, atlas), [types, atlas]);
  const [pointer, setPointer] = useState(null);
  const [grid, gridWidth] = useWidth();
  const shown = MAPPED.filter((id) => replay[id]);
  // Points keep their minimum pixel size on small maps, so additive glow is thinned to avoid saturating.
  const mapWidth = gridWidth / Math.max(1, shown.length);
  const alpha = mapWidth < 160 ? 0.14 : mapWidth < 280 ? 0.24 : undefined;

  return (
    <>
      <div ref={grid} className="fb-maps">
        {shown.map((id) => (
          <figure key={id} className="fb-map">
            <figcaption className="fb-map-head">
              <strong>{sentence(labels[id])}</strong>
              <span className="fb-map-count">
                {count(replay[id].silenced_types[step])}
                <small>cut off</small>
              </span>
            </figcaption>
            <div className="fb-map-canvas" style={{ aspectRatio: aspect }}>
              <Atlas
                types={types}
                atlas={atlas}
                tone="field"
                pointAlpha={alpha}
                batch={step}
                removedAt={types.removed[id]}
                silencedAt={types.silenced[id]}
                onType={(index) => setPointer(index == null ? null : { id, index })}
                label={`Cell types under ${labels[id]} at ${percent(fractions[step])} removed: ${count(replay[id].silenced_types[step])} cut off from sensory input`}
              />
            </div>
          </figure>
        ))}
      </div>
      <p className="fb-readout">
        {pointer ? (
          <TypeState types={types} fractions={fractions} step={step} label={labels[pointer.id]} {...pointer} />
        ) : (
          "Point at a cell type to see its state."
        )}
      </p>
    </>
  );
}

function TypeState({ types, fractions, step, label, id, index }) {
  const removed = types.removed[id][index];
  const silenced = types.silenced[id][index];
  let state = "still reached from sensory input";
  if (removed >= 1 && removed <= step) state = `removed at ${percent(fractions[removed])}`;
  else if (silenced >= 0 && silenced <= step) state = `cut off since ${percent(fractions[silenced])} removed`;
  return (
    <>
      <span className="id">{types.name[index]}</span> under {label}: {state}
    </>
  );
}
