import { memo, useCallback, useEffect, useId, useMemo, useRef, useState } from "react";
import Atlas, { atlasAspect } from "./Atlas.jsx";
import { ChartFrame, XAxis, YAxis, spreadLabels } from "./Chart.jsx";
import { Figure, Segmented, Sidenote, TextBlock } from "./ui.jsx";
import { useInView, useReducedMotion, useTokens, useWidth } from "../lib/hooks.js";
import { count, fixed, numberWord, percent, sentence, valueAt } from "../lib/format.js";
import { band, line, linear } from "../lib/scales.js";
import "../styles/collapse.css";

const STEP_MS = 120;
const CALM_STEP_MS = 600;
const THUMB = 14;
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

// The right margin holds the labels at the playhead: a value column, then the strategy name.
const WIDE_MARGIN = { top: 32, right: 228, bottom: 46, left: 54 };
const NARROW_MARGIN = { top: 32, right: 14, bottom: 42, left: 40 };
const LABEL_VALUE_X = 50;
const LABEL_NAME_X = 58;

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
  const word = sentence(numberWord(halved));
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
      <path d="M4 1.8 12.2 7 4 12.2z" fill="currentColor" />
    </svg>
  );
}

function nearestStep(fractions, f) {
  let best = 0;
  for (let i = 1; i < fractions.length; i += 1) {
    if (Math.abs(fractions[i] - f) < Math.abs(fractions[best] - f)) best = i;
  }
  return best;
}

export default function Collapse({ meta, percolation, types, atlas }) {
  const reduced = useReducedMotion();
  const strategies = meta.strategies;
  const uid = useId().replace(/[^a-zA-Z0-9_-]/g, "");
  const clipId = `race-clip-${uid}`;
  const measureLabelId = `race-measure-${uid}`;

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
          name: sentence(label),
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
  const tenPercent = useMemo(() => nearestStep(fractions, 0.1), [fractions]);

  const stepMs = reduced ? CALM_STEP_MS : STEP_MS;
  const { batch, setBatch, playing, setPlaying } = useRace(last, reduced ? tenPercent : 0, stepMs);
  const [metric, setMetric] = useState("flow");
  const [pinned, setPinned] = useState(null);
  const [hovered, setHovered] = useState(null);
  const [hoverStep, setHoverStep] = useState(null);
  const [mainRef, mainWidth] = useWidth(900);
  const [viewRef, seen] = useInView("0px 0px -35% 0px");
  const started = useRef(false);
  const pressed = useRef(false);
  const labelSpots = useRef([]);
  const mapTokens = useTokens(MAP_TOKENS);

  const narrow = mainWidth < 640;
  const height = narrow ? 300 : 440;
  const margin = narrow ? NARROW_MARGIN : WIDE_MARGIN;
  const series = model[metric];
  const m = METRICS[metric];
  const fraction = fractions[batch];
  const random = series.find((s) => s.trials);
  const total = strategies.length;
  const totalWord = numberWord(total);
  const active = hovered ?? pinned;
  const dim = (id) => active != null && active !== id;

  useEffect(() => {
    if (!seen || reduced || started.current) return;
    started.current = true;
    setBatch(0);
    setPlaying(true);
  }, [seen, reduced, setBatch, setPlaying]);

  const halved = (s) => s.halvedAt != null && fraction >= s.halvedAt - 1e-9;
  const halvedCount = series.filter(halved).length;
  const removedCount = atlas.replay[strategies[0].id].removed_types[batch];

  const [announcement, setAnnouncement] = useState("");
  const ranked = [...series].sort((a, b) => a.values[batch] - b.values[batch] || a.auc - b.auc);
  const summary = `At ${percent(fraction)} of cell types removed, ${m.noun} remaining: ${ranked
    .map((s) => `${s.label} ${percent(s.values[batch])}`)
    .join(", ")}. ${halvedSentence(halvedCount, total, m.noun)}`;
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

  const togglePin = useCallback((id) => setPinned((current) => (current === id ? null : id)), []);

  // A click on a map or line leaves focus outside the figure, so Escape is heard on the document while a pin is set.
  useEffect(() => {
    if (!pinned) return undefined;
    const onKeyDown = (event) => {
      if (event.key === "Escape" && !event.defaultPrevented) setPinned(null);
    };
    document.addEventListener("keydown", onKeyDown);
    return () => document.removeEventListener("keydown", onKeyDown);
  }, [pinned]);

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

  /** Highlights the line nearest the pointer, or the label under it; a pressed mouse drags the step. */
  function pointer(px, py, inner) {
    const { x, y } = geometry(inner);
    let target = null;
    let step = null;
    if (px > inner.width + 4) {
      const spot = labelSpots.current.find((l) => Math.abs(l.y - py) <= 8);
      target = spot?.id ?? null;
    } else {
      step = nearestStep(fractions, x.invert(Math.max(0, Math.min(inner.width, px))));
      if (step <= batch) {
        let best = 18;
        for (const s of series) {
          const d = Math.abs(y(s.values[step]) - py);
          if (d < best) {
            best = d;
            target = s.id;
          }
        }
      }
    }
    if (target !== hovered) setHovered(target);
    if (step !== hoverStep) setHoverStep(step);
    if (pressed.current && step != null && step !== batch) seek(step);
  }

  const atEnd = batch >= last;
  const playLabel = playing ? "Pause" : atEnd ? "Replay" : batch > 0 && started.current ? "Resume" : "Play";
  const aspect = useMemo(() => atlasAspect(types, atlas), [types, atlas]);
  const firstToHalve = series
    .filter((s) => !s.trials && s.halvedAt != null)
    .sort((a, b) => a.halvedAt - b.halvedAt)[0];
  const annotated = (active ? [active, random?.id] : [firstToHalve?.id, random?.id]).filter(
    (id, i, list) => id && list.indexOf(id) === i,
  );

  const motion = {
    "--race-step": playing ? `${stepMs}ms` : "260ms",
    "--race-ease": playing ? "linear" : "var(--ease)",
    "--race-left": `${margin.left}px`,
    "--race-right": `${margin.right}px`,
    "--race-thumb": `${THUMB}px`,
  };

  const measure = (
    <div className="race-measure">
      <span className="race-measure-label" id={measureLabelId}>
        Measure
      </span>
      <Segmented
        labelledBy={measureLabelId}
        options={Object.entries(METRICS).map(([value, item]) => ({ value, label: item.label }))}
        value={metric}
        onChange={setMetric}
      />
    </div>
  );

  const readout = (
    <p className="race-readout" aria-hidden="true">
      <span className="number">{percent(fraction)}</span>
      <span className="race-readout-note">removed, {count(removedCount)} cell types</span>
    </p>
  );

  return (
    <section className="section" id="collapse" aria-labelledby="collapse-title">
      <div className="wrap">
        <Intro meta={meta} percolation={percolation} flowSeries={model.flow} pairsSeries={model.pairs} />

        <Figure
          id="collapse-race"
          title={`The race between ${totalWord} attacks`}
          variant="field"
          controls={measure}
          caption={
            <>
              Each line is the share of {m.noun} left as cell types are removed, and each map shows the same step under
              one attack. Red dots mark where an attack halves it; point at a line or map, or select a map&apos;s name,
              to follow one attack.
            </>
          }
        >
          <div
            className={`race ${active ? "has-focus" : ""}`}
            ref={viewRef}
            style={motion}
          >
            <div className="race-main" ref={mainRef}>
              <div
                className="race-chart"
                onPointerDown={(event) => {
                  if (event.pointerType === "mouse") pressed.current = true;
                }}
                onPointerUp={() => (pressed.current = false)}
                onPointerLeave={() => (pressed.current = false)}
                onClick={() => {
                  if (hoverStep != null) seek(hoverStep);
                  else if (hovered) togglePin(hovered);
                }}
              >
                <ChartFrame
                  height={height}
                  margin={margin}
                  label={`${m.label} remaining, as a share of the intact graph, against the share of cell types removed, for ${totalWord} removal strategies, drawn up to ${percent(fraction)} removed. The table after the figure lists the halving point and area under the curve for each.`}
                  onPointer={pointer}
                  onLeave={() => {
                    setHovered(null);
                    setHoverStep(null);
                  }}
                >
                  {(inner) => {
                    const { x, y, lines, band: bandPath } = geometry(inner);
                    const head = x(fraction);
                    const labels = narrow
                      ? []
                      : spreadLabels(
                          series.map((s) => ({ id: s.id, name: s.name, color: s.color, value: s.values[batch], y: y(s.values[batch]) })),
                          17,
                          4,
                          inner.height,
                        );
                    labelSpots.current = labels;
                    const half = y(0.5);
                    const room = inner.width + (narrow ? margin.right : 0);
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
                        <line className="race-half" x1={0} x2={inner.width} y1={half} y2={half} />
                        <text className="race-half-label" x={inner.width - 4} y={half + 16} textAnchor="end">
                          Half of intact
                        </text>

                        <g clipPath={`url(#${clipId})`}>
                          {bandPath && <path d={bandPath} className={`race-band ${dim(random.id) ? "is-dim" : ""}`} />}
                          {series.map((s, i) => (
                            <path
                              key={s.id}
                              d={lines[i]}
                              className={`race-line ${dim(s.id) ? "is-dim" : ""} ${active === s.id ? "is-focus" : ""}`}
                              style={{ stroke: s.color, strokeDasharray: s.trials ? "5 4" : undefined }}
                            />
                          ))}
                        </g>

                        {hoverStep != null && hoverStep !== batch && (
                          <line
                            className="race-hover-line"
                            x1={x(fractions[hoverStep])}
                            x2={x(fractions[hoverStep])}
                            y1={0}
                            y2={inner.height}
                          />
                        )}

                        <line
                          className="race-playhead race-move"
                          x1={0}
                          x2={0}
                          y1={-8}
                          y2={inner.height}
                          style={{ transform: `translateX(${head}px)` }}
                        />

                        {series.map((s) =>
                          halved(s) ? (
                            <circle
                              key={`half-${metric}-${s.id}`}
                              className={`race-halving ${dim(s.id) ? "is-dim" : ""}`}
                              cx={x(s.halvedAt)}
                              cy={half}
                              r={active === s.id ? 5 : 4}
                            />
                          ) : null,
                        )}

                        {(() => {
                          let lastRight = -Infinity;
                          return series
                            .filter((s) => annotated.includes(s.id) && halved(s))
                            .sort((a, b) => a.halvedAt - b.halvedAt)
                            .map((s) => {
                              const name = narrow ? "" : `${s.name}, `;
                              const value = `${narrow ? "Halved" : "halved"} at ${percent(s.halvedAt)}`;
                              // Approximate width of 12px Archivo; on wide charts the note waits until the playhead labels have passed it.
                              const w = (name.length + value.length) * 6.4;
                              const left = Math.max(0, Math.min(room - w, x(s.halvedAt) - w / 2));
                              if (!narrow && head < left + w + 12) return null;
                              const below = left < lastRight + 8;
                              lastRight = below ? lastRight : left + w;
                              return (
                                <text
                                  key={`note-${metric}-${s.id}`}
                                  className="race-note"
                                  x={left}
                                  y={below ? half + 20 : half - 11}
                                >
                                  {name && <tspan style={{ fill: s.color }}>{name}</tspan>}
                                  {value}
                                </text>
                              );
                            });
                        })()}

                        {series.map((s) => (
                          <circle
                            key={`head-${s.id}`}
                            r={active === s.id ? 4.5 : 3.5}
                            className={`race-dot race-move ${dim(s.id) ? "is-dim" : ""}`}
                            style={{ fill: s.color, transform: `translate(${head}px, ${y(s.values[batch])}px)` }}
                          />
                        ))}
                        {labels.map((l) => (
                          <g
                            key={`label-${l.id}`}
                            className={`race-label race-move ${dim(l.id) ? "is-dim" : ""} ${active === l.id ? "is-focus" : ""}`}
                            style={{ transform: `translate(${head}px, ${l.y}px)` }}
                          >
                            <text className="race-label-value" x={LABEL_VALUE_X} dy="0.32em" textAnchor="end">
                              {percent(l.value)}
                            </text>
                            <text className="race-label-name" x={LABEL_NAME_X} dy="0.32em" style={{ fill: l.color }}>
                              {l.name}
                            </text>
                          </g>
                        ))}
                      </>
                    );
                  }}
                </ChartFrame>
              </div>

              {narrow && (
                <ul className="race-key" aria-label={`${m.label} remaining at ${percent(fraction)} removed`}>
                  {series.map((s) => (
                    <li key={s.id}>
                      <button
                        type="button"
                        aria-pressed={pinned === s.id}
                        className={dim(s.id) ? "is-dim" : ""}
                        onClick={() => togglePin(s.id)}
                      >
                        <span className="swatch is-line" style={{ background: s.color }} aria-hidden="true" />
                        <span className="race-key-name">{s.name}</span>
                        <span className={`race-key-value ${halved(s) ? "is-halved" : ""}`}>{percent(s.values[batch])}</span>
                      </button>
                    </li>
                  ))}
                </ul>
              )}

              <div className={`race-scrub ${narrow ? "is-narrow" : ""}`}>
                <button
                  type="button"
                  className="race-play"
                  onClick={toggle}
                  aria-label={`${playLabel} the removal race`}
                  title={playLabel}
                >
                  <Icon kind={playing ? "pause" : atEnd ? "replay" : "play"} />
                </button>
                <div className="race-track" style={{ "--at": fraction / fractions[last] }}>
                  <span className="race-rail" aria-hidden="true" />
                  <input
                    type="range"
                    min={0}
                    max={fractions[last]}
                    step="any"
                    value={fraction}
                    aria-label="Cell types removed"
                    aria-valuetext={`Step ${batch} of ${last}, ${percent(fraction)} of cell types removed`}
                    onChange={(event) => seek(nearestStep(fractions, Number(event.target.value)))}
                    onKeyDown={(event) => {
                      const move = { ArrowRight: 1, ArrowUp: 1, ArrowLeft: -1, ArrowDown: -1, PageUp: 5, PageDown: -5 }[
                        event.key
                      ];
                      if (move) seek(batch + move);
                      else if (event.key === "Home") seek(0);
                      else if (event.key === "End") seek(last);
                      else return;
                      event.preventDefault();
                    }}
                  />
                </div>
                {readout}
              </div>
              <div className="visually-hidden" role="status" aria-live="polite">
                {announcement}
              </div>
            </div>

            <div className="race-maps-head">
              <div className="legend race-map-legend" aria-hidden="true">
                <span>
                  <span className="race-swatch race-swatch-live" />
                  Present
                </span>
                <span>
                  <span className="race-swatch race-swatch-fresh" />
                  Removed in this step
                </span>
                <span>
                  <span className="race-swatch race-swatch-silent" />
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
              active={active}
              pinned={pinned}
              onHover={setHovered}
              onPin={togglePin}
              silentColor={mapTokens["field-ink-2"]}
            />
          </div>
        </Figure>

        <Summary model={model} />
      </div>
    </section>
  );
}

const MAP_STAGGER_MS = 18;

/** One strategy per map; redraws are staggered so six canvases never repaint in the same frame. */
const Multiples = memo(function Multiples({ strategies, types, atlas, batch, aspect, active, pinned, onHover, onPin, silentColor }) {
  return (
    <ul className="race-maps">
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
          dimmed={active != null && active !== id}
          focused={active === id}
          pinned={pinned === id}
          onHover={onHover}
          onPin={onPin}
          silentColor={silentColor}
        />
      ))}
    </ul>
  );
});

const MapCell = memo(function MapCell({ id, label, types, atlas, batch, delay, aspect, dimmed, focused, pinned, onHover, onPin, silentColor }) {
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
    <li
      className={`race-map ${dimmed ? "is-dim" : ""} ${focused ? "is-focus" : ""}`}
      style={{ "--strategy": `var(--glow-${id})` }}
      onPointerEnter={(event) => event.pointerType === "mouse" && onHover(id)}
      onPointerLeave={(event) => event.pointerType === "mouse" && onHover(null)}
      onClick={() => onPin(id)}
    >
      <button
        type="button"
        className="race-map-name"
        aria-pressed={pinned}
        onFocus={(event) => event.target.matches(":focus-visible") && onHover(id)}
        onBlur={() => onHover(null)}
      >
        <span className="swatch" aria-hidden="true" />
        {sentence(label)}
      </button>
      <div className="race-map-canvas" style={{ aspectRatio: aspect }}>
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
      <p className="race-map-count" aria-hidden="true">
        <span className="number">{count(silenced)}</span> cut off
      </p>
    </li>
  );
});

/** Section heading and the prose that introduces the race, with notes on the random baseline and how to read it. */
const Intro = memo(function Intro({ meta, percolation, flowSeries, pairsSeries }) {
  const totalWord = numberWord(meta.strategies.length);
  const fastest = flowSeries.filter((s) => !s.trials).sort((a, b) => a.halvedAt - b.halvedAt)[0];
  const randomFlow = flowSeries.find((s) => s.trials);
  const randomPairs = pairsSeries.find((s) => s.id === randomFlow.id);
  const randomTrials = percolation.strategies[randomFlow.id].trials;
  const batchShare = meta.protocol?.batch_fraction_of_remaining;
  const avalanche = useMemo(() => {
    const fractions = percolation.strategies[meta.strategies[0].id].fraction_removed;
    let best = null;
    for (const { id, label } of meta.strategies) {
      const sizes = percolation.strategies[id].avalanche;
      if (!Array.isArray(sizes)) continue;
      sizes.forEach((size, i) => {
        if (size != null && (!best || size > best.size)) best = { size, label, fraction: fractions[i] };
      });
    }
    return best;
  }, [percolation, meta.strategies]);

  return (
    <div className="section-head">
      <h2 id="collapse-title">{sentence(totalWord)} ways to take it apart</h2>
      <TextBlock
        notes={
          <>
            <Sidenote title="Random baseline">
              Random removal is run {randomTrials} times in different orders. Flow capacity halves at{" "}
              {percent(randomFlow.halvedAt)} on average
              {randomFlow.ci ? ` (95% CI ${percent(randomFlow.ci[0])} to ${percent(randomFlow.ci[1])})` : ""}.
            </Sidenote>
            <Sidenote title="Reading the race">
              {batchShare ? `Each step removes ${percent(batchShare, 0)} of the cell types still present. ` : ""}
              The gray band spans the lowest and highest values over the {randomTrials} random orders, and the dashed
              line is one of those runs. Gray squares on the maps are types cut off from every sensory type.
              {avalanche && avalanche.size > 1000
                ? ` The largest single step, under ${avalanche.label} at ${percent(avalanche.fraction)} removed, cuts ${count(avalanche.size)} types off at once.`
                : ""}
            </Sidenote>
            <Sidenote title="Area under the curve">
              Random removal scores {fixed(randomFlow.auc, 3)} on flow capacity and {fixed(randomPairs.auc, 3)} on
              reachable pairs. The table after the figure gives both for every strategy.
            </Sidenote>
          </>
        }
      >
        <p>
          The {totalWord} attacks run side by side on the same {count(meta.graph.cell_types)} cell types, scored by the
          two measures defined above.
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

/** Summary table of AUC and halving points per strategy, ordered by the flow halving point. */
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
              <th scope="col" className="num">
                Reachable pairs halve at
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
                    <td className="num">{pairs.halvedAt != null ? percent(pairs.halvedAt) : "Not within the range"}</td>
                  </tr>
                );
              })}
          </tbody>
        </table>
      </div>
    </details>
  );
});
