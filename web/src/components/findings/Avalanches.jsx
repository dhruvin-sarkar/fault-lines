import { useMemo, useState } from "react";
import { useRovingRows } from "./useRovingRows.js";
import { ChartFrame, Row, Tooltip } from "../Chart.jsx";
import { Figure, Keynote, Segmented, Sidenote, TextBlock } from "../ui.jsx";
import { Finding, Pending, useResult } from "./Finding.jsx";
import { LogAxes, PValue, Pow, inkColor, sentence } from "./marks.jsx";
import { count, fixed, percent, strategyLabel } from "../../lib/format.js";
import { useWidth } from "../../lib/hooks.js";
import { line, log } from "../../lib/scales.js";
import "../../styles/findings-b.css";

const ID = "avalanches";
const TITLE = "How collapse arrives";
const ALTERNATIVES = {
  exponential: "an exponential",
  lognormal: "a lognormal",
  truncated_power_law: "a truncated power law",
};
// Clauset, Shalizi and Newman: a power law is plausible when the bootstrap p is at least 0.1.
const PLAUSIBLE = 0.1;
const SIGNIFICANCE = 0.05;
const TIP_HALF = 115;

const color = inkColor;

/** Plain reading of a normalized log-likelihood ratio test against one alternative. */
function verdict(comparison, name) {
  if (comparison.p_value >= SIGNIFICANCE) return `Cannot be told apart from ${name}`;
  return comparison.loglikelihood_ratio > 0
    ? `Fits better than ${name}`
    : `${name[0].toUpperCase()}${name.slice(1)} fits better`;
}

export default function Avalanches({ meta, percolation }) {
  const { data, missing } = useResult("avalanches.json");
  if (missing) return <Pending id={ID} title={TITLE} />;
  return data?.primary ? <AvalanchesView data={data} meta={meta} percolation={percolation} /> : null;
}

function AvalanchesView({ data, meta, percolation }) {
  const [set, setSet] = useState("primary");
  const [active, setActive] = useState(null);
  const strategies = meta.strategies;
  const trials = meta.protocol?.random_trials;

  const primary = useMemo(() => {
    const sizes = [];
    for (const s of strategies) {
      for (const v of percolation.strategies[s.id]?.avalanche ?? []) if (v != null && v > 0) sizes.push({ v, id: s.id });
    }
    const n = sizes.length;
    const unique = [...new Set(sizes.map((d) => d.v))].sort((a, b) => a - b);
    return unique.map((size) => {
      const bySize = {};
      let atLeast = 0;
      for (const d of sizes) {
        if (d.v === size) bySize[d.id] = (bySize[d.id] ?? 0) + 1;
        if (d.v >= size) atLeast += 1;
      }
      return { size, p: atLeast / n, atLeast, n, bySize };
    });
  }, [strategies, percolation]);

  const sets = [
    { value: "primary", label: "One run per strategy" },
    ...(data.sensitivity && data.ccdf
      ? [{ value: "sensitivity", label: trials ? `With all ${count(trials)} random trials` : "With all random trials" }]
      : []),
  ];
  const shown = sets.some((s) => s.value === set) ? set : "primary";
  const fit = data[shown];
  const points =
    shown === "primary"
      ? primary
      : data.ccdf.size.map((size, i) => ({
          size,
          p: data.ccdf.p[i],
          atLeast: Math.round(data.ccdf.p[i] * data.sensitivity.fitted),
          n: data.sensitivity.fitted,
          bySize: null,
        }));
  const labels = Object.fromEntries(strategies.map((s) => [s.id, strategyLabel(s.id)]));
  const largestId = Object.entries(data.per_strategy ?? {}).find(([, v]) => v.max_size === data.primary.max_size)?.[0];
  const plausible = (r) => (r.power_law_plausible ? "is not rejected" : "is rejected");
  const lognormalOpen = [data.primary, data.sensitivity]
    .filter(Boolean)
    .every((r) => r.comparisons.lognormal.p_value >= SIGNIFICANCE);
  const rows = strategies
    .filter((s) => data.per_strategy?.[s.id])
    .map((s) => ({ ...s, ...data.per_strategy[s.id] }))
    .sort((a, b) => b.total_cut_off - a.total_cut_off);
  const quiet = rows.filter((r) => r.max_size <= 1);

  return (
    <Finding
      id={ID}
      title={TITLE}
      stat={count(data.primary.max_size)}
      statLabel={`types cut off from all sensory input by one removal batch, the largest cascade${largestId ? `, under ${labels[largestId]}` : ""}`}
    >
      <TextBlock
        notes={
          <>
            <Sidenote title="A cascade">
              The cell types one removal batch newly cuts off from every sensory type, not counting the types removed in
              that batch.
            </Sidenote>
            <Keynote value={fixed(data.primary.alpha)}>
              fitted power-law exponent from size {count(data.primary.xmin)}, plus or minus{" "}
              {fixed(data.primary.alpha_se)}
            </Keynote>
            <Sidenote title="Structure, not activity">
              No neural activity is simulated. These cascades are in the wiring diagram and say nothing about avalanches
              of activity in living tissue.
            </Sidenote>
          </>
        }
      >
        <p>
          Most removal batches cut off nothing or a handful of types; a few cut off hundreds or thousands. Of{" "}
          {count(data.primary.batches)} batches in one run per strategy, {count(data.primary.zero_size)} cut off
          nothing. The largest cascade, {count(data.primary.max_size)} types in a single batch, comes from the{" "}
          {labels[largestId] ?? largestId} run
          {quiet.length > 0 &&
            `, while ${quiet.map((r) => labels[r.id]).join(" and ")} removal never cuts off more than ${count(Math.max(...quiet.map((r) => r.max_size)))} at a time`}
          .
        </p>
        <p>
          The tail is heavy, but it is not shown to be scale free. A power law {plausible(data.primary)} for one run per
          strategy (bootstrap p = {fixed(data.primary.bootstrap_p, 3)})
          {data.sensitivity &&
            ` and ${plausible(data.sensitivity)} when all ${trials ? `${count(trials)} ` : ""}random trials are pooled (p = ${fixed(data.sensitivity.bootstrap_p, 3)})`}
          .{lognormalOpen && " In neither set can it be told apart from a lognormal."}
        </p>
      </TextBlock>

      <Figure
        title="Share of cascades at least as large as each size"
        controls={sets.length > 1 && <Segmented label="Runs pooled" options={sets} value={shown} onChange={setSet} />}
        caption={
          <>
            Both axes are logarithmic. Each dot is one cascade size and its height the share of cascades that large or
            larger. Filled dots lie in the fitted tail, from size {count(fit.xmin)}; the dashed line is the power law
            fitted there, exponent {fixed(fit.alpha)} plus or minus {fixed(fit.alpha_se)}. Hover a dot for counts
            {shown === "primary" ? " and the strategies that produced it" : ""}.
          </>
        }
      >
        <div className="legend fb-legend" aria-hidden="true">
          <span>
            <svg width="10" height="10" viewBox="-5 -5 10 10">
              <circle r="4" className="fb-glyph-ink" />
            </svg>
            In the fitted tail
          </span>
          <span>
            <svg width="10" height="10" viewBox="-5 -5 10 10">
              <circle r="3.5" className="fb-glyph-ring" />
            </svg>
            Below the tail
          </span>
        </div>
        <CascadeChart
          points={points}
          fit={fit}
          active={shown === "primary" ? active : null}
          labels={labels}
          largestLabel={labels[largestId]}
        />
      </Figure>

      <div className="fb-fits">
        <dl className="facts">
          <div>
            <dt>Smallest cascade size in the fitted tail</dt>
            <dd className="number">{count(fit.xmin)}</dd>
          </div>
          <div>
            <dt>Cascades in the tail, of {count(fit.fitted)} that cut off at least one type</dt>
            <dd className="number">{count(fit.n_tail)}</dd>
          </div>
          <div>
            <dt>
              Bootstrap goodness of fit over {count(fit.bootstrap_sims)} synthetic sets; below {PLAUSIBLE} rejects a
              power law
            </dt>
            <dd className="number">{fixed(fit.bootstrap_p, 3)}</dd>
          </div>
        </dl>
        <div>
          <p className="label fb-fits-title">The power law against other distributions</p>
          <ul className="fb-verdicts">
            {Object.entries(ALTERNATIVES).map(([id, name]) => {
              const c = fit.comparisons[id];
              if (!c) return null;
              return (
                <li key={id}>
                  <span>{verdict(c, name)}</span>
                  <span className="fb-stat">
                    R = {c.loglikelihood_ratio > 0 ? "+" : ""}
                    {fixed(c.loglikelihood_ratio)}, <PValue p={c.p_value} />
                  </span>
                </li>
              );
            })}
          </ul>
          <p className="caption fb-fits-note">
            R is the normalized log-likelihood ratio; positive R favours the power law. A p of {SIGNIFICANCE} or more
            means the sign of R is not significant.
          </p>
        </div>
      </div>

      {rows.length > 0 && (
        <Figure
          title="Types cut off per strategy, one run each"
          caption={
            <>
              Logarithmic scale. The bar is the total number of types each run cut off; the black tick is its largest
              single cascade. Select a strategy to pick out the sizes of its cascades in the chart above.
            </>
          }
        >
          <Strip rows={rows} active={active} onPick={(id) => {
            setSet("primary");
            setActive(active === id ? null : id);
          }} />
        </Figure>
      )}

      <details className="more">
        <summary>Cascades as a table</summary>
        <div className="table-wrap">
          <table className="data">
            <thead>
              <tr>
                <th>Strategy</th>
                <th className="num">Batches</th>
                <th className="num">Batches with a cascade</th>
                <th className="num">Largest cascade</th>
                <th className="num">Types cut off in total</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((r) => (
                <tr key={r.id}>
                  <td>{strategyLabel(r.id)}</td>
                  <td className="num">{count(r.batches)}</td>
                  <td className="num">{count(r.batches - r.zero_size)}</td>
                  <td className="num">{count(r.max_size)}</td>
                  <td className="num">{count(r.total_cut_off)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        {data.sensitivity && (
          <p className="caption fb-table-note">
            One run per strategy: {count(data.primary.batches)} batches, {count(data.primary.zero_size)} without a
            cascade. All random trials pooled: {count(data.sensitivity.batches)} batches,{" "}
            {count(data.sensitivity.zero_size)} without a cascade. Sizes of zero are left out of both fits.
          </p>
        )}
      </details>
    </Finding>
  );
}

function Strip({ rows, active, onPick }) {
  const rowProps = useRovingRows(
    rows.map((r) => r.id),
    () => {},
  );
  const decades = Math.max(1, Math.ceil(Math.log10(Math.max(...rows.map((r) => r.total_cut_off), 10))));
  const at = (v) => `${(100 * Math.log10(Math.max(1, v))) / decades}%`;
  return (
    <>
      <ul className="fb-strip" aria-label="Types cut off per strategy">
        {rows.map((r) => (
          <li key={r.id}>
            <button
              {...rowProps(r.id)}
              type="button"
              aria-pressed={active === r.id}
              aria-label={`${strategyLabel(r.id)}: ${count(r.total_cut_off)} types cut off in total, largest cascade ${count(r.max_size)}`}
              onClick={() => onPick(r.id)}
              className={active && active !== r.id ? "is-dim" : ""}
            >
              <span className="fb-name">{sentence(strategyLabel(r.id))}</span>
              <span className="fb-track" aria-hidden="true">
                <span className="fb-bar" style={{ width: at(r.total_cut_off), background: color(r.id) }} />
                <span className="fb-mark" style={{ left: at(r.max_size) }} />
              </span>
              <span className="fb-figures">
                <strong>{count(r.total_cut_off)}</strong> total, largest {count(r.max_size)}
              </span>
            </button>
          </li>
        ))}
      </ul>
      <div className="fb-strip-axis" aria-hidden="true">
        <span />
        <span className="fb-ticks">
          {Array.from({ length: decades + 1 }, (_, k) => (
            <span key={k} style={{ left: `${(100 * k) / decades}%` }}>
              <svg width="28" height="16" viewBox="-14 -12 28 16">
                <text textAnchor="middle" className="fb-strip-tick">
                  <Pow value={10 ** k} />
                </text>
              </svg>
            </span>
          ))}
        </span>
        <span />
      </div>
    </>
  );
}

function CascadeChart({ points, fit, active, labels, largestLabel }) {
  const [hover, setHover] = useState(null);
  const [sizer, width] = useWidth();
  const narrow = width < 620;
  const margin = { top: 32, right: narrow ? 20 : 40, bottom: 50, left: 54 };
  const maxSize = points[points.length - 1].size;
  const xDomain = [1, 10 ** Math.max(1, Math.ceil(Math.log10(maxSize)))];
  const tailShare = fit.n_tail / fit.fitted;
  const fitAt = (s) => tailShare * (s / fit.xmin) ** (1 - fit.alpha);
  const minP = Math.min(...points.map((d) => d.p), fitAt(maxSize));
  const yDomain = [10 ** Math.floor(Math.log10(minP)), 1];
  const hovered = hover == null ? null : points[hover];

  return (
    <div ref={sizer}>
      <ChartFrame
        height={narrow ? 340 : 400}
        margin={margin}
        label={`Log-log chart of the share of cascades at least as large as each size, with a power law of exponent ${fixed(fit.alpha)} fitted from size ${fit.xmin}`}
        onPointer={(x, _y, inner) => {
          const xs = log(xDomain, [0, inner.width]);
          let best = 0;
          for (let i = 1; i < points.length; i += 1) {
            if (Math.abs(xs(points[i].size) - x) < Math.abs(xs(points[best].size) - x)) best = i;
          }
          setHover(best);
        }}
        onLeave={() => setHover(null)}
        overlay={({ width: full, height, margin: m }) => {
          if (!hovered) return null;
          const w = full - m.left - m.right;
          const xs = log(xDomain, [0, w]);
          const ys = log(yDomain, [height, 0]);
          const x = m.left + xs(hovered.size);
          const flip = x > m.left + w / 2;
          const left = Math.max(TIP_HALF, Math.min(full - TIP_HALF, x + (flip ? -TIP_HALF - 12 : TIP_HALF + 12)));
          const top = Math.max(m.top + 110, m.top + ys(hovered.p) + 40);
          return (
            <Tooltip x={left} y={Math.min(top, m.top + height)} width={full}>
              <strong className="fb-tip-head">
                {count(hovered.size)} {hovered.size === 1 ? "type" : "types"} cut off
              </strong>
              <Row label="This large or larger" value={`${count(hovered.atLeast)} of ${count(hovered.n)} (${percent(hovered.p)})`} />
              {hovered.size >= fit.xmin && <Row label="Power law" value={percent(fitAt(hovered.size))} />}
              {hovered.bySize &&
                Object.entries(hovered.bySize).map(([id, n]) => (
                  <Row key={id} label={sentence(labels[id])} value={`${count(n)} of this size`} color={color(id)} />
                ))}
            </Tooltip>
          );
        }}
      >
        {(inner) => {
          const xs = log(xDomain, [0, inner.width]);
          const ys = log(yDomain, [inner.height, 0]);
          const steps = 32;
          const fitPoints = Array.from({ length: steps }, (_, k) => {
            const s = fit.xmin * (maxSize / fit.xmin) ** (k / (steps - 1));
            return [xs(s), ys(Math.max(yDomain[0], fitAt(s)))];
          });
          const fitLabel = `Power law, exponent ${fixed(fit.alpha)}`;
          const anchor = fitPoints[Math.round(steps * 0.6)];
          const largest = points[points.length - 1];
          const tailX = xs(fit.xmin);
          return (
            <g>
              <rect className="fb-tail" x={tailX} y={0} width={inner.width - tailX} height={inner.height} />
              <LogAxes
                xs={xs}
                ys={ys}
                width={inner.width}
                height={inner.height}
                xTitle={narrow ? "Cascade size, types cut off" : "Cascade size, types cut off by one batch"}
                yTitle={narrow ? "Share this large or larger" : "Share of cascades this large or larger"}
              />
              <text className="fb-note" x={tailX + 6} y={14}>
                Fitted tail from size {count(fit.xmin)}
              </text>
              <path className="fb-fit" d={line(fitPoints)} />
              <text
                className="direct-label"
                x={Math.max(fitLabel.length * 6.4, anchor[0] - 6)}
                y={Math.min(inner.height - 8, anchor[1] + 22)}
                textAnchor="end"
              >
                {fitLabel}
              </text>
              {points.map((d, i) => {
                const inTail = d.size >= fit.xmin;
                const marked = active && d.bySize?.[active];
                const faded = active && !marked;
                return (
                  <circle
                    key={d.size}
                    cx={xs(d.size)}
                    cy={ys(d.p)}
                    r={marked ? 6 : hover === i ? 5.5 : 4}
                    className={`fb-dot ${inTail ? "is-tail" : ""} ${faded ? "is-faded" : ""}`}
                    style={marked ? { fill: color(active), stroke: "var(--ink)" } : undefined}
                  />
                );
              })}
              {largest && (
                <text className="fb-value" x={xs(largest.size) - 10} y={ys(largest.p) - 12} textAnchor="end">
                  {count(largest.size)} types in one batch{!narrow && largestLabel ? `, ${largestLabel}` : ""}
                </text>
              )}
            </g>
          );
        }}
      </ChartFrame>
    </div>
  );
}
