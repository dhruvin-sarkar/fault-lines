import { memo, useEffect, useId, useLayoutEffect, useMemo, useRef, useState } from "react";
import Atlas, { atlasAspect } from "./Atlas.jsx";
import { ChartFrame, Row, Tooltip, XAxis, YAxis, spreadLabels } from "./Chart.jsx";
import { Figure, Segmented, Sidenote, Slider, TextBlock } from "./ui.jsx";
import { useInView, useReducedMotion, useTokens, useWidth } from "../lib/hooks.js";
import { count, fixed, percent, valueAt } from "../lib/format.js";
import { band, line, linear } from "../lib/scales.js";
import "../styles/collapse.css";

const STEP_MS = 120;
const CALM_STEP_MS = 600;
const ROW = 64;
const MAP_TOKENS = ["field-ink-2"];

const METRICS = {
  flow: {
    label: "Flow capacity",
    noun: "flow capacity",
    series: "flow",
    low: "flow_low",
    high: "flow_high",
    auc: "auc_flow",
  },
  pairs: {
    label: "Reachable pairs",
    noun: "reachable sensory-to-motor pairs",
    series: "reachable_pairs",
    low: "pairs_low",
    high: "pairs_high",
    auc: "auc_reachability",
  },
};

const WIDE_MARGIN = { top: 32, right: 176, bottom: 46, left: 54 };
const NARROW_MARGIN = { top: 32, right: 12, bottom: 42, left: 40 };
const NUMBER_WORDS = ["none", "one", "two", "three", "four", "five", "six", "seven", "eight", "nine", "ten"];

const capitalize = (text) => text.charAt(0).toUpperCase() + text.slice(1);
const numberWord = (n) => NUMBER_WORDS[n] ?? String(n);

/** Removal fraction where a normalized series first drops below one half, interpolated; null if it never does. */
function halfCrossing(fractions, values) {
  for (let i = 1; i < values.length; i += 1) {
    if (values[i] < 0.5) {
      const a = values[i - 1];
      const b = values[i];
      return fractions[i - 1] + ((a - 0.5) / (a - b || 1)) * (fractions[i] - fractions[i - 1]);
    }
  }
  return null;
}

function resample(fractions, source, values, scale) {
  if (source.length === fractions.length && source.every((f, i) => Math.abs(f - fractions[i]) < 1e-9)) {
    return values.map((v) => v / scale);
  }
  return fractions.map((f) => valueAt(source, values, f) / scale);
}

/** Sentence on how many strategies have halved the measure, with the strategy count taken from the data. */
function halvedSentence(halved, total, noun) {
  const totalWord = numberWord(total);
  if (halved === 0) return `None of the ${totalWord} attacks has halved ${noun}.`;
  if (halved === total) return `All ${totalWord} attacks have halved ${noun}.`;
  const word = capitalize(numberWord(halved));
  return `${word} of the ${totalWord} attacks ${halved === 1 ? "has" : "have"} halved ${noun}.`;
}

/** Integer removal step that advances on a timer; motion between steps is left to CSS transitions. */
function useRace(last, initial, stepMs) {
  const [batch, setBatch] = useState(initial);
  const [playing, setPlaying] = useState(false);
  useEffect(() => {
    if (!playing) return undefined;
    if (batch >= last) {
      setPlaying(false);
      return undefined;
    }
    const timer = setTimeout(() => setBatch((b) => Math.min(last, b + 1)), stepMs);
    return () => clearTimeout(timer);
  }, [playing, batch, last, stepMs]);
  return { batch, setBatch, playing, setPlaying };
}

function Icon({ kind }) {
  if (kind === "pause") {
    return (
      <svg viewBox="0 0 14 14" aria-hidden="true">
        <path d="M3 2h3v10H3zM8 2h3v10H8z" fill="currentColor" />
      </svg>
    );
  }
  if (kind === "replay") {
    return (
      <svg viewBox="0 0 14 14" aria-hidden="true">
        <path d="M11.5 7A4.5 4.5 0 1 1 7 2.5h2" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" />
        <path d="M8.2 0.4 10.6 2.5 8.2 4.6z" fill="currentColor" />
      </svg>
    );
  }
  return (
    <svg viewBox="0 0 14 14" aria-hidden="true">
      <path d="M3.5 1.8 12 7l-8.5 5.2z" fill="currentColor" />
    </svg>
  );
}

export default function Collapse({ meta, percolation, types, atlas }) {
  const reduced = useReducedMotion();
  const strategies = meta.strategies;
  const uid = useId().replace(/[^a-zA-Z0-9_-]/g, "");
  const clipId = `race-clip-${uid}`;
  const focusLabelId = `race-focus-${uid}`;

  const model = useMemo(() => {
    const fractions = percolation.strategies[strategies[0].id].fraction_removed;
    const build = (key) => {
      const m = METRICS[key];
      const intact = key === "flow" ? percolation.intact_flow : percolation.intact_reachable_pairs;
      return strategies.map(({ id, label }) => {
        const s = percolation.strategies[id];
        const values = resample(fractions, s.fraction_removed, s[m.series], intact);
        const trials = s.band && {
          low: resample(fractions, s.band.fraction_removed, s.band[m.low], intact),
          high: resample(fractions, s.band.fraction_removed, s.band[m.high], intact),
        };
        return {
          id,
          label,
          name: capitalize(label),
          color: `var(--glow-${id})`,
          values,
          auc: s[m.auc],
          halvedAt: key === "flow" ? s.critical_fraction : halfCrossing(fractions, values),
          ci: key === "flow" ? s.critical_fraction_ci95 : null,
          trials,
        };
      });
    };
    return { fractions, flow: build("flow"), pairs: build("pairs") };
  }, [percolation, strategies]);

  const { fractions } = model;
  const last = fractions.length - 1;
  const xTicks = useMemo(() => {
    const ticks = [];
    for (let k = 0; k * 0.1 <= fractions[last] + 1e-9; k += 1) ticks.push(Number((k * 0.1).toFixed(2)));
    return ticks;
  }, [fractions, last]);
  const tenPercent = useMemo(() => {
    let best = 0;
    fractions.forEach((f, i) => {
      if (Math.abs(f - 0.1) < Math.abs(fractions[best] - 0.1)) best = i;
    });
    return best;
  }, [fractions]);

  const stepMs = reduced ? CALM_STEP_MS : STEP_MS;
  const { batch, setBatch, playing, setPlaying } = useRace(last, reduced ? tenPercent : 0, stepMs);
  const [metric, setMetric] = useState("flow");
  const [focus, setFocus] = useState("all");
  const [hover, setHover] = useState(null);
  const [mainRef, mainWidth] = useWidth(900);
  const [viewRef, seen] = useInView("0px 0px -35% 0px");
  const started = useRef(false);
  const pressed = useRef(false);
  const rows = useRef(new Map());
  const previousRank = useRef(new Map());
  const mapTokens = useTokens(MAP_TOKENS);

  const narrow = mainWidth < 640;
  const height = narrow ? 300 : 420;
  const margin = narrow ? NARROW_MARGIN : WIDE_MARGIN;
  const series = model[metric];
  const m = METRICS[metric];
  const fraction = fractions[batch];
  const random = series.find((s) => s.trials);
  const total = strategies.length;
  const totalWord = numberWord(total);
  const stepShare = percent(meta.protocol.batch_fraction_of_remaining, 0);
  const dim = (id) => focus !== "all" && focus !== id;

  useEffect(() => {
    if (!seen || reduced || started.current) return;
    started.current = true;
    setBatch(0);
    setPlaying(true);
  }, [seen, reduced, setBatch, setPlaying]);

  const standings = series
    .map((s) => ({ ...s, value: s.values[batch], halved: s.halvedAt != null && fraction >= s.halvedAt - 1e-9 }))
    .sort((a, b) => a.value - b.value || a.auc - b.auc);

  useLayoutEffect(() => {
    standings.forEach((s, rank) => {
      const node = rows.current.get(s.id);
      if (!node) return;
      const from = previousRank.current.get(s.id);
      if (from != null && from !== rank) {
        node.style.transition = "none";
        node.style.transform = `translateY(${from * ROW}px)`;
        node.getBoundingClientRect();
        node.style.transition = "";
      }
      node.style.transform = `translateY(${rank * ROW}px)`;
      previousRank.current.set(s.id, rank);
    });
  });

  const [announcement, setAnnouncement] = useState("");
  const summary = `At ${percent(fraction)} of cell types removed, ${m.noun} remaining: ${standings
    .map((s) => `${s.label} ${percent(s.value)}`)
    .join(", ")}.`;
  useEffect(() => {
    if (playing || !started.current) return undefined;
    const timer = setTimeout(() => setAnnouncement(summary), 700);
    return () => clearTimeout(timer);
  }, [playing, summary]);

  function seek(index) {
    started.current = true;
    setPlaying(false);
    setBatch(Math.max(0, Math.min(last, index)));
  }

  function toggle() {
    started.current = true;
    if (playing) setPlaying(false);
    else {
      if (batch >= last) setBatch(0);
      setPlaying(true);
    }
  }

  function nearestIndex(x, inner) {
    const f = (Math.max(0, Math.min(inner.width, x)) / inner.width) * fractions[last];
    let best = 0;
    for (let i = 1; i < fractions.length; i += 1) {
      if (Math.abs(fractions[i] - f) < Math.abs(fractions[best] - f)) best = i;
    }
    return best;
  }

  function pointer(x, y, inner) {
    const index = nearestIndex(x, inner);
    if (index !== hover?.index || (x > inner.width / 2 ? "left" : "right") !== hover?.side) {
      setHover({ index, side: x > inner.width / 2 ? "left" : "right" });
    }
    if (pressed.current && index !== batch) seek(index);
  }

  const paths = useRef({ key: "", value: null });
  function geometry(inner) {
    const key = `${metric}|${inner.width}|${inner.height}`;
    if (paths.current.key === key) return paths.current.value;
    const x = linear([0, fractions[last]], [0, inner.width]);
    const y = linear([0, 1], [inner.height, 0]);
    const value = {
      x,
      y,
      lines: series.map((s) => line(s.values.map((v, i) => [x(fractions[i]), y(v)]))),
      band:
        random &&
        band(
          random.trials.high.map((v, i) => [x(fractions[i]), y(v)]),
          random.trials.low.map((v, i) => [x(fractions[i]), y(v)]),
        ),
    };
    paths.current = { key, value };
    return value;
  }

  const atEnd = batch >= last;
  const playLabel = playing ? "Pause" : atEnd ? "Replay" : batch > 0 && started.current ? "Resume" : "Play";
  const halvedCount = standings.filter((s) => s.halved).length;
  const leader = standings[0];
  const randomNow = random && standings.find((s) => s.id === random.id);
  const aspect = useMemo(() => atlasAspect(types, atlas), [types, atlas]);
  const randomTrials = random && percolation.strategies[random.id].trials;
  const avalanche = useMemo(() => {
    let best = null;
    for (const { id, label } of strategies) {
      const sizes = percolation.strategies[id].avalanche;
      if (!Array.isArray(sizes)) continue;
      sizes.forEach((size, i) => {
        if (!best || size > best.size) best = { size, label, fraction: fractions[i] };
      });
    }
    return best;
  }, [percolation, strategies, fractions]);

  const motion = {
    "--race-step": playing ? `${stepMs}ms` : "260ms",
    "--race-ease": playing ? "linear" : "var(--ease)",
  };

  const controls = (
    <div className="race-controls">
      <button type="button" className="btn is-strong race-play" onClick={toggle} aria-label={`${playLabel} the removal race`}>
        <Icon kind={playing ? "pause" : atEnd ? "replay" : "play"} />
        {playLabel}
      </button>
      <Segmented
        label="Measure shown"
        options={Object.entries(METRICS).map(([value, item]) => ({ value, label: item.label }))}
        value={metric}
        onChange={setMetric}
      />
    </div>
  );

  return (
    <section className="section" id="collapse" aria-labelledby="collapse-title">
      <div className="wrap">
        <Intro meta={meta} percolation={percolation} flowSeries={model.flow} />

        <Figure
          id="collapse-race"
          title={`The race between ${totalWord} attacks`}
          variant="field"
          controls={controls}
          caption={
            <>
              Each map is the nervous system at the current step under one strategy, one square per cell type at its place
              in the brain and nerve cord. Types removed in earlier steps are no longer drawn, and grey squares are types still present but cut off from every sensory type.
              {avalanche && avalanche.size > 1000
                ? ` The largest single step, under ${avalanche.label} at ${percent(avalanche.fraction)} removed, cuts ${count(avalanche.size)} cell types off from sensory input at once.`
                : ""}
            </>
          }
        >
          <div className="race-focus">
            <span className="label" id={focusLabelId}>
              Follow a strategy
            </span>
            <Segmented
              label="Follow a strategy"
              options={[
                { value: "all", label: `All ${totalWord}` },
                ...strategies.map(({ id, label }) => ({ value: id, label: capitalize(label), color: `var(--glow-${id})` })),
              ]}
              value={focus}
              onChange={setFocus}
            />
          </div>

          <div className="instrument race-instrument" ref={viewRef} style={motion}>
            <div className="instrument-main" ref={mainRef}>
              <div
                className={`race-chart race-tip-${narrow ? "top" : hover?.side ?? "right"}`}
                onPointerDown={(event) => {
                  if (event.pointerType === "mouse") pressed.current = true;
                }}
                onPointerUp={() => (pressed.current = false)}
                onPointerLeave={() => (pressed.current = false)}
                onClick={() => hover && seek(hover.index)}
              >
                <ChartFrame
                  height={height}
                  margin={margin}
                  label={`${m.label} remaining, as a share of the intact graph, against the share of cell types removed, for ${totalWord} removal strategies. Drawn up to ${percent(fraction)} removed. The table below the figure lists the summary values.`}
                  onPointer={pointer}
                  onLeave={() => setHover(null)}
                  overlay={({ width, height: innerHeight, margin: frame }) => {
                    if (!hover) return null;
                    const inner = { width: width - frame.left - frame.right, height: innerHeight };
                    const { x } = geometry(inner);
                    const k = hover.index;
                    const tipRows = series.map((s) => ({ ...s, v: s.values[k] })).sort((a, b) => a.v - b.v);
                    return (
                      <Tooltip
                        x={frame.left + x(fractions[k])}
                        y={narrow ? frame.top + 4 : frame.top + innerHeight / 2}
                        width={width}
                      >
                        <strong>{percent(fractions[k])} removed</strong>
                        {tipRows.map((s) => (
                          <Row key={s.id} label={s.name} value={percent(s.v)} color={s.color} />
                        ))}
                        {random && (
                          <span className="race-tip-note">
                            {randomTrials} random orders: {percent(random.trials.low[k])} to {percent(random.trials.high[k])}
                          </span>
                        )}
                      </Tooltip>
                    );
                  }}
                >
                  {(inner) => {
                    const { x, y, lines, band: bandPath } = geometry(inner);
                    const head = x(fraction);
                    const labels = narrow
                      ? []
                      : spreadLabels(
                          standings.map((s) => ({ id: s.id, label: s.name, color: s.color, y: y(s.value) })),
                          16,
                          4,
                          inner.height,
                        );
                    return (
                      <>
                        <defs>
                          <clipPath id={clipId}>
                            <rect
                              className="race-move"
                              x={-inner.width - 4}
                              y={-12}
                              width={inner.width + 4}
                              height={inner.height + 24}
                              style={{ transform: `translateX(${head}px)` }}
                            />
                          </clipPath>
                        </defs>
                        <YAxis
                          scale={y}
                          ticks={[0, 0.25, 0.5, 0.75, 1]}
                          width={inner.width}
                          format={(t) => `${Math.round(t * 100)}%`}
                          title={`${m.label} remaining`}
                          inset={narrow ? 36 : 46}
                        />
                        <XAxis
                          scale={x}
                          ticks={xTicks}
                          height={inner.height}
                          width={inner.width}
                          format={(t) => `${Math.round(t * 100)}%`}
                          title="Cell types removed"
                        />
                        <line className="race-half" x1={0} x2={inner.width} y1={y(0.5)} y2={y(0.5)} />
                        <text className="race-half-label" x={inner.width - 4} y={y(0.5) - 7} textAnchor="end">
                          half
                        </text>

                        <g clipPath={`url(#${clipId})`}>
                          {bandPath && <path d={bandPath} className={`race-band ${dim(random.id) ? "is-dim" : ""}`} />}
                          {series.map((s, i) => (
                            <path
                              key={s.id}
                              d={lines[i]}
                              className={`race-line ${dim(s.id) ? "is-dim" : ""} ${focus === s.id ? "is-focus" : ""}`}
                              style={{ stroke: s.color, strokeDasharray: s.trials ? "5 4" : undefined }}
                            />
                          ))}
                        </g>

                        {series.map((s) =>
                          s.ci && fraction >= s.ci[0] ? (
                            <line
                              key={`ci-${s.id}`}
                              className={`race-ci-bar ${dim(s.id) ? "is-dim" : ""}`}
                              x1={x(s.ci[0])}
                              x2={x(Math.min(s.ci[1], fraction))}
                              y1={y(0.5)}
                              y2={y(0.5)}
                              style={{ stroke: s.color }}
                            />
                          ) : null,
                        )}
                        {standings.map((s) =>
                          s.halved ? (
                            <g
                              key={`half-${metric}-${s.id}`}
                              className={dim(s.id) ? "is-dim" : ""}
                              transform={`translate(${x(s.halvedAt)},${y(0.5)})`}
                            >
                              <circle r={5} className="race-ring" style={{ stroke: s.color }} />
                              <circle r={4.5} className="race-halving" style={{ stroke: s.color }} />
                            </g>
                          ) : null,
                        )}

                        <line
                          className="race-playhead race-move"
                          x1={0}
                          x2={0}
                          y1={-8}
                          y2={inner.height}
                          style={{ transform: `translateX(${head}px)` }}
                        />

                        {hover && (
                          <g>
                            <line
                              className="race-hover-line"
                              x1={x(fractions[hover.index])}
                              x2={x(fractions[hover.index])}
                              y1={0}
                              y2={inner.height}
                            />
                            {series.map((s) => (
                              <circle
                                key={s.id}
                                cx={x(fractions[hover.index])}
                                cy={y(s.values[hover.index])}
                                r={3.5}
                                className="race-dot"
                                style={{ fill: s.color }}
                              />
                            ))}
                          </g>
                        )}

                        {series.map((s) => (
                          <circle
                            key={`head-${s.id}`}
                            r={4}
                            className={`race-dot race-move ${dim(s.id) ? "is-dim" : ""}`}
                            style={{ fill: s.color, transform: `translate(${head}px, ${y(s.values[batch])}px)` }}
                          />
                        ))}
                        {labels.map((l) => (
                          <text
                            key={`label-${l.id}`}
                            className={`direct-label race-move ${dim(l.id) ? "is-dim" : ""} ${focus === l.id ? "is-focus" : ""}`}
                            dy="0.32em"
                            style={{ fill: l.color, transform: `translate(${head + 10}px, ${l.y}px)` }}
                          >
                            {l.label}
                          </text>
                        ))}
                      </>
                    );
                  }}
                </ChartFrame>
              </div>

              {narrow && (
                <div className="legend race-legend" aria-hidden="true">
                  {series.map((s) => (
                    <span key={s.id}>
                      <span className="swatch is-line" style={{ background: s.color }} />
                      {s.name}
                    </span>
                  ))}
                </div>
              )}

              <div className="race-scrub">
                <Slider
                  label="Removal step"
                  min={0}
                  max={last}
                  value={batch}
                  onChange={seek}
                  format={(v) => `${percent(fractions[v])} removed`}
                  valueText={(v) => `Step ${v} of ${last}, ${percent(fractions[v])} of cell types removed`}
                />
              </div>

              <p className="caption race-chart-caption">
                Each line is the share of the intact value still standing as cell types are removed, {stepShare} of those
                left at each step; the vertical line is the current step. Rings on the half line mark where each attack
                halves the measure. The grey band spans the lowest and highest value across {randomTrials} random removal
                orders, the dashed line is one of them, and the short bar on the half line is the 95% confidence interval
                of the random halving point. Click the chart or drag the slider to move to any step.
              </p>
            </div>

            <div className="race-side">
              <p className="label">
                {m.label} remaining at {percent(fraction)} removed, most damaged first
              </p>
              <ol className="board race-board" style={{ height: total * ROW }} aria-label={`${m.label} remaining, most damaged first`}>
                {standings.map((s) => (
                  <li
                    key={s.id}
                    ref={(node) => {
                      if (node) rows.current.set(s.id, node);
                      else rows.current.delete(s.id);
                    }}
                    className={`${dim(s.id) ? "is-dim" : ""} ${focus === s.id ? "is-focus" : ""}`}
                  >
                    <span className="bar" style={{ background: s.color }} />
                    <span className="race-board-name">
                      <span className="race-board-label">{s.name}</span>
                      <span className="race-meter" aria-hidden="true">
                        <span style={{ transform: `scaleX(${Math.max(0, s.value)})`, background: s.color }} />
                      </span>
                      <span className={`meta ${s.halved ? "is-halved" : ""}`} key={s.halved ? "halved" : "intact"}>
                        {s.halved ? `halved at ${percent(s.halvedAt)}` : `AUC ${fixed(s.auc, 3)}`}
                      </span>
                    </span>
                    <span className="value">{percent(s.value)}</span>
                  </li>
                ))}
              </ol>
              <p className="caption race-commentary">
                {halvedSentence(halvedCount, total, m.noun)}
                {batch > 0 && randomNow && leader.id !== randomNow.id
                  ? ` Ranked by ${leader.label}, ${percent(leader.value)} is left; random removal leaves ${percent(randomNow.value)}.`
                  : ""}
              </p>
              <div className="visually-hidden" role="status" aria-live="polite">
                {announcement}
              </div>
            </div>
          </div>

          <div className="race-multiples-head">
            <p className="label">
              Where each attack strikes at step {batch}, {percent(fraction)} removed
            </p>
            <div className="legend race-map-legend" aria-hidden="true">
              <span>
                <span className="race-key race-key-live" />
                Present
              </span>
              <span>
                <span className="race-key race-key-fresh" />
                Removed in this step
              </span>
              <span>
                <span className="race-key race-key-silent" />
                Cut off from sensory input
              </span>
            </div>
          </div>
          <Multiples
            strategies={strategies}
            types={types}
            atlas={atlas}
            batch={batch}
            aspect={aspect}
            focus={focus}
            silentColor={mapTokens["field-ink-2"]}
          />
        </Figure>

        <Summary model={model} />
      </div>
    </section>
  );
}

const MAP_STAGGER_MS = 18;

/** One strategy per map; redraws are staggered so six canvases never repaint in the same frame. */
const Multiples = memo(function Multiples({ strategies, types, atlas, batch, aspect, focus, silentColor }) {
  return (
    <div className="multiples race-multiples">
      {strategies.map(({ id, label }, index) => (
        <MapCell
          key={id}
          id={id}
          label={label}
          types={types}
          atlas={atlas}
          batch={batch}
          delay={index * MAP_STAGGER_MS}
          aspect={aspect}
          dimmed={focus !== "all" && focus !== id}
          silentColor={silentColor}
        />
      ))}
    </div>
  );
});

const MapCell = memo(function MapCell({ id, label, types, atlas, batch, delay, aspect, dimmed, silentColor }) {
  const [shown, setShown] = useState(batch);
  useEffect(() => {
    if (shown === batch) return undefined;
    const timer = setTimeout(() => setShown(batch), delay);
    return () => clearTimeout(timer);
  }, [batch, shown, delay]);

  const replay = atlas.replay[id];
  const removed = replay.removed_types[shown];
  const silenced = replay.silenced_types[shown];
  return (
    <div className={`multiple ${dimmed ? "is-dim" : ""}`}>
      <p className="label">
        <span className="race-multiple-name">
          <span className="swatch" style={{ background: `var(--glow-${id})` }} />
          {capitalize(label)}
        </span>
      </p>
      <div className="canvas-box" style={{ aspectRatio: aspect }}>
        <Atlas
          types={types}
          atlas={atlas}
          batch={shown}
          removedAt={types.removed[id]}
          silencedAt={types.silenced[id]}
          tone="field"
          pointAlpha={0.24}
          ghostAlpha={0}
          silentColor={silentColor}
          silentAlpha={1}
          label={`Nervous system under ${label} removal at ${percent(replay.fraction_removed[shown])} removed: ${count(removed)} cell types removed, ${count(silenced)} cut off from sensory input.`}
        />
      </div>
      <div className="race-counts">
        <span>
          <span className="number">{count(removed)}</span> removed
        </span>
        <span>
          <span className="number">{count(silenced)}</span> cut off
        </span>
      </div>
    </div>
  );
});

/** Section heading and the prose that introduces the race, with notes defining the halving point and AUC. */
const Intro = memo(function Intro({ meta, percolation, flowSeries }) {
  const totalWord = numberWord(meta.strategies.length);
  const stepShare = percent(meta.protocol.batch_fraction_of_remaining, 0);
  const [aucFrom, aucTo] = meta.protocol.auc_range;
  const fastest = flowSeries.filter((s) => !s.trials).sort((a, b) => a.halvedAt - b.halvedAt)[0];
  const randomFlow = flowSeries.find((s) => s.trials);
  const randomTrials = randomFlow && percolation.strategies[randomFlow.id].trials;
  return (
    <div className="section-head">
      <h2 id="collapse-title">{capitalize(totalWord)} ways to take it apart</h2>
      <TextBlock
        notes={
          <>
            <Sidenote
              title={
                <>
                  Halving point, <i>f</i>
                  <sub>c</sub>
                </>
              }
            >
              The share of cell types removed when flow capacity first falls below half of its intact{" "}
              {count(percolation.intact_flow)} routes, interpolated between steps. For random removal it is the mean
              over {randomTrials} orders.
            </Sidenote>
            <Sidenote title="Area under the curve (AUC)">
              The area under a curve from {percent(aucFrom, 0)} to {percent(aucTo, 0)} removed, divided by that
              range. A measure that never dropped would score 1; lower means the network gives way sooner. Random
              removal scores {fixed(randomFlow.auc, 3)} on flow capacity.
            </Sidenote>
          </>
        }
      >
        <p>
          {capitalize(totalWord)} removal orders run on the same {count(meta.graph.cell_types)} cell types. Each step
          takes away {stepShare} of the types still present and scores the rest again, so an attack on hubs keeps
          finding the new hubs as the old ones go.
        </p>
        <p>
          Targeting by {fastest.label} halves sensory-to-motor flow capacity once {percent(fastest.halvedAt)} of
          types are gone; random removal needs {percent(randomFlow.halvedAt)}. The race below runs all {totalWord} at
          once.
        </p>
      </TextBlock>
    </div>
  );
});

/** Summary table of AUC and halving point per strategy, ordered by halving point. */
const Summary = memo(function Summary({ model }) {
  const flowSeries = model.flow;
  return (
    <details className="more race-more">
      <summary>Area under the curve and halving point for each strategy</summary>
      <div className="table-wrap">
        <table className="data">
          <thead>
            <tr>
              <th scope="col">Strategy</th>
              <th scope="col" className="num">
                AUC, flow capacity
              </th>
              <th scope="col" className="num">
                AUC, reachable pairs
              </th>
              <th scope="col" className="num">
                Flow capacity halves at
              </th>
            </tr>
          </thead>
          <tbody>
            {[...flowSeries]
              .sort((a, b) => a.halvedAt - b.halvedAt)
              .map((s) => {
                const pairs = model.pairs.find((p) => p.id === s.id);
                return (
                  <tr key={s.id}>
                    <td className="race-table-name">
                      <span className="swatch" style={{ background: `var(--s-${s.id}-ink, var(--s-${s.id}))` }} />
                      {s.name}
                    </td>
                    <td className="num">{fixed(s.auc, 3)}</td>
                    <td className="num">{fixed(pairs.auc, 3)}</td>
                    <td className="num">
                      {percent(s.halvedAt)}
                      {s.ci && (
                        <span className="race-ci">
                          {" "}
                          (95% CI {percent(s.ci[0])} to {percent(s.ci[1])})
                        </span>
                      )}
                    </td>
                  </tr>
                );
              })}
          </tbody>
        </table>
      </div>
    </details>
  );
});
