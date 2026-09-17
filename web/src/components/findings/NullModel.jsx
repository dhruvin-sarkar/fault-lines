import { useMemo, useState } from "react";
import { Finding, useResult } from "./Finding.jsx";
import { inkColor as ink } from "./marks.jsx";
import { useRovingRows } from "./useRovingRows.js";
import { ChartFrame, Row, Tooltip } from "../Chart.jsx";
import { Figure, Segmented, Sidenote, TextBlock } from "../ui.jsx";
import { useReducedMotion, useWidth } from "../../lib/hooks.js";
import { linear, log, niceTicks } from "../../lib/scales.js";
import { count, fixed, numberWord, sentence, signedFixed } from "../../lib/format.js";
import "../../styles/findings-a.css";

const ID = "null-model";
const NEUTRAL_TITLE = "Against degree-preserving randomizations";
const METRICS = [
  { value: "auc_flow", label: "Flow capacity" },
  { value: "auc_reachability", label: "Reachable pairs" },
];
const P_TICKS = [0.001, 0.002, 0.005, 0.01, 0.02, 0.05, 0.1, 0.2, 0.5, 1];
// Ensemble size fixed in the pre-registration; the size actually scored is read from nulls.json.
const PLANNED_NULLS = 200;

/** p to four decimals, the resolution of an empirical p over a few hundred graphs. */
const p4 = (p) => fixed(p, 4);

/**
 * Short and full wording of one test's reading. Significance is only read when the ensemble is the registered one;
 * a non-significant result is reported as such, in the registered direction only.
 */
function reading(test, complete) {
  if (!complete) return { short: "Ensemble incomplete", narrow: "Incomplete", yes: false };
  if (test.verdict === "more_fragile") {
    return { short: "Significantly more fragile", narrow: "Significant", yes: true };
  }
  if (test.verdict === "above_null_mean") {
    return { short: "Not significant, above the randomized mean", narrow: "Not significant", yes: false };
  }
  return { short: "Not significant", narrow: "Not significant", yes: false };
}

/** The chapter title describes the measured outcome and nothing beyond it. */
function titleFor(yes, total, complete) {
  if (!complete) return NEUTRAL_TITLE;
  if (yes === total) return `More fragile than degree-preserving randomizations under all ${numberWord(total)} orders`;
  if (yes > 0) {
    return `More fragile than degree-preserving randomizations under ${numberWord(yes)} of ${numberWord(total)} orders`;
  }
  return "Not significantly more fragile than degree-preserving randomizations";
}

const joinNames = (names) =>
  names.length <= 1 ? names.join("") : `${names.slice(0, -1).join(", ")} and ${names[names.length - 1]}`;

/** "p = a" when every p is the same, "p from a to b" otherwise. */
function pRange(tests) {
  const ps = tests.map((t) => t.p_value);
  const lo = Math.min(...ps);
  const hi = Math.max(...ps);
  return lo === hi ? `p = ${p4(lo)}` : `p from ${p4(lo)} to ${p4(hi)}`;
}

function Marker({ id, x, r = 5.5 }) {
  if (id === "random") {
    return <path d={`M${x} ${-r - 1}L${x + r + 1} 0L${x} ${r + 1}L${x - r - 1} 0Z`} className="fa-diamond" style={{ stroke: ink(id) }} />;
  }
  return <circle cx={x} r={r} style={{ fill: ink(id) }} />;
}

function TestRows({ test, n }) {
  return (
    <>
      <Row label="Real AUC" value={fixed(test.real, 4)} />
      <Row label="Randomized mean" value={`${fixed(test.null_mean, 4)} ± ${fixed(test.null_sd, 4)}`} />
      <Row label="Randomized range" value={`${fixed(test.null_min, 3)} to ${fixed(test.null_max, 3)}`} />
      <Row label="At or below real" value={`${count(test.n_at_or_below_real)} of ${count(n)}`} />
      <Row label="z" value={signedFixed(test.z_score, 1)} />
      <Row label="p, one-sided" value={p4(test.p_value)} />
    </>
  );
}

/** One row per removal order: its one-sided p on a log axis, the corrected threshold, and the reading. */
function Ladder({ strategies, tests, n, alpha, floor, complete, metricLabel }) {
  const [wrapRef, width] = useWidth();
  const [active, setActive] = useState(null);
  const wide = width >= 720;
  const rowH = wide ? 42 : 60;
  const margin = { top: 40, right: wide ? 280 : 14, bottom: 46, left: wide ? 200 : 6 };
  const keys = strategies.map((s) => s.id);
  const rowProps = useRovingRows(keys, setActive);
  const height = margin.top + margin.bottom + rowH * strategies.length;
  const ps = strategies.map((s) => tests[s.id].p_value);
  const domain = [Math.min(floor, alpha, ...ps) / 1.6, 1];
  const center = (i) => (wide ? i * rowH + rowH / 2 : i * rowH + rowH - 16);
  const activeIndex = keys.indexOf(active);

  return (
    <div ref={wrapRef}>
      <ChartFrame
        height={height}
        margin={margin}
        role="group"
        label={`One-sided p-value of the ${metricLabel.toLowerCase()} test for each of ${strategies.length} removal orders against the corrected threshold of ${p4(alpha)}, on a logarithmic axis. Use the arrow keys to move between orders.`}
        onPointer={(_x, y) => {
          const i = Math.floor(y / rowH);
          setActive(i >= 0 && i < keys.length ? keys[i] : null);
        }}
        onLeave={() => setActive(null)}
        overlay={({ margin: m, width: w }) => {
          if (activeIndex < 0) return null;
          const s = strategies[activeIndex];
          const test = tests[s.id];
          const scale = log(domain, [0, w - m.left - m.right]);
          return (
            <Tooltip x={m.left + scale(test.p_value)} y={m.top + center(activeIndex) - 12} width={w}>
              <div className="fa-tip">
                <strong>{sentence(s.label)}</strong>
                <span className="fa-tip-sub">{reading(test, complete).short}</span>
                <TestRows test={test} n={n} />
              </div>
            </Tooltip>
          );
        }}
      >
        {(inner) => {
          const x = log(domain, [0, inner.width]);
          const ticks = P_TICKS.filter((t) => t >= domain[0] && t <= 1).filter(
            (t) => wide || [0.001, 0.01, 0.1, 1].includes(t) || t === 0.005,
          );
          const ax = x(alpha);
          return (
            <g>
              <rect className="fn-zone" x={0} y={-8} width={ax} height={inner.height + 8} />
              {ticks.map((t) => (
                <line key={t} className="fn-grid" x1={x(t)} x2={x(t)} y1={-8} y2={inner.height} />
              ))}
              <line className="fn-threshold" x1={ax} x2={ax} y1={-24} y2={inner.height} />
              <text className="fn-threshold-label" x={ax + 6} y={-14}>
                Threshold 0.05 / {strategies.length} = {p4(alpha)}
              </text>
              <g transform={`translate(0,${inner.height})`}>
                <line className="axis-line" x2={inner.width} />
                {ticks.map((t) => (
                  <g key={t} transform={`translate(${x(t)},0)`}>
                    <line className="fa-axis-tick" y2={5} />
                    <text y={18} textAnchor="middle">
                      {String(t)}
                    </text>
                  </g>
                ))}
                <text className="axis-title" x={inner.width} y={38} textAnchor="end">
                  One-sided p, logarithmic
                </text>
              </g>
              {strategies.map((s, i) => {
                const test = tests[s.id];
                const r = reading(test, complete);
                const cy = center(i);
                const px = x(test.p_value);
                const flip = px > inner.width - 90;
                const labelY = wide ? cy : i * rowH + 18;
                return (
                  <g
                    key={s.id}
                    {...rowProps(s.id)}
                    role="img"
                    aria-label={`${sentence(s.label)}: p = ${p4(test.p_value)}, ${r.short.toLowerCase()}. Real AUC ${fixed(test.real, 3)}, randomized mean ${fixed(test.null_mean, 3)}, ${count(test.n_at_or_below_real)} of ${count(n)} randomized graphs at or below the real score.`}
                  >
                    <rect
                      className={`fa-band${active === s.id ? " is-on" : ""}`}
                      x={-margin.left + 2}
                      y={i * rowH + 1}
                      width={inner.width + margin.left + margin.right - 4}
                      height={rowH - 2}
                      rx={3}
                    />
                    <line className="fa-track" x1={0} x2={inner.width} y1={cy} y2={cy} />
                    <g transform={`translate(0,${cy})`}>
                      <Marker id={s.id} x={px} />
                      <text className="fa-value fn-halo" x={flip ? px - 11 : px + 11} y={4} textAnchor={flip ? "end" : "start"}>
                        {p4(test.p_value)}
                      </text>
                    </g>
                    <text className="fa-row-label" x={wide ? -margin.left + 12 : 0} y={labelY} dy={wide ? "0.32em" : 0}>
                      {sentence(s.label)}
                    </text>
                    <text
                      className={`fn-verdict${r.yes ? " is-yes" : ""}`}
                      x={wide ? inner.width + 18 : inner.width}
                      y={labelY}
                      dy={wide ? "0.32em" : 0}
                      textAnchor={wide ? "start" : "end"}
                    >
                      {wide ? r.short : r.narrow}
                    </text>
                  </g>
                );
              })}
            </g>
          );
        }}
      </ChartFrame>
    </div>
  );
}

const STEPS = { ArrowRight: 1, ArrowUp: 1, ArrowLeft: -1, ArrowDown: -1 };

/** One removal order: randomized-graph scores as a histogram with the real score as a line. */
function Panel({ strategy, test, n, complete, metricLabel }) {
  const [hover, setHover] = useState(null);
  const { lo, step, counts, quantiles } = test.distribution;
  const bins = counts.length;
  const peak = Math.max(1, ...counts);
  const hi = lo + bins * step;
  const domain = useMemo(() => {
    const a = Math.min(lo, test.real);
    const b = Math.max(hi, test.real);
    const pad = (b - a) * 0.06 || 0.005;
    return [a - pad, b + pad];
  }, [lo, hi, test.real]);
  const margin = { top: 24, right: 10, bottom: 28, left: 10 };
  const r = reading(test, complete);
  const median = Math.min(bins - 1, Math.max(0, Math.floor((quantiles[2] - lo) / step)));

  const onKeyDown = (event) => {
    let next = null;
    if (event.key in STEPS) next = Math.max(0, Math.min(bins - 1, (hover ?? median) + STEPS[event.key]));
    else if (event.key === "Home") next = 0;
    else if (event.key === "End") next = bins - 1;
    if (next == null) return;
    event.preventDefault();
    setHover(next);
  };

  return (
    <div className="fa-null">
      <div className="fa-null-head">
        <span>
          <svg width="12" height="12" viewBox="-6 -6 12 12" aria-hidden="true" className="fa-swatch">
            <Marker id={strategy.id} x={0} r={4.5} />
          </svg>
          {sentence(strategy.label)}
        </span>
        <span className={`fa-verdict${r.yes ? " is-yes" : ""}`}>{r.narrow}</span>
      </div>
      <ChartFrame
        height={156}
        margin={margin}
        role="group"
        label={`${metricLabel} AUC of ${count(n)} randomized graphs under ${strategy.label} removal, with the real graph at ${fixed(test.real, 3)}. Focus the histogram and use the arrow keys to read each bar.`}
        onPointer={(px, _y, inner) => {
          const value = linear(domain, [0, inner.width]).invert(px);
          const bin = Math.floor((value - lo) / step);
          setHover(bin >= 0 && bin < bins ? bin : null);
        }}
        onLeave={() => setHover(null)}
        overlay={({ margin: m, width: w, height: h }) => {
          if (hover == null) return null;
          const x = linear(domain, [0, w - m.left - m.right]);
          const from = lo + hover * step;
          return (
            <Tooltip x={m.left + x(from + step / 2)} y={m.top + h - (counts[hover] / peak) * (h - 6) - 4} width={w}>
              <strong>
                AUC {fixed(from, 4)} to {fixed(from + step, 4)}
              </strong>
              <Row label="Randomized graphs" value={count(counts[hover])} />
              <Row label="Real graph" value={fixed(test.real, 4)} />
            </Tooltip>
          );
        }}
      >
        {(inner) => {
          const x = linear(domain, [0, inner.width]);
          const bw = x(lo + step) - x(lo);
          const ticks = niceTicks(domain, inner.width < 240 ? 2 : 3).filter((t) => t >= domain[0] && t <= domain[1]);
          const digits = Math.max(2, Math.min(4, Math.ceil(-Math.log10((domain[1] - domain[0]) / 3))));
          const realX = x(test.real);
          const flip = realX > inner.width - 80;
          return (
            <g
              tabIndex={0}
              className="fa-focusable"
              onKeyDown={onKeyDown}
              onFocus={() => setHover((h) => h ?? median)}
              onBlur={() => setHover(null)}
            >
              <rect className="fn-ring" x={-6} y={-18} width={inner.width + 12} height={inner.height + 22} rx={4} />
              {counts.map((c, i) => (
                <rect
                  key={i}
                  className="fa-move"
                  width={Math.max(1, bw - 1)}
                  height={1}
                  style={{
                    transform: `translate(${x(lo + i * step) + 0.5}px, ${inner.height}px) scaleY(${-(c / peak) * (inner.height - 6)})`,
                    fill: ink(strategy.id),
                    fillOpacity: strategy.id === "random" ? 0.2 : hover == null || hover === i ? 0.85 : 0.3,
                    stroke: ink(strategy.id),
                    strokeWidth: strategy.id === "random" || (hover != null && hover !== i) ? 1 : 0,
                    vectorEffect: "non-scaling-stroke",
                  }}
                />
              ))}
              <g transform={`translate(0,${inner.height})`}>
                <line className="axis-line" x2={inner.width} />
                {ticks.map((t) => (
                  <g key={t} transform={`translate(${x(t)},0)`}>
                    <line className="fa-axis-tick" y2={4} />
                    <text y={17} textAnchor="middle">
                      {fixed(t, digits)}
                    </text>
                  </g>
                ))}
              </g>
              <g className="fa-move" style={{ transform: `translateX(${realX}px)` }}>
                <line className="fa-real" y1={-12} y2={inner.height} />
                <text className="fa-real-label" x={flip ? -6 : 6} y={-4} textAnchor={flip ? "end" : "start"}>
                  Real {fixed(test.real, 3)}
                </text>
              </g>
            </g>
          );
        }}
      </ChartFrame>
      <dl className="fa-null-stats">
        <div>
          <dt>Middle 95%</dt>
          <dd>
            {fixed(quantiles[0], 3)} to {fixed(quantiles[4], 3)}
          </dd>
        </div>
        <div>
          <dt>At or below real</dt>
          <dd>
            {count(test.n_at_or_below_real)} of {count(n)}
          </dd>
        </div>
        <div>
          <dt>z; p</dt>
          <dd>
            {signedFixed(test.z_score, 1)}; {p4(test.p_value)}
          </dd>
        </div>
      </dl>
    </div>
  );
}

function ResultText({ strategies, data, complete }) {
  const n = data.n_nulls;
  const total = strategies.length;
  const flow = (s) => data.strategies[s.id].auc_flow;
  if (!complete) {
    return (
      <p>
        This build reports {count(n)} of the {count(data.n_preregistered)} randomized graphs fixed in advance. The
        registered test needs all of them, so no removal order is read as significant or not significant here; the
        p-values below describe the partial ensemble only.
      </p>
    );
  }
  const yes = strategies.filter((s) => flow(s).verdict === "more_fragile");
  const no = strategies.filter((s) => flow(s).verdict !== "more_fragile");
  const above = no.filter((s) => flow(s).verdict === "above_null_mean");
  const reachYes = strategies.filter((s) => data.strategies[s.id].auc_reachability.verdict === "more_fragile");
  const atFloor = strategies.filter((s) => flow(s).n_at_or_below_real === 0);
  const names = (list) => joinNames(list.map((s) => (s.id === "random" ? "random removal" : s.label)));

  let main;
  if (yes.length === total) {
    main = `Under all ${numberWord(total)} removal orders the real graph scores significantly below its randomizations (${pRange(yes.map(flow))}, each below the Bonferroni threshold of ${p4(data.alpha)}).`;
  } else if (yes.length > 0) {
    main = `Under ${numberWord(yes.length)} of the ${numberWord(total)} removal orders, ${names(yes)}, the real graph scores significantly below its randomizations (${pRange(yes.map(flow))}, below the Bonferroni threshold of ${p4(data.alpha)}). Under ${names(no)} it does not differ significantly in the registered direction (${pRange(no.map(flow))}).`;
  } else {
    main = `Under none of the ${numberWord(total)} removal orders does the real graph score significantly below its randomizations (${pRange(no.map(flow))}, against a Bonferroni threshold of ${p4(data.alpha)}).`;
  }
  const aboveText = above.length
    ? ` Under ${names(above)} the real score lies above the randomized mean.`
    : "";
  const floorText = atFloor.length
    ? ` A p of ${p4(data.p_floor)} is the smallest attainable with ${count(n)} graphs: no randomized graph scored at or below the real one${atFloor.length === total ? " under any order" : ` under ${names(atFloor)}`}.`
    : "";
  return (
    <p>
      {main}
      {aboveText}
      {floorText} Reachable pairs, the secondary measure, give {numberWord(reachYes.length)} of {numberWord(total)}{" "}
      significant results.
    </p>
  );
}

/** The chapter while the randomized ensemble is still computing: the test as registered, and no results. */
function Planned({ meta }) {
  const orders = meta.strategies.length;
  return (
    <Finding id={ID} title={NEUTRAL_TITLE}>
      <TextBlock
        notes={
          <Sidenote title="Degree-preserving randomization">
            Each randomized graph keeps every cell type&apos;s number of inputs and outputs and its output synapse
            total, but reassigns who connects to whom.
          </Sidenote>
        }
      >
        <p>
          Is the real wiring more fragile than its degrees alone would make it? This chapter compares it with{" "}
          {count(PLANNED_NULLS)} degree-preserving randomizations of the graph.
        </p>
        <p>
          All {numberWord(orders)} removal orders are rerun on every randomized graph. For each order, a one-sided test
          asks whether routing in the real graph collapses sooner, at a Bonferroni-corrected threshold of 0.05 /{" "}
          {orders} = {p4(0.05 / orders)}.
        </p>
      </TextBlock>
      <p className="fa-planned" role="status">
        The randomized graphs are still being scored, so no comparison is shown yet. The design was fixed in advance
        and is set out in <a href="#methods-validation">Validation</a>.
      </p>
    </Finding>
  );
}

export default function NullModel({ meta }) {
  const { data, missing } = useResult("nulls.json");
  const [metric, setMetric] = useState("auc_flow");
  const reduced = useReducedMotion();

  if (missing) return <Planned meta={meta} />;
  if (!data) return null;

  const strategies = meta.strategies.filter((s) => data.strategies[s.id]);
  const n = data.n_nulls;
  const complete = n === data.n_preregistered;
  const alpha = data.alpha;
  const yes = strategies.filter((s) => data.strategies[s.id].auc_flow.verdict === "more_fragile");
  const metricLabel = METRICS.find((m) => m.value === metric).label;
  const tests = Object.fromEntries(strategies.map((s) => [s.id, data.strategies[s.id][metric]]));
  const control = <Segmented label="Score" options={METRICS} value={metric} onChange={setMetric} />;

  return (
    <Finding
      id={ID}
      title={titleFor(yes.length, strategies.length, complete)}
      stat={complete ? `${yes.length} of ${strategies.length}` : `${count(n)} of ${count(data.n_preregistered)}`}
      statLabel={
        complete
          ? `removal orders under which routing collapses significantly sooner than in ${count(n)} degree-preserving randomizations`
          : "randomized graphs scored; the registered test needs all of them"
      }
    >
      <TextBlock
        notes={
          <>
            <Sidenote title="Degree-preserving randomization">
              Each randomized graph keeps every cell type&apos;s number of inputs and outputs and its output synapse
              total, but reassigns who connects to whom.
            </Sidenote>
            <Sidenote title="Fixed in advance">
              The direction, the one-sided test, {count(data.n_preregistered)} randomized graphs and the Bonferroni
              threshold of {p4(alpha)} were registered before any randomized graph was scored. With {count(n)} graphs the
              smallest attainable p is {p4(data.p_floor)}.
            </Sidenote>
          </>
        }
      >
        <p>
          Degree-preserving randomizations keep how many partners every cell type has and scramble who connects to
          whom. If the real graph is no more fragile than they are, its fragility follows from the
          degree sequence alone. Every removal order was rerun on each randomized graph, and each was tested in the
          direction registered in advance: does the real graph score lower?
        </p>
        <p>
          The score is the area under the flow capacity curve over the first half of removals; lower means routing
          collapses sooner.
        </p>
        <ResultText strategies={strategies} data={data} complete={complete} />
      </TextBlock>

      <Figure
        title="Each removal order against the corrected threshold"
        controls={control}
        caption={
          <>
            Each row is one removal order and its one-sided p-value for the {metricLabel.toLowerCase()} score, on a
            logarithmic axis. p is (1 + randomized graphs scoring at or below the real graph) / ({count(n)} + 1), so it
            cannot fall below {p4(data.p_floor)}. The shaded band lies below the threshold of 0.05 / {strategies.length}{" "}
            = {p4(alpha)}, fixed in advance for {numberWord(strategies.length)} tests; a mark inside it is a significant
            result. Random removal is the diamond. Hover a row, or focus the chart and use the arrow keys, for its
            scores.
          </>
        }
      >
        <Ladder
          strategies={strategies}
          tests={tests}
          n={n}
          alpha={alpha}
          floor={data.p_floor}
          complete={complete}
          metricLabel={metricLabel}
        />
      </Figure>

      <Figure
        className={reduced ? "fa-still" : ""}
        title="The real graph against its randomizations"
        controls={control}
        caption={
          <>
            Each panel is one removal order. Bars count the {count(n)} randomized graphs by their{" "}
            {metricLabel.toLowerCase()} AUC; the black line is the real graph. A line left of the bars means the real
            wiring loses routing faster than wiring with the same degrees. The middle 95% spans the 2.5th to the 97.5th
            percentile of the randomized scores, and z is the distance of the real score from their mean in standard
            deviations. Panels use their own axes. Hover a bar, or focus a panel and use the arrow keys, for its count.
          </>
        }
      >
        <div className="fa-nulls">
          {strategies.map((s) => (
            <Panel key={s.id} strategy={s} test={tests[s.id]} n={n} complete={complete} metricLabel={metricLabel} />
          ))}
        </div>
      </Figure>

      <details className="more">
        <summary>Null-model tests as a table</summary>
        <div className="table-wrap">
          <table className="data">
            <thead>
              <tr>
                <th>Removal order</th>
                <th>Score</th>
                <th className="num">Real AUC</th>
                <th className="num">Randomized mean</th>
                <th className="num">SD</th>
                <th className="num">Range</th>
                <th className="num">At or below real</th>
                <th className="num">z</th>
                <th className="num">p</th>
                <th>Result</th>
              </tr>
            </thead>
            <tbody>
              {METRICS.flatMap((m) =>
                strategies.map((s) => {
                  const t = data.strategies[s.id][m.value];
                  return (
                    <tr key={`${m.value}-${s.id}`}>
                      <td>{sentence(s.label)}</td>
                      <td>{m.label}</td>
                      <td className="num">{fixed(t.real, 3)}</td>
                      <td className="num">{fixed(t.null_mean, 3)}</td>
                      <td className="num">{fixed(t.null_sd, 4)}</td>
                      <td className="num">
                        {fixed(t.null_min, 3)} to {fixed(t.null_max, 3)}
                      </td>
                      <td className="num">
                        {count(t.n_at_or_below_real)} of {count(n)}
                      </td>
                      <td className="num">{signedFixed(t.z_score, 1)}</td>
                      <td className="num">{p4(t.p_value)}</td>
                      <td>{reading(t, complete).short}</td>
                    </tr>
                  );
                }),
              )}
            </tbody>
          </table>
        </div>
      </details>
    </Finding>
  );
}
