import { useMemo, useState } from "react";
import { ChartFrame, Row, Tooltip } from "../Chart.jsx";
import { Figure, Keynote, Sidenote, TextBlock } from "../ui.jsx";
import { useWidth } from "../../lib/hooks.js";
import { count, percent, sentence, signedCount, superclassName } from "../../lib/format.js";
import { linear, niceTicks } from "../../lib/scales.js";
import { Finding, Pending, useResult } from "./Finding.jsx";
import { PValue } from "./marks.jsx";
import { coarsePointer, useRovingRows } from "./useRovingRows.js";
import "../../styles/findings-c.css";

const ID = "bilateral";
const TITLE = "Left and right";
const ALPHA = 0.05;
const SENSORY = 1;

const CLASSES = [
  { key: "superadditive", name: "Superadditive", meaning: "Both sides together cost more than the two alone" },
  { key: "additive", name: "Additive", meaning: "The two single-side losses add up exactly" },
  { key: "subadditive", name: "Subadditive", meaning: "One side alone already costs most of what both carry" },
];

const SIDES = { L: "left", R: "right", M: "on the midline", unknown: "without a recorded side" };

/** A signed-rank statistic exactly; W can be a half-integer when ranks are tied. */
const statistic = (w) => (w == null ? "n/a" : w.toLocaleString("en-US", { maximumFractionDigits: 1 }));

export default function Bilateral({ types }) {
  const { data, missing } = useResult("bilateral.json");
  if (missing) return <Pending id={ID} title={TITLE} />;
  return data ? <BilateralView data={data} types={types} /> : null;
}

function BilateralView({ data, types }) {
  const index = useMemo(() => new Map((types?.name ?? []).map((n, i) => [n, i])), [types]);
  const counts = data.additivity_counts ?? {};
  const informative = data.informative_types;
  const largest = Math.max(1, ...CLASSES.map((c) => counts[c.key] ?? 0));
  const single = data.both_greater_than_single_mean;
  const sum = data.both_greater_than_sum_of_singles;
  const sides = Object.entries(data.nodes_by_side ?? {}).filter(([, n]) => n > 0);
  const strongest = data.strongest_superadditive ?? [];
  const additiveShare = informative ? (counts.additive ?? 0) / informative : null;
  const maxSuper = strongest.length ? Math.max(...strongest.map((r) => r.superadditivity)) : null;
  const top = strongest.find((r) => r.superadditivity === maxSuper);
  // The listed types can end partway through a tie, so the share of sensory types is taken above the lowest listed value.
  const floorSuper = strongest.length ? Math.min(...strongest.map((r) => r.superadditivity)) : null;
  const aboveFloor = strongest.filter((r) => r.superadditivity > floorSuper);
  const ranked = aboveFloor.length ? aboveFloor : strongest;
  const sensoryTop = ranked.filter((r) => index.has(r.cell_type) && types.role[index.get(r.cell_type)] === SENSORY).length;
  const rankedLabel = aboveFloor.length
    ? `types with an excess of ${count(floorSuper + 1)} routes or more`
    : "most superadditive types listed";
  const describe = (name) => {
    const i = index.get(name);
    return i == null ? null : sentence(superclassName(types.superclasses[types.superclass[i]]));
  };

  return (
    <Finding
      id={ID}
      title={TITLE}
      stat={additiveShare != null ? percent(additiveShare) : count(data.fully_insured_types)}
      statLabel={
        additiveShare != null
          ? `of the ${count(informative)} types whose removal changes flow lose exactly their two single-side losses added up`
          : "types whose loss shows only when both copies are removed"
      }
    >
      <TextBlock
        notes={
          <>
            <Sidenote title="Sides">
              Each neuron&apos;s side is its annotated soma side, or its nerve root side for sensory neurons. No side is
              inferred from a type&apos;s name.
            </Sidenote>
            <Sidenote title="Superadditivity">
              The routes lost with both copies removed, minus the losses with each copy removed alone. Positive values
              mean each side covers for the other.
            </Sidenote>
            <Keynote value={count(data.fully_insured_types)}>
              types lose nothing when either side goes alone, and lose routes only when both go
            </Keynote>
          </>
        }
      >
        <p>
          Most cell types exist as a left and a right copy. Splitting every type by hemisphere gives a graph of{" "}
          {count(data.nodes)} nodes and {count(data.edges)} connections
          {sides.length > 0 && ` (${sides.map(([side, n]) => `${count(n)} ${SIDES[side] ?? side}`).join(", ")})`}, with{" "}
          {count(data.intact_flow)} routes from sensory to motor nodes. Each of the {count(data.bilateral_types)} types
          with both copies was removed three ways: left only, right only, and both.
        </p>
        <p>
          Of those, {count(informative)} change flow capacity in at least one of the three removals. For{" "}
          {count(counts.additive)} of them the two sides are independent: removing both costs exactly what the two
          single removals cost added together. Of the rest, {count(counts.superadditive)} are superadditive and{" "}
          {count(counts.subadditive)} subadditive. Only {count(data.fully_insured_types)} types are hidden entirely by
          their opposite copy, costing nothing until both are gone.
        </p>
        {top && (
          <p>
            Where the two sides do back each other up, the effect is small. The largest excess is{" "}
            {count(maxSuper)} routes, for <span className="id">{top.cell_type}</span>, whose two copies cost{" "}
            {count(top.impact_left)} and {count(top.impact_right)} alone and {count(top.impact_both)} together.{" "}
            {types &&
              `${count(sensoryTop)} of the ${count(ranked.length)} ${rankedLabel} are sensory, the same pattern as the pairs above: sensory types are where flow enters, and when one copy goes the other fills downstream capacity it leaves unused.`}
          </p>
        )}
      </TextBlock>

      <Figure
        title="How the two single-side losses combine"
        caption={
          <>
            Each of the {count(informative)} types whose removal changes flow capacity, classed by comparing the loss
            with both copies removed against the two single-side losses added up. Bar length is the number of types.
          </>
        }
      >
        <ul className="fc-bars" aria-label="Types by how their single-side losses combine">
          {CLASSES.map((c) => {
            const n = counts[c.key] ?? 0;
            return (
              <li key={c.key}>
                <span className="fc-bar-label">
                  <span className="fc-bar-name">{c.name}</span>
                  <span className="fc-bar-meaning">{c.meaning}</span>
                </span>
                <span className="fc-bar-track" aria-hidden="true">
                  <span
                    className="fc-bar-fill"
                    style={{ width: `max(2px, ${(100 * n) / largest}%)`, background: "var(--ink-2)" }}
                  />
                </span>
                <span className="fc-bar-count">
                  {count(n)}
                  <small>{informative ? percent(n / informative) : ""}</small>
                </span>
              </li>
            );
          })}
        </ul>
      </Figure>

      {single && sum && (
        <dl className="fc-tests">
          <div>
            <dt>Does losing both sides cost more than losing one?</dt>
            <dd>
              <span className="fc-verdict">
                {single.p_value < ALPHA
                  ? "Yes, though this is expected: when the two losses simply add, removing both always costs more than the average single side."
                  : "Not detectably. Removing both copies did not cost significantly more than the average single-side removal."}
              </span>
              <span className="fc-stats">
                One-sided Wilcoxon signed-rank test over the {count(single.pairs_differing)} types whose values differ: W ={" "}
                {statistic(single.statistic)}, <PValue p={single.p_value} />
              </span>
            </dd>
          </div>
          <div>
            <dt>Does it cost more than the two single-side losses added up?</dt>
            <dd>
              <span className="fc-verdict">
                {sum.p_value < ALPHA
                  ? `Among the ${count(sum.pairs_differing)} types where the two differ at all, yes: superadditive types outnumber subadditive ones ${count(counts.superadditive)} to ${count(counts.subadditive)}. For the other ${count(informative - sum.pairs_differing)}, the sides add up exactly.`
                  : "Not in general. The joint loss is not significantly larger than the two single losses added up; backup between sides belongs to particular types."}
              </span>
              <span className="fc-stats">
                One-sided Wilcoxon signed-rank test over the {count(sum.pairs_differing)} types whose values differ: W ={" "}
                {statistic(sum.statistic)}, <PValue p={sum.p_value} />
              </span>
            </dd>
          </div>
        </dl>
      )}

      {strongest.length > 0 && (
        <Figure
          title="The types whose two sides back each other up most"
          caption={
            <>
              Each bar is one type&apos;s superadditivity: the routes lost with both copies removed, beyond the two
              single-side losses. The number after it is everything both copies cost together, out of{" "}
              {count(data.intact_flow)}. Hover or focus a row for the single-side losses.
            </>
          }
        >
          <SuperChart rows={strongest} describe={describe} />
        </Figure>
      )}

      <dl className="facts">
        <div>
          <dt>Types with both a left and a right copy</dt>
          <dd>{count(data.bilateral_types)}</dd>
        </div>
        <div>
          <dt>Of those, types whose removal changes flow capacity</dt>
          <dd>{count(informative)}</dd>
        </div>
        <div>
          <dt>Covered completely by the opposite copy</dt>
          <dd>{count(data.fully_insured_types)}</dd>
        </div>
        <div>
          <dt>Routes in the intact hemisphere-resolved graph</dt>
          <dd>{count(data.intact_flow)}</dd>
        </div>
      </dl>

      {strongest.length > 0 && (
        <details className="more">
          <summary>The {strongest.length} most superadditive types as a table</summary>
          <div className="table-wrap">
            <table className="data">
              <thead>
                <tr>
                  <th>Cell type</th>
                  <th>Superclass</th>
                  <th className="num">Left removed</th>
                  <th className="num">Right removed</th>
                  <th className="num">Both removed</th>
                  <th className="num">Superadditivity</th>
                </tr>
              </thead>
              <tbody>
                {strongest.map((r) => (
                  <tr key={r.cell_type}>
                    <td>
                      <span className="id">{r.cell_type}</span>
                    </td>
                    <td>{describe(r.cell_type) ?? ""}</td>
                    <td className="num">{count(r.impact_left)}</td>
                    <td className="num">{count(r.impact_right)}</td>
                    <td className="num">{count(r.impact_both)}</td>
                    <td className="num">{signedCount(r.superadditivity)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </details>
      )}
    </Finding>
  );
}

function SuperChart({ rows, describe }) {
  const [wrapRef, width] = useWidth();
  const [hover, setHover] = useState(null);
  const keys = rows.map((r) => r.cell_type);
  const rowProps = useRovingRows(keys, (key) => setHover(key == null ? null : keys.indexOf(key)));
  const wide = width >= 520;
  const rowH = wide && !coarsePointer() ? 30 : 46;
  const margin = { top: 12, right: 12, bottom: 46, left: wide ? 120 : 0 };
  const height = rows.length * rowH + margin.top + margin.bottom;
  const barY = wide ? rowH / 2 : 32;
  const peak = Math.max(1, ...rows.map((r) => r.superadditivity));
  const reserve = 96;

  return (
    <div ref={wrapRef}>
      <ChartFrame
        height={height}
        margin={margin}
        role="group"
        label={`Superadditivity of the ${rows.length} most superadditive cell types, from ${signedCount(rows[0].superadditivity)} down to ${signedCount(rows.at(-1).superadditivity)} routes`}
        onPointer={(_x, y) => {
          const i = Math.floor(y / rowH);
          setHover(i >= 0 && i < rows.length ? i : null);
        }}
        onLeave={() => setHover(null)}
        overlay={({ margin: m, width: w }) => {
          if (hover == null || hover >= rows.length) return null;
          const r = rows[hover];
          const x = linear([0, peak], [0, Math.max(10, w - m.left - m.right - reserve)]);
          const superclass = describe(r.cell_type);
          return (
            <Tooltip x={m.left + x(r.superadditivity)} y={m.top + hover * rowH + barY - 8} width={w}>
              <div className="fc-tip">
                <strong>
                  <span className="id">{r.cell_type}</span>
                </strong>
                {superclass && <span className="fc-tip-sub">{superclass}</span>}
                <Row label="Left removed" value={count(r.impact_left)} />
                <Row label="Right removed" value={count(r.impact_right)} />
                <Row label="Both removed" value={count(r.impact_both)} />
                <Row label="Superadditivity" value={signedCount(r.superadditivity)} />
              </div>
            </Tooltip>
          );
        }}
      >
        {(inner) => {
          const span = Math.max(10, inner.width - reserve);
          const x = linear([0, peak], [0, span]);
          const ticks = niceTicks([0, peak], span < 240 ? 3 : 5).filter((t) => Number.isInteger(t) && t <= peak);
          const body = rows.length * rowH;
          return (
            <g>
              {ticks.map((t) => (
                <g key={t} className="tick" transform={`translate(${x(t)},0)`}>
                  <line y1={-4} y2={body} />
                </g>
              ))}
              <g transform={`translate(0,${body})`}>
                <line className="axis-line" x2={inner.width} />
                {ticks.map((t) => (
                  <text key={t} x={x(t)} y={18} textAnchor="middle">
                    {count(t)}
                  </text>
                ))}
                <text className="axis-title" x={inner.width} y={38} textAnchor="end">
                  Routes lost beyond the two single-side losses
                </text>
              </g>
              {rows.map((r, i) => {
                const y = i * rowH;
                const end = x(r.superadditivity);
                return (
                  <g
                    key={r.cell_type}
                    {...rowProps(r.cell_type)}
                    className="fc-row fc-row-static"
                    transform={`translate(0,${y})`}
                    role="img"
                    aria-label={`${r.cell_type}: left ${r.impact_left}, right ${r.impact_right}, both ${r.impact_both}, superadditivity ${r.superadditivity}`}
                  >
                    <rect
                      className="fc-band"
                      x={-margin.left}
                      width={inner.width + margin.left + margin.right}
                      height={rowH}
                      rx={3}
                      style={{ opacity: i === hover ? 1 : 0 }}
                    />
                    <text
                      className="fc-row-label"
                      x={wide ? -12 : 0}
                      y={wide ? rowH / 2 : 15}
                      dy="0.32em"
                      textAnchor={wide ? "end" : "start"}
                    >
                      {r.cell_type}
                    </text>
                    <rect className="fc-bar" x={0} y={barY - 5} width={Math.max(1, end)} height={10} rx={1} />
                    <text className="fc-value" x={end + 6} y={barY} dy="0.32em">
                      {signedCount(r.superadditivity)}
                      <tspan className="fc-value-quiet" dx={6}>
                        {count(r.impact_both)} in all
                      </tspan>
                    </text>
                    <rect className="fc-hit" x={-margin.left} width={inner.width + margin.left + margin.right} height={rowH} rx={3} />
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
