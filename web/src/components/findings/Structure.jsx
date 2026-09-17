import { useState } from "react";
import { ChartFrame, Row, Tooltip, XAxis, YAxis } from "../Chart.jsx";
import { Figure, Keynote, Segmented, Sidenote, TextBlock } from "../ui.jsx";
import { Finding, Pending, useResult } from "./Finding.jsx";
import { ALTERNATIVES, LogAxes, PValue, Pow, minorTicks, verdict } from "./marks.jsx";
import { count, fixed, percent, sentence, signedFixed } from "../../lib/format.js";
import { useWidth } from "../../lib/hooks.js";
import { line, linear, log, logTicks } from "../../lib/scales.js";
import "../../styles/findings-b.css";

const ID = "structure";
const TITLE = "The shape of the graph";
const MEASURES = [
  { value: "out-strength", label: "Weighted out-degree", unit: "Output synapses", short: "synapses" },
  { value: "out-degree", label: "Out-degree", unit: "Target cell types", short: "partner types" },
  { value: "in-degree", label: "In-degree", unit: "Input cell types", short: "partner types" },
];
const SIGNIFICANCE = 0.05;
const TIP_HALF = 120;

const smallPercent = (v) => (v >= 0.01 ? percent(v, 0) : v >= 0.001 ? percent(v, 1) : percent(v, 2));

function joinWords(items) {
  if (items.length < 2) return items.join("");
  return `${items.slice(0, -1).join(", ")} and ${items[items.length - 1]}`;
}

/** Sort the alternatives into those that fit the tail better than a power law, those tied with it, and those worse. */
function compare(tail) {
  const better = [];
  const tied = [];
  const worse = [];
  for (const [id, name] of Object.entries(ALTERNATIVES)) {
    const c = tail.comparisons?.[id];
    if (!c) continue;
    if (c.p_value >= SIGNIFICANCE) tied.push(name);
    else if (c.loglikelihood_ratio < 0) better.push(name);
    else worse.push(name);
  }
  return { better, tied, worse };
}

/** The distribution the likelihood-ratio tests favor for one tail, in words. */
function favored(tail) {
  const { better, tied } = compare(tail);
  if (better.length) return `favors ${joinWords(better)} over a pure power law`;
  if (tied.length) return `cannot tell a power law from ${joinWords(tied)}`;
  return "favors a power law over every alternative";
}

const strengthWord = (rho) => {
  const r = Math.abs(rho);
  if (r < 0.3) return "weakly";
  if (r < 0.6) return "moderately";
  return "strongly";
};

export default function Structure({ percolation }) {
  const { data, missing } = useResult("structure.json");
  if (missing) return <Pending id={ID} title={TITLE} />;
  return data ? <StructureView data={data} percolation={percolation} /> : null;
}

function StructureView({ data, percolation }) {
  const [measure, setMeasure] = useState(MEASURES[0].value);
  const tails = MEASURES.map((m) => ({ ...m, tail: data.degree_tails?.find((t) => t.measure.startsWith(m.value)) })).filter(
    (m) => m.tail,
  );
  const byName = Object.fromEntries(tails.map((m) => [m.value, m.tail]));
  const strength = byName["out-strength"];
  const outDegree = byName["out-degree"];
  const inDegree = byName["in-degree"];
  const current = tails.find((m) => m.value === measure) ?? tails[0];
  const verdicts = strength ? compare(strength) : null;
  const deepShare = data.types_in_deepest_core / data.types;
  const rho = data.coreness_vs_out_strength;
  const ranked = Object.entries(percolation?.strategies ?? {})
    .filter(([id, s]) => id !== "random" && s.critical_fraction != null)
    .sort((a, b) => a[1].critical_fraction - b[1].critical_fraction);
  const strengthFirst = ranked[0]?.[0] === "out_strength";
  const weak = Math.abs(rho.spearman_rho) < 0.3;

  return (
    <Finding
      id={ID}
      title={TITLE}
      stat={percent(deepShare)}
      statLabel={`of cell types sit in the deepest core of the graph, k = ${data.max_coreness}`}
    >
      <TextBlock
        notes={
          <>
            {strength && (
              <Keynote value={`${count(strength.max / strength.median)} times`}>
                the median type&apos;s output synapses, sent by the strongest cell type
              </Keynote>
            )}
            <Sidenote title="Tail fits">
              Discrete maximum-likelihood fits with the tail start chosen by the Kolmogorov-Smirnov criterion (Clauset,
              Shalizi and Newman, 2009). A fitted exponent alone is not evidence of a scale-free graph, so each fit is
              tested against three alternatives.
            </Sidenote>
          </>
        }
      >
        {strength && (
          <p>
            {strengthFirst
              ? "The ranking that halves flow soonest orders cell types by how many synapses they send, and that quantity is extremely uneven."
              : "One of the rankings orders cell types by how many synapses they send, and that quantity is extremely uneven."}{" "}
            The median type makes {count(strength.median)} output synapses; the largest makes{" "}
            {count(strength.max)}. Only {count(strength.n_tail)} of {count(strength.n)} types (
            {percent(strength.n_tail / strength.n)}) send at least {count(strength.xmin)}. A ranking by weighted
            out-degree removes those few types first, and each takes far more synapses with it than a type picked at
            random, which almost always comes from the bulk of the distribution.
          </p>
        )}
        {strength && verdicts && (
          <p>
            Above {count(strength.xmin)} synapses a power law fits with exponent {fixed(strength.alpha)}
            {verdicts.better.length > 0 &&
              `, but ${joinWords(verdicts.better)} ${verdicts.better.length > 1 ? "fit" : "fits"} the tail better`}
            {verdicts.tied.length > 0 &&
              `${verdicts.better.length > 0 ? " and" : ", but"} ${joinWords(verdicts.tied)} ${verdicts.tied.length > 1 ? "fit" : "fits"} it as well`}
            .{" "}
            {verdicts.better.length + verdicts.tied.length > 0
              ? "The distribution is heavy tailed; the data do not show that the graph is scale free."
              : "Of the models compared, the power law fits best."}{" "}
            {outDegree && inDegree && (
              <>
                Counts of partners are less extreme: out-degree reaches {count(outDegree.max)} target types from a
                median of {count(outDegree.median)}, and in-degree is narrow, from a median of {count(inDegree.median)}{" "}
                to at most {count(inDegree.max)}.
              </>
            )}
          </p>
        )}
        <p>
          Peeling the undirected graph into k-cores ends at k = {data.max_coreness}, and{" "}
          {count(data.types_in_deepest_core)} of {count(data.types)} types belong to that deepest core
          {deepShare > 0.5 ? ": most of the graph is one densely interconnected block with thin shells around it." : "."}{" "}
          Coreness and weighted out-degree
          {rho.spearman_rho >= 0 ? " rise together" : " move in opposite directions"}
          {weak ? " only" : ""} {strengthWord(rho.spearman_rho)} (Spearman rho = {fixed(rho.spearman_rho)})
          {weak
            ? ", so ranking types by output picks out different types than ranking them by how deep in the core they sit."
            : "."}
        </p>
      </TextBlock>

      <div className="fb-structure">
        <Figure
          title="Share of cell types at or above each value"
          controls={<Segmented label="Measure" options={tails} value={current.value} onChange={setMeasure} />}
          caption={
            <>
              Both axes are logarithmic. The solid line is the share of cell types with at least each value; the dashed
              line is the power law fitted from the start of the shaded tail. The likelihood-ratio tests listed under
              the chart say which distribution the tail favors.
            </>
          }
        >
          <TailChart measure={current} />
          <p className="fb-favored">
            The {current.label.toLowerCase()} tail {favored(current.tail)}.
          </p>
          <ul className="fb-verdicts">
            {Object.entries(ALTERNATIVES).map(([id, name]) => {
              const c = current.tail.comparisons?.[id];
              if (!c) return null;
              return (
                <li key={id}>
                  <span>{verdict(c, name, SIGNIFICANCE)}</span>
                  <span className="fb-stat">
                    R = {signedFixed(c.loglikelihood_ratio)}, <PValue p={c.p_value} />
                  </span>
                </li>
              );
            })}
          </ul>
        </Figure>

        <Figure
          title="Cell types in each k-core layer"
          caption={
            <>
              Each stem counts the cell types whose coreness is k, on a logarithmic scale: the largest k for which the
              type belongs to a subgraph where every type has at least k partners. The deepest layer holds{" "}
              {percent(deepShare)} of all types.
            </>
          }
        >
          <CoreChart data={data} />
        </Figure>
      </div>

      <details className="more">
        <summary>Tail fits as a table</summary>
        <div className="table-wrap">
          <table className="data">
            <thead>
              <tr>
                <th>Measure</th>
                <th className="num">Types</th>
                <th className="num">Median</th>
                <th className="num">Maximum</th>
                <th className="num">Exponent</th>
                <th className="num">Tail starts at</th>
                <th className="num">Types in tail</th>
                <th className="num">KS distance</th>
                <th>Likelihood ratio</th>
              </tr>
            </thead>
            <tbody>
              {tails.map(({ value, label, tail }) => (
                <tr key={value}>
                  <td>{label}</td>
                  <td className="num">{count(tail.n)}</td>
                  <td className="num">{count(tail.median)}</td>
                  <td className="num">{count(tail.max)}</td>
                  <td className="num">{fixed(tail.alpha)}</td>
                  <td className="num">{count(tail.xmin)}</td>
                  <td className="num">{count(tail.n_tail)}</td>
                  <td className="num">{fixed(tail.ks_distance, 3)}</td>
                  <td>{sentence(favored(tail))}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <p className="caption fb-table-note">Only types with a value above zero are included.</p>
      </details>
    </Finding>
  );
}

function TailChart({ measure }) {
  const [hover, setHover] = useState(null);
  const [sizer, width] = useWidth();
  const narrow = width < 520;
  const { tail } = measure;
  const values = tail.ccdf.x;
  const ps = tail.ccdf.p;
  const margin = { top: 32, right: 24, bottom: 50, left: 54 };
  const xDomain = [1, 10 ** Math.max(1, Math.ceil(Math.log10(tail.max)))];
  const tailShare = tail.n_tail / tail.n;
  const fitAt = (x) => tailShare * (x / tail.xmin) ** (1 - tail.alpha);
  const minP = Math.min(...ps.filter((p) => p > 0), fitAt(tail.max));
  const yDomain = [10 ** Math.floor(Math.log10(minP)), 1];

  return (
    <div ref={sizer}>
      <ChartFrame
        height={narrow ? 320 : 380}
        margin={margin}
        label={`Log-log chart of the share of cell types with ${measure.label.toLowerCase()} at or above each value, with a power law of exponent ${fixed(tail.alpha)} fitted from ${count(tail.xmin)}`}
        onPointer={(x, _y, inner) => {
          const xs = log(xDomain, [0, inner.width]);
          let best = 0;
          for (let i = 1; i < values.length; i += 1) if (Math.abs(xs(values[i]) - x) < Math.abs(xs(values[best]) - x)) best = i;
          setHover(best);
        }}
        onLeave={() => setHover(null)}
        overlay={({ width: full, height, margin: m }) => {
          if (hover == null) return null;
          const w = full - m.left - m.right;
          const xs = log(xDomain, [0, w]);
          const x = m.left + xs(values[hover]);
          const flip = x > m.left + w / 2;
          const left = Math.max(TIP_HALF, Math.min(full - TIP_HALF, x + (flip ? -TIP_HALF - 12 : TIP_HALF + 12)));
          return (
            <Tooltip x={left} y={m.top + height * 0.55} width={full}>
              <strong className="fb-tip-head">
                {count(values[hover])} {measure.short} or more
              </strong>
              <Row label="Cell types" value={`${count(ps[hover] * tail.n)} (${smallPercent(ps[hover])})`} />
              {values[hover] >= tail.xmin && <Row label="Power law" value={smallPercent(fitAt(values[hover]))} />}
            </Tooltip>
          );
        }}
      >
        {(inner) => {
          const xs = log(xDomain, [0, inner.width]);
          const ys = log(yDomain, [inner.height, 0]);
          const clampY = (p) => ys(Math.max(yDomain[0], p));
          const observed = values.map((x, i) => [xs(x), clampY(ps[i])]);
          const steps = 32;
          const fit = Array.from({ length: steps }, (_, k) => {
            const x = tail.xmin * (tail.max / tail.xmin) ** (k / (steps - 1));
            return [xs(x), clampY(fitAt(x))];
          });
          const tailX = xs(tail.xmin);
          const fitLabel = `Power law, exponent ${fixed(tail.alpha)}`;
          const anchor = fit[Math.round(steps * 0.5)];
          const fitX = Math.max(fitLabel.length * 6.4, anchor[0] - 8);
          return (
            <g>
              <rect className="fb-tail" x={tailX} y={0} width={inner.width - tailX} height={inner.height} />
              <LogAxes xs={xs} ys={ys} width={inner.width} height={inner.height} xTitle={measure.unit} yTitle="Share of types at or above" />
              <text className="fb-note" x={tailX + 6} y={14} textAnchor={tailX > inner.width - 110 ? "end" : "start"} dx={tailX > inner.width - 110 ? -12 : 0}>
                Tail, {count(tail.n_tail)} types
              </text>
              <path className="fb-fit" d={line(fit)} />
              <path className="fb-observed" d={line(observed)} />
              <text className="direct-label" x={fitX} y={Math.min(inner.height - 8, anchor[1] + 22)} textAnchor="end">
                {fitLabel}
              </text>
              <text className="direct-label" x={8} y={clampY(ps[0]) + 18}>
                Observed
              </text>
              {hover != null && (
                <>
                  <line className="fb-crosshair" x1={xs(values[hover])} x2={xs(values[hover])} y1={0} y2={inner.height} />
                  <circle className="fb-point" cx={xs(values[hover])} cy={clampY(ps[hover])} r={4.5} style={{ fill: "var(--ink)" }} />
                </>
              )}
            </g>
          );
        }}
      </ChartFrame>
    </div>
  );
}

function CoreChart({ data }) {
  const [hover, setHover] = useState(null);
  const ks = Array.from({ length: data.max_coreness + 1 }, (_, k) => k);
  const counts = ks.map((k) => data.coreness_counts[String(k)] ?? 0);
  const margin = { top: 32, right: 16, bottom: 46, left: 54 };
  const yDomain = [1, 10 ** Math.max(1, Math.ceil(Math.log10(Math.max(...counts))))];
  const deepest = data.max_coreness;
  const step = ks.length > 12 ? 5 : 1;

  return (
    <ChartFrame
      height={380}
      margin={margin}
      label={`Stem chart of cell types by coreness from 0 to ${deepest}, logarithmic scale; ${count(counts[deepest])} types have coreness ${deepest}`}
      onPointer={(x, _y, inner) => setHover(Math.max(0, Math.min(ks.length - 1, Math.floor((x / inner.width) * ks.length))))}
      onLeave={() => setHover(null)}
      overlay={({ width: full, height, margin: m }) => {
        if (hover == null) return null;
        const w = full - m.left - m.right;
        const x = m.left + ((hover + 0.5) / ks.length) * w;
        return (
          <Tooltip x={Math.max(95, Math.min(full - 95, x))} y={m.top + height * 0.35} width={full}>
            <strong className="fb-tip-head">Coreness {hover}</strong>
            <Row label="Cell types" value={count(counts[hover])} />
            <Row label="Share of all types" value={smallPercent(counts[hover] / data.types)} />
          </Tooltip>
        );
      }}
    >
      {(inner) => {
        const ys = log(yDomain, [inner.height, 0]);
        const xs = linear([0, ks.length], [0, inner.width]);
        const cx = (k) => xs(k + 0.5);
        const labelRight = cx(deepest) > inner.width - 120;
        return (
          <>
            <YAxis scale={ys} ticks={logTicks(yDomain)} width={inner.width} format={(v) => <Pow value={v} />} title="Cell types" />
            {minorTicks(yDomain).map((t) => (
              <line key={t} className="fb-tick" x1={-3} x2={0} y1={ys(t)} y2={ys(t)} />
            ))}
            <line className="fb-tick" x1={0} x2={0} y1={0} y2={inner.height} />
            <XAxis
              scale={cx}
              ticks={ks.filter((k) => k % step === 0 && deepest - k >= step / 2).concat(deepest)}
              height={inner.height}
              width={inner.width}
              title="Coreness, k"
            />
            {hover != null && <rect className="fb-band" x={xs(hover)} width={xs(1) - xs(0)} y={0} height={inner.height} />}
            {counts.map((c, k) =>
              c > 0 ? (
                <g key={k} className={k === deepest ? "fb-core is-deepest" : "fb-core"}>
                  <line x1={cx(k)} x2={cx(k)} y1={inner.height} y2={ys(c)} />
                  <circle cx={cx(k)} cy={ys(c)} r={k === deepest ? 4.5 : 3} />
                </g>
              ) : null,
            )}
            <text
              className="direct-label"
              x={cx(deepest) + (labelRight ? -10 : 10)}
              y={ys(counts[deepest]) + 4}
              textAnchor={labelRight ? "end" : "start"}
            >
              {count(counts[deepest])} types at k = {deepest}
            </text>
          </>
        );
      }}
    </ChartFrame>
  );
}
