import { useMemo, useState } from "react";
import { Finding, Pending, useResult } from "./Finding.jsx";
import { inkColor as ink } from "./marks.jsx";
import { ChartFrame, Row, Tooltip } from "../Chart.jsx";
import { Figure, Segmented, Sidenote, TextBlock } from "../ui.jsx";
import { useReducedMotion } from "../../lib/hooks.js";
import { linear, niceTicks } from "../../lib/scales.js";
import { count, fixed, pValue } from "../../lib/format.js";
import "../../styles/findings-a.css";

const ID = "null-model";
const NEUTRAL_TITLE = "Against randomized graphs with the same degrees";
const BINS = 18;
const METRICS = [
  { value: "auc_flow", label: "Flow capacity" },
  { value: "auc_reachability", label: "Reachable pairs" },
];

/** Equal-width bins over a domain that always contains the real value. */
function histogram(samples, real) {
  let lo = Math.min(real, ...samples);
  let hi = Math.max(real, ...samples);
  const pad = (hi - lo) * 0.06 || 0.005;
  lo -= pad;
  hi += pad;
  const step = (hi - lo) / BINS;
  const counts = new Array(BINS).fill(0);
  for (const v of samples) counts[Math.min(BINS - 1, Math.floor((v - lo) / step))] += 1;
  return { lo, hi, step, counts, peak: Math.max(...counts) };
}


/** The chapter title states the result only as far as the tests support it. */
function titleFor(significant, total) {
  if (significant === total) return "Not the degree sequence";
  if (significant > 0) return "Partly beyond the degree sequence";
  return NEUTRAL_TITLE;
}

function Swatch({ id }) {
  if (id === "random") {
    return (
      <svg width="12" height="12" viewBox="-6 -6 12 12" aria-hidden="true" className="fa-swatch">
        <path d="M0 -5L5 0L0 5L-5 0Z" className="fa-diamond" style={{ stroke: ink(id) }} />
      </svg>
    );
  }
  return <span className="swatch" style={{ background: ink(id) }} aria-hidden="true" />;
}

const joinNames = (names) =>
  names.length <= 1 ? names.join("") : `${names.slice(0, -1).join(", ")} and ${names[names.length - 1]}`;

function Panel({ strategy, test, samples, significant, metricLabel }) {
  const [hover, setHover] = useState(null);
  const hist = useMemo(() => histogram(samples, test.real), [samples, test.real]);
  const margin = { top: 22, right: 8, bottom: 26, left: 8 };
  const plot = (h) => h - 6;

  return (
    <div className="fa-null">
      <div className="fa-null-head">
        <span>
          <Swatch id={strategy.id} />
          {strategy.label}
        </span>
        <span className={`fa-verdict${significant ? " is-yes" : ""}`}>{significant ? "Significant" : "Not significant"}</span>
      </div>
      <ChartFrame
        height={150}
        margin={margin}
        label={`${metricLabel} AUC of ${samples.length} randomized graphs under ${strategy.label} removal; the real graph scores ${fixed(test.real, 3)}.`}
        onPointer={(x, _y, inner) => {
          const bin = Math.floor((x / inner.width) * BINS);
          setHover(bin >= 0 && bin < BINS ? bin : null);
        }}
        onLeave={() => setHover(null)}
        overlay={({ margin: m, width: w, height: h }) => {
          if (hover == null) return null;
          const from = hist.lo + hover * hist.step;
          const barTop = h - (hist.counts[hover] / (hist.peak || 1)) * plot(h);
          return (
            <Tooltip x={m.left + ((hover + 0.5) / BINS) * (w - m.left - m.right)} y={m.top + barTop - 2} width={w}>
              <strong>
                AUC {fixed(from, 3)} to {fixed(from + hist.step, 3)}
              </strong>
              <Row label="Randomized graphs" value={count(hist.counts[hover])} />
              <Row label="Real graph" value={fixed(test.real, 3)} />
            </Tooltip>
          );
        }}
      >
        {(inner) => {
          const x = linear([hist.lo, hist.hi], [0, inner.width]);
          const bw = inner.width / BINS;
          const ticks = niceTicks([hist.lo, hist.hi], inner.width < 240 ? 2 : 3).filter((t) => t >= hist.lo && t <= hist.hi);
          const realX = x(test.real);
          const flip = realX > inner.width - 70;
          return (
            <g>
              {hist.counts.map((c, i) => (
                <rect
                  key={i}
                  className="fa-move"
                  width={Math.max(1, bw - 1)}
                  height={1}
                  style={{
                    transform: `translate(${i * bw + 0.5}px, ${inner.height}px) scaleY(${-(c / (hist.peak || 1)) * plot(inner.height)})`,
                    fill: ink(strategy.id),
                    fillOpacity: strategy.id === "random" ? 0.18 : hover == null || hover === i ? 0.9 : 0.25,
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
                    <text y={16} textAnchor="middle">
                      {fixed(t, 2)}
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
          <dt>Randomized</dt>
          <dd>
            {fixed(test.null_mean, 3)} ± {fixed(test.null_sd, 3)}
          </dd>
        </div>
        <div>
          <dt>At or below real</dt>
          <dd>
            {count(test.n_at_or_below_real)} of {count(samples.length)}
          </dd>
        </div>
        <div>
          <dt>z; p</dt>
          <dd>
            {fixed(test.z_score, 1)}; {pValue(test.p_value)}
          </dd>
        </div>
      </dl>
    </div>
  );
}

export default function NullModel({ meta }) {
  const { data, missing } = useResult("nulls.json");
  const [metric, setMetric] = useState("auc_flow");
  const reduced = useReducedMotion();

  if (missing) return <Pending id={ID} title={NEUTRAL_TITLE} />;
  if (!data) return null;

  const strategies = meta.strategies.filter((s) => data.strategies[s.id]);
  const alpha = data.alpha;
  const isSignificant = (t) => t.significant ?? t.p_value <= alpha;
  const significantFor = (m) => strategies.filter((s) => isSignificant(data.strategies[s.id][m]));
  const flowYes = significantFor("auc_flow");
  const flowNo = strategies.filter((s) => !flowYes.includes(s));
  const reachYes = significantFor("auc_reachability");
  const aboveMean = flowNo.filter((s) => data.strategies[s.id].auc_flow.real > data.strategies[s.id].auc_flow.null_mean);
  const metricLabel = METRICS.find((m) => m.value === metric).label;
  const floor = 1 / (data.n_nulls + 1);
  const all = flowYes.length === strategies.length;

  return (
    <Finding
      id={ID}
      title={titleFor(flowYes.length, strategies.length)}
      stat={`${flowYes.length} of ${strategies.length}`}
      statLabel="removal orders under which routing fails significantly sooner than in randomized graphs"
    >
      <TextBlock
        notes={
          <>
            <Sidenote title="Degree-preserving randomization">
              Each of the {count(data.n_nulls)} randomized graphs keeps every cell type&apos;s number of inputs and
              outputs and its output synapse total, but reassigns who connects to whom.
            </Sidenote>
            <Sidenote title="Fixed in advance">
              The direction, the one-sided test and the Bonferroni threshold of {fixed(alpha, 4)} were registered before
              any randomized graph was scored. With {count(data.n_nulls)} graphs the smallest possible p is{" "}
              {fixed(floor, 4)}.
            </Sidenote>
          </>
        }
      >
        <p>
          A few very connected types make almost any network fragile under targeted removal. The question here is
          whether the fly&apos;s particular wiring adds fragility beyond its degree sequence, so every removal order was
          rerun on randomized graphs with the same degrees.
        </p>
        <p>
          The score is the area under the flow capacity curve over the first half of removals; lower means routing
          collapses sooner. {all ? "Under all" : `Under ${flowYes.length} of`} {strategies.length} removal orders
          {!all && flowYes.length > 0 ? ` (${joinNames(flowYes.map((s) => s.label))})` : ""} the real graph scores
          significantly below its randomized versions.
          {flowNo.length > 0 &&
            ` Under the other ${flowNo.length === 1 ? "one" : flowNo.length}, the difference does not reach the corrected threshold${
              aboveMean.length ? `, and under ${aboveMean.length === flowNo.length ? (flowNo.length === 1 ? "it" : "all of them") : `${aboveMean.length} of them`} the real graph scores above the randomized mean` : ""
            }.`}{" "}
          Reachable pairs, the secondary measure, give {reachYes.length} of {strategies.length} significant results.
        </p>
      </TextBlock>

      <Figure
        className={reduced ? "fa-still" : ""}
        title="The real graph against its degree-preserving randomizations"
        controls={<Segmented label="Score" options={METRICS} value={metric} onChange={setMetric} />}
        caption={
          <>
            Each panel is one removal order. Bars count the {count(data.n_nulls)} randomized graphs by their{" "}
            {metricLabel.toLowerCase()} AUC; the black line is the real graph. A line left of the bars means the real
            wiring loses routing faster than wiring with the same degrees. p is (1 + randomized graphs at or below the
            real score) / ({count(data.n_nulls)} + 1), judged against {fixed(alpha, 4)}; z is the distance from the
            randomized mean in standard deviations. Random removal is drawn with outlined bars and a diamond. Panels use their own axes. Hover a bar for its count.
          </>
        }
      >
        <div className="fa-nulls">
          {strategies.map((s) => (
            <Panel
              key={s.id}
              strategy={s}
              test={data.strategies[s.id][metric]}
              samples={data.samples[s.id][metric]}
              significant={isSignificant(data.strategies[s.id][metric])}
              metricLabel={metricLabel}
            />
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
                      <td>{s.label}</td>
                      <td>{m.label.toLowerCase()}</td>
                      <td className="num">{fixed(t.real, 3)}</td>
                      <td className="num">{fixed(t.null_mean, 3)}</td>
                      <td className="num">{fixed(t.null_sd, 3)}</td>
                      <td className="num">
                        {fixed(t.null_min, 3)} to {fixed(t.null_max, 3)}
                      </td>
                      <td className="num">{count(t.n_at_or_below_real)}</td>
                      <td className="num">{fixed(t.z_score, 2)}</td>
                      <td className="num">{pValue(t.p_value)}</td>
                      <td>{isSignificant(t) ? "Significant" : "Not significant"}</td>
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
