import { useEffect, useMemo, useRef, useState } from "react";
import { Finding } from "./Finding.jsx";
import { coarsePointer, useRovingRows } from "./useRovingRows.js";
import { ChartFrame, Row, Tooltip, YAxis, spreadLabels } from "../Chart.jsx";
import { Figure, Segmented, Sidenote, TextBlock } from "../ui.jsx";
import { useData } from "../../lib/data.js";
import { useReducedMotion, useWidth } from "../../lib/hooks.js";
import { linear } from "../../lib/scales.js";
import { count, fixed, pValue, sentence, superclassName } from "../../lib/format.js";
import "../../styles/findings-a.css";

const ID = "literature";
const TITLE = "Agreement with experiments";
const CONTROL = "MN9";

/** The published name with the type's own name removed, e.g. "DNa12" for aSP22 (DNa12); empty when they match. */
function alias(name, published) {
  if (!published.toLowerCase().startsWith(name.toLowerCase())) return published;
  return published.slice(name.length).trim().replace(/^\((.*)\)$/, "$1");
}

const METRICS = [
  { value: "sm_betweenness", label: "Sensory-motor betweenness", text: "sensory-motor betweenness" },
  { value: "betweenness", label: "Betweenness", text: "betweenness" },
  { value: "flow_drop", label: "Flow lost alone", text: "the flow capacity lost when the type is removed alone" },
];
const EVIDENCE = {
  S: "Activation evokes it",
  N: "Silencing impairs it",
  "S+N": "Activation evokes it, silencing impairs it",
};
const MARGIN = { top: 34, right: 8, bottom: 14, left: 40 };
const HEIGHT = 480;
// Label spacing: tight for a mouse, a full touch target on touch screens.
const LABEL_GAP = 17;
const TOUCH_GAP = 40;
const GAP = 12;

const ordinal = (value) => {
  const n = Math.round(value);
  const tail = n % 100;
  if (tail >= 11 && tail <= 13) return `${n}th`;
  return `${n}${{ 1: "st", 2: "nd", 3: "rd" }[n % 10] ?? "th"}`;
};

/** Dots at their percentile, pushed sideways where they would overlap, with labels spread to stay apart. */
function arrange(curated, metric, innerHeight, labelGap) {
  const y = linear([0, 100], [innerHeight, 0]);
  const entries = Object.entries(curated)
    .map(([name, info]) => ({ name, pct: info[`${metric}_percentile`] }))
    .sort((a, b) => b.pct - a.pct || a.name.localeCompare(b.name));
  const placed = [];
  for (const e of entries) {
    const dotY = y(e.pct);
    let dx = 0;
    for (let k = 0; k < 40; k += 1) {
      dx = k === 0 ? 0 : (k % 2 ? 1 : -1) * Math.ceil(k / 2) * GAP;
      if (placed.every((p) => Math.hypot(p.dx - dx, p.dotY - dotY) >= GAP)) break;
    }
    placed.push({ ...e, dotY, dx });
  }
  const labels = spreadLabels(placed.map((p) => ({ name: p.name, y: p.dotY })), labelGap, 6, innerHeight - 2);
  const labelY = Object.fromEntries(labels.map((l) => [l.name, l.y]));
  return Object.fromEntries(placed.map((p) => [p.name, { dx: p.dx, dotY: p.dotY, labelY: labelY[p.name], pct: p.pct }]));
}

/** Interpolates between successive layouts when `key` changes; jumps when only the size changes. */
function useTween(target, key, reduced, duration = 560) {
  const [state, setState] = useState(target);
  const last = useRef({ key, value: target });
  useEffect(() => {
    const origin = last.current.value;
    if (reduced || last.current.key === key) {
      last.current = { key, value: target };
      setState(target);
      return undefined;
    }
    last.current.key = key;
    const start = performance.now();
    let frame;
    const step = (now) => {
      const t = Math.min(1, (now - start) / duration);
      const e = 1 - (1 - t) ** 3;
      const next = {};
      for (const [name, b] of Object.entries(target)) {
        const a = origin[name] ?? b;
        next[name] = { ...b, dx: a.dx + (b.dx - a.dx) * e, dotY: a.dotY + (b.dotY - a.dotY) * e, labelY: a.labelY + (b.labelY - a.labelY) * e };
      }
      last.current.value = next;
      setState(next);
      if (t < 1) frame = requestAnimationFrame(step);
    };
    frame = requestAnimationFrame(step);
    return () => cancelAnimationFrame(frame);
  }, [target, key, reduced, duration]);
  return state;
}

export default function Literature() {
  const { data } = useData("literature.json");
  return data ? <LiteratureView data={data} /> : null;
}

/** Rendered only once the data exists, so the width observer attaches to a mounted node. */
function LiteratureView({ data }) {
  const [metric, setMetric] = useState("sm_betweenness");
  const [hover, setHover] = useState(null);
  const [wrapRef, width] = useWidth();
  const reduced = useReducedMotion();
  const labelGap = coarsePointer() ? TOUCH_GAP : LABEL_GAP;
  const height = Math.max(HEIGHT, Object.keys(data.curated_types).length * labelGap + MARGIN.top + MARGIN.bottom + 12);
  const innerHeight = height - MARGIN.top - MARGIN.bottom;

  const layouts = useMemo(
    () => Object.fromEntries(METRICS.map((m) => [m.value, arrange(data.curated_types, m.value, innerHeight, labelGap)])),
    [data, innerHeight, labelGap],
  );
  const positions = useTween(layouts[metric], metric, reduced);
  const rowProps = useRovingRows(Object.keys(layouts[metric]), setHover);

  const curated = data.curated_types;
  const alpha = data.alpha;
  const test = data.tests.primary[metric];
  const control = data.tests.with_positive_control?.[metric];
  const swap = data.tests.DNp71_for_DNp09?.[metric];
  const primary = data.tests.primary.sm_betweenness;
  const metricText = METRICS.find((m) => m.value === metric).text;
  const nCurated = test.n_curated;
  const examples = ["DNp01", "MDN"].filter((name) => curated[name]);
  const controlInfo = curated[CONTROL];

  const spread = Object.values(layouts).flatMap((l) => Object.values(l).map((p) => p.dx));
  const left = Math.max(0, -Math.min(...spread));
  const right = Math.max(0, ...spread);
  const cx = left + 12;
  const labelX = cx + right + 34;
  const innerWidth = width - MARGIN.left - MARGIN.right;
  const roomForNames = innerWidth - labelX > 210;

  const zeroCost = Object.entries(curated).filter(([name, info]) => name !== CONTROL && info.flow_drop === 0).length;
  const hovered = hover && curated[hover];
  const hoveredPos = hover && positions[hover];

  function pick(x, y) {
    let best = null;
    let bestDistance = Infinity;
    for (const [name, p] of Object.entries(positions)) {
      const d = x < labelX - 12 ? Math.hypot(cx + p.dx - x, p.dotY - y) : Math.abs(p.labelY - y);
      if (d < bestDistance) {
        bestDistance = d;
        best = name;
      }
    }
    setHover(bestDistance <= (x < labelX - 12 ? 14 : labelGap / 2) ? best : null);
  }

  return (
    <Finding
      id={ID}
      title={TITLE}
      stat={ordinal(primary.median_percentile)}
      statLabel={`median percentile of the ${primary.n_curated} behaviorally validated cell types in sensory-motor betweenness`}
    >
      <TextBlock
        notes={
          <>
            {controlInfo && (
              <Sidenote title="Positive control">
                <span className="id">{CONTROL}</span> drives {controlInfo.behavior}.
                As a motor type it ends sensory-to-motor routes rather than relaying them, so it scores zero on
                sensory-motor betweenness and removing it alone costs a single route. It is drawn as an open ring and
                left out of the test, as pre-registered
                {control ? `; including it gives AUC ${fixed(control.auc, 2)}, p = ${pValue(control.p_value)}` : ""}.
              </Sidenote>
            )}
            <Sidenote title="Not a random sample">
              Well-studied neurons were found because they are large, accessible or have striking phenotypes, so
              agreement here cannot show that the ranking finds essential neurons in general.
              {swap &&
                ` Scoring DNp71, which also carries the DNp09 label, in place of DNp09 gives AUC ${fixed(swap.auc, 2)}, p = ${pValue(swap.p_value)}.`}
            </Sidenote>
          </>
        }
      >
        <p>
          Published activation and silencing experiments tie {nCurated} cell types to specific behaviors
          {examples.length > 0 && (
            <>
              , among them{" "}
              {examples.map((name, i) => (
                <span key={name}>
                  {i > 0 && " and "}the {curated[name].published_name} (<span className="id">{name}</span>) in{" "}
                  {curated[name].behavior}
                </span>
              ))}
            </>
          )}
          . None was tested here; the list and a one-sided Mann-Whitney test were fixed before any structural score was
          computed.
        </p>
        <p>
          The question is whether a purely structural ranking puts these types high. Under the primary score,
          sensory-motor betweenness, their median percentile is the {ordinal(primary.median_percentile)} (AUC{" "}
          {fixed(primary.auc, 2)}, p = {pValue(primary.p_value)}).
        </p>
      </TextBlock>

      <Figure
        className={reduced ? "fa-still" : ""}
        title="Where behaviorally validated cell types rank among all cell types"
        controls={
          <Segmented label="Score" options={METRICS.map(({ value, label }) => ({ value, label }))} value={metric} onChange={setMetric} />
        }
        caption={
          <>
            Each dot is one curated cell type at its percentile among all {count(test.n_curated + test.n_other)} types
            under the chosen score; dots at nearly the same percentile sit side by side. The dashed line is the 50th
            percentile, where a type drawn at random would sit on average. AUC is the probability that a curated type
            outranks a randomly chosen other type. Hover a type, or focus the chart and use the arrow keys, for its behavior and all three percentiles.
          </>
        }
      >
        <div className="fa-lit">
          <div ref={wrapRef}>
            <ChartFrame
              height={height}
              margin={MARGIN}
              role="group"
              label={`Percentile of ${nCurated} behaviorally validated cell types and one positive control among all cell types, by ${metricText}. Use the arrow keys to move between types.`}
              onPointer={pick}
              onLeave={() => setHover(null)}
              overlay={({ margin: m, width: w }) =>
                hovered && hoveredPos ? (
                  <Tooltip x={m.left + cx + hoveredPos.dx} y={m.top + hoveredPos.dotY - 8} width={w}>
                    <div className="fa-tip">
                      <strong>
                        <span className="id">{hover}</span>
                        {alias(hover, hovered.published_name) && `, ${alias(hover, hovered.published_name)}`}
                      </strong>
                      <span className="fa-tip-sub">
                        {sentence(hovered.behavior)}
                        {hover === CONTROL && "; positive control, not in the test"}
                      </span>
                      <Row label="Evidence" value={EVIDENCE[hovered.evidence] ?? hovered.evidence} />
                      {METRICS.map((m2) => (
                        <Row key={m2.value} label={m2.label} value={ordinal(hovered[`${m2.value}_percentile`])} />
                      ))}
                      <Row label="Neurons" value={count(hovered.n_neurons)} />
                      <Row label="Superclass" value={sentence(superclassName(hovered.superclass))} />
                    </div>
                  </Tooltip>
                ) : null
              }
            >
              {(inner) => {
                const y = linear([0, 100], [inner.height, 0]);
                return (
                  <g>
                    <YAxis
                      scale={y}
                      ticks={[0, 25, 50, 75, 100]}
                      width={labelX - 22}
                      title="Percentile among all cell types"
                      inset={MARGIN.left}
                    />
                    <line className="fa-ref" x1={0} x2={labelX - 22} y1={y(50)} y2={y(50)} />
                    {Object.entries(positions).map(([name, p]) => {
                      const info = curated[name];
                      const isControl = name === CONTROL;
                      const dim = hover && hover !== name;
                      const dotX = cx + p.dx;
                      const text = isControl ? "positive control" : alias(name, info.published_name) || null;
                      return (
                        <g
                          key={name}
                          {...rowProps(name)}
                          role="img"
                          aria-label={`${name}, ${info.published_name}, ${info.behavior}: ${ordinal(p.pct)} percentile`}
                          style={{ opacity: dim ? 0.3 : 1, transition: "opacity 160ms" }}
                        >
                          <rect
                            className={`fa-band${hover === name ? " is-on" : ""}`}
                            x={labelX - 10}
                            y={p.labelY - (labelGap - 2) / 2}
                            width={Math.max(40, inner.width - labelX + 10)}
                            height={labelGap - 2}
                            rx={3}
                          />
                          <path className="fa-leader" d={`M${dotX + 7} ${p.dotY}L${labelX - 16} ${p.dotY}L${labelX - 6} ${p.labelY}`} />
                          {isControl ? (
                            <circle cx={dotX} cy={p.dotY} r={4.5} className="fa-ring" style={{ stroke: "var(--ink)" }} />
                          ) : (
                            <circle cx={dotX} cy={p.dotY} r={hover === name ? 6 : 4.75} className="fa-glyph-ink" />
                          )}
                          <text className="fa-type" x={labelX} y={p.labelY} dy="0.32em">
                            {name}
                            {text && (roomForNames || isControl) && (
                              <tspan className="fa-type-name" dx={7}>
                                {text}
                              </tspan>
                            )}
                          </text>
                        </g>
                      );
                    })}
                  </g>
                );
              }}
            </ChartFrame>
          </div>

          <div>
            <dl className="facts">
              <div>
                <dt>AUC</dt>
                <dd>{fixed(test.auc, 2)}</dd>
              </div>
              <div>
                <dt>p, one-sided Mann-Whitney U</dt>
                <dd>{pValue(test.p_value)}</dd>
              </div>
              <div>
                <dt>Median percentile</dt>
                <dd>{ordinal(test.median_percentile)}</dd>
              </div>
              <div>
                <dt>Curated types, against {count(test.n_other)} others</dt>
                <dd>{test.n_curated}</dd>
              </div>
            </dl>
            <p className="fa-lit-reading">
              Under {metricText}, a curated type outranks a randomly chosen other type with probability{" "}
              {fixed(test.auc, 2)}; p = {pValue(test.p_value)} is {test.p_value < alpha ? "below" : "above"} the{" "}
              {fixed(alpha, 2)} threshold.
              {metric === "flow_drop" &&
                ` ${zeroCost} of ${nCurated} curated types cost no flow capacity when removed alone, so they share one tied percentile with most other types.`}
            </p>
          </div>
        </div>
      </Figure>

      <details className="more">
        <summary>Curated cell types as a table</summary>
        <div className="table-wrap">
          <table className="data">
            <thead>
              <tr>
                <th>Type</th>
                <th>Published name</th>
                <th>Behavior</th>
                <th>Evidence</th>
                <th className="num">Sensory-motor betweenness percentile</th>
                <th className="num">Betweenness percentile</th>
                <th className="num">Flow lost alone percentile</th>
              </tr>
            </thead>
            <tbody>
              {Object.entries(curated).map(([name, info]) => (
                <tr key={name}>
                  <td>
                    <span className="id">{name}</span>
                    {name === CONTROL && " (positive control)"}
                  </td>
                  <td>{info.published_name}</td>
                  <td>{sentence(info.behavior)}</td>
                  <td>{EVIDENCE[info.evidence] ?? info.evidence}</td>
                  <td className="num">{fixed(info.sm_betweenness_percentile, 1)}</td>
                  <td className="num">{fixed(info.betweenness_percentile, 1)}</td>
                  <td className="num">{fixed(info.flow_drop_percentile, 1)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </details>
    </Finding>
  );
}
