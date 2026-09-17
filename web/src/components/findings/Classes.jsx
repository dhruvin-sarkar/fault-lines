import { useState } from "react";
import { Finding, Pending, useResult } from "./Finding.jsx";
import { useRovingRows } from "./useRovingRows.js";
import { ChartFrame, Row, Tooltip } from "../Chart.jsx";
import { Figure, Segmented, Sidenote, TextBlock } from "../ui.jsx";
import { useReducedMotion, useWidth } from "../../lib/hooks.js";
import { linear } from "../../lib/scales.js";
import { count, percent, pValue, sentence, superclassName } from "../../lib/format.js";
import "../../styles/findings-a.css";

const ID = "classes";
const TITLE = "Losing a class";
const SIGNIFICANCE = 0.05;
const SORTS = [
  { value: "flow_drop", label: "Flow lost" },
  { value: "excess_over_random", label: "Difference from random" },
];
const TICKS = [0, 0.25, 0.5, 0.75, 1];

const points = (v) => `${v >= 0 ? "+" : "−"}${Math.abs(100 * v).toFixed(1)} points`;

export default function Classes() {
  const { data, missing } = useResult("structure.json");
  if (missing) return <Pending id={ID} title={TITLE} />;
  return data ? <ClassesView data={data} /> : null;
}

/** Rendered only once the data exists, so the width observer attaches to a mounted node. */
function ClassesView({ data }) {
  const [sort, setSort] = useState("flow_drop");
  const [active, setActive] = useState(null);
  const [wrapRef, width] = useWidth();
  const reduced = useReducedMotion();

  const rows = data.superclass_impact;
  const ordered = [...rows].sort((a, b) => b[sort] - a[sort]);
  const order = Object.fromEntries(ordered.map((r, i) => [r.superclass, i]));
  const top = [...rows].sort((a, b) => b.flow_drop - a.flow_drop)[0];
  const isAbove = (r) => r.p_value < SIGNIFICANCE && r.excess_over_random > 0;
  const above = rows.filter(isAbove);
  const below = [...rows].sort((a, b) => a.excess_over_random - b.excess_over_random)[0];

  const wide = width >= 560;
  const rowH = wide ? 32 : 48;
  const margin = { top: 30, right: 16, bottom: 46, left: wide ? 170 : 6 };
  const height = rows.length * rowH + margin.top + margin.bottom;
  const activeRow = active ? rows.find((r) => r.superclass === active) : null;
  const dotY = wide ? rowH / 2 : rowH - 13;
  const rowProps = useRovingRows(
    ordered.map((r) => r.superclass),
    setActive,
  );

  return (
    <Finding
      id={ID}
      title={TITLE}
      stat={percent(top.flow_drop)}
      statLabel={`of flow capacity lost when all ${count(top.types)} ${superclassName(top.superclass)} types are removed`}
    >
      <TextBlock
        notes={
          <>
            <Sidenote title="The comparison">
              For each superclass, {count(data.random_draws)} random sets of the same number of types were removed. p is
              the share of those sets that lose at least as much flow capacity, uncorrected.
            </Sidenote>
            <Sidenote title="Included classes">
              The {rows.length} superclasses with at least {count(data.superclass_threshold)} cell types.
            </Sidenote>
          </>
        }
      >
        <p>
          Removing an entire superclass at once asks which kinds of neuron sensory-to-motor routing depends on. Taking
          out the {count(top.types)} {superclassName(top.superclass)} types costs {percent(top.flow_drop)} of flow
          capacity, where random sets of the same size cost {percent(top.random_mean)}.
        </p>
        <p>
          Of the {rows.length} superclasses, {above.length} lose more than their random sets at p &lt; {SIGNIFICANCE}.
          {below.excess_over_random < 0 &&
            ` The largest shortfall runs the other way: the ${count(below.types)} ${superclassName(below.superclass)} types cost ${percent(below.flow_drop)}, less than the ${percent(below.random_mean)} lost by random sets of that size, so their share of routing is smaller than their share of types.`}
        </p>
      </TextBlock>

      <Figure
        className={reduced ? "fa-still" : ""}
        title="Flow capacity lost per superclass, against random sets of the same size"
        controls={<Segmented label="Order superclasses by" options={SORTS} value={sort} onChange={setSort} />}
        caption={
          <>
            Each row removes every cell type of one superclass. The dot is the flow capacity lost; the tick is the mean
            loss of {count(data.random_draws)} same-size random sets, and the bar between them shows the difference.
            Filled dots on a dark bar lose significantly more than random (p &lt; {SIGNIFICANCE}); open dots on a light
            bar do not. Hover a row, or focus the chart and use the arrow keys, for type and neuron counts.
          </>
        }
      >
        <div className="legend fa-legend" aria-hidden="true">
          <span>
            <svg width="12" height="12" viewBox="-6 -6 12 12">
              <circle r="5" className="fa-glyph-ink" />
            </svg>
            Lost, p &lt; {SIGNIFICANCE}
          </span>
          <span>
            <svg width="12" height="12" viewBox="-6 -6 12 12">
              <circle r="4.25" className="fa-glyph-ring" style={{ stroke: "var(--ink)" }} />
            </svg>
            Lost, not significant
          </span>
          <span>
            <svg width="8" height="16" viewBox="-4 -8 8 16">
              <path d="M0 -7V7" className="fa-glyph-line" style={{ stroke: "var(--ink-2)" }} />
            </svg>
            Random sets, mean
          </span>
        </div>
        <div ref={wrapRef}>
          <ChartFrame
            height={height}
            margin={margin}
            role="group"
            label={`Use the arrow keys to move between superclasses. Flow capacity lost when each of ${rows.length} superclasses is removed, compared with random sets of the same size. Highest: ${sentence(superclassName(top.superclass))}, ${percent(top.flow_drop)}.`}
            onPointer={(_x, y) => {
              const i = Math.floor(y / rowH);
              setActive(i >= 0 && i < ordered.length ? ordered[i].superclass : null);
            }}
            onLeave={() => setActive(null)}
            overlay={({ margin: m, width: w }) => {
              if (!activeRow) return null;
              const x = linear([0, 1], [0, w - m.left - m.right]);
              return (
                <Tooltip
                  x={m.left + x(Math.max(activeRow.flow_drop, activeRow.random_mean))}
                  y={m.top + order[activeRow.superclass] * rowH + dotY - 10}
                  width={w}
                >
                  <div className="fa-tip">
                    <strong>{sentence(superclassName(activeRow.superclass))}</strong>
                    <span className="fa-tip-sub">
                      {count(activeRow.types)} types, {count(activeRow.neurons)} neurons
                    </span>
                    <Row label="Flow capacity lost" value={percent(activeRow.flow_drop)} />
                    <Row label="Random sets, mean" value={percent(activeRow.random_mean)} />
                    <Row label="Difference" value={points(activeRow.excess_over_random)} />
                    <Row label="Routes left" value={count(activeRow.flow_after)} />
                    <Row label="p, upper tail" value={pValue(activeRow.p_value)} />
                  </div>
                </Tooltip>
              );
            }}
          >
            {(inner) => {
              const x = linear([0, 1], [0, inner.width]);
              return (
                <g>
                  {TICKS.map((t) => (
                    <g key={t} className="tick" transform={`translate(${x(t)},0)`}>
                      <line y1={-4} y2={inner.height} />
                      <text y={-12} textAnchor="middle">
                        {percent(t, 0)}
                      </text>
                    </g>
                  ))}
                  <g transform={`translate(0,${inner.height})`}>
                    <line className="axis-line" x2={inner.width} />
                    {TICKS.map((t) => (
                      <g key={t} transform={`translate(${x(t)},0)`}>
                        <line className="fa-axis-tick" y2={5} />
                        <text y={18} textAnchor="middle">
                          {percent(t, 0)}
                        </text>
                      </g>
                    ))}
                    <text className="axis-title" x={inner.width} y={38} textAnchor="end">
                      Flow capacity lost
                    </text>
                  </g>
                  {rows.map((r) => {
                    const significant = isAbove(r);
                    const on = active === r.superclass;
                    const xo = x(r.flow_drop);
                    const xr = x(r.random_mean);
                    return (
                      <g
                        key={r.superclass}
                        {...rowProps(r.superclass)}
                        className="fa-move fa-focusable"
                        style={{ transform: `translateY(${order[r.superclass] * rowH}px)` }}
                        role="img"
                        aria-label={`${sentence(superclassName(r.superclass))}: ${percent(r.flow_drop)} lost; random sets ${percent(r.random_mean)}; p ${pValue(r.p_value)}`}
                      >
                        <rect
                          className={`fa-band${on ? " is-on" : ""}`}
                          x={-margin.left + 2}
                          width={inner.width + margin.left + margin.right - 4}
                          y={1}
                          height={rowH - 2}
                          rx={3}
                        />
                        <text
                          className="fa-row-label"
                          x={wide ? -12 : 0}
                          y={wide ? rowH / 2 : 13}
                          dy="0.32em"
                          textAnchor={wide ? "end" : "start"}
                        >
                          {sentence(superclassName(r.superclass))}
                        </text>
                        <line className="fa-track" x1={0} x2={inner.width} y1={dotY} y2={dotY} />
                        <line
                          x1={xr}
                          x2={xo}
                          y1={dotY}
                          y2={dotY}
                          style={{
                            stroke: significant ? "var(--ink-2)" : "var(--rule-strong)",
                            strokeWidth: significant ? 3 : 2,
                          }}
                        />
                        <path d={`M${xr} ${dotY - 7}V${dotY + 7}`} style={{ stroke: "var(--ink-2)", strokeWidth: 2 }} />
                        {significant ? (
                          <circle cx={xo} cy={dotY} r={on ? 6.5 : 5.5} className="fa-glyph-ink" />
                        ) : (
                          <circle cx={xo} cy={dotY} r={on ? 6 : 4.75} className="fa-ring" style={{ stroke: "var(--ink)" }} />
                        )}
                      </g>
                    );
                  })}
                </g>
              );
            }}
          </ChartFrame>
        </div>
      </Figure>

      <details className="more">
        <summary>Superclass removals as a table</summary>
        <div className="table-wrap">
          <table className="data">
            <thead>
              <tr>
                <th>Superclass</th>
                <th className="num">Types</th>
                <th className="num">Neurons</th>
                <th className="num">Flow lost</th>
                <th className="num">Random sets</th>
                <th className="num">Difference</th>
                <th className="num">p</th>
              </tr>
            </thead>
            <tbody>
              {ordered.map((r) => (
                <tr key={r.superclass}>
                  <td>{sentence(superclassName(r.superclass))}</td>
                  <td className="num">{count(r.types)}</td>
                  <td className="num">{count(r.neurons)}</td>
                  <td className="num">{percent(r.flow_drop)}</td>
                  <td className="num">{percent(r.random_mean)}</td>
                  <td className="num">{points(r.excess_over_random)}</td>
                  <td className="num">{pValue(r.p_value)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </details>
    </Finding>
  );
}
