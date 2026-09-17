import { useMemo, useRef, useState } from "react";
import Atlas, { FIELD_LIVE, atlasAspect } from "../Atlas.jsx";
import { ChartFrame, Row, Tooltip } from "../Chart.jsx";
import { Figure, Keynote, Segmented, Sidenote, TextBlock } from "../ui.jsx";
import { useWidth } from "../../lib/hooks.js";
import { count, sentence, signedCount, superclassName } from "../../lib/format.js";
import { linear, niceTicks } from "../../lib/scales.js";
import { Finding, Pending, useResult } from "./Finding.jsx";
import { activateOr, coarsePointer, useRovingRows } from "./useRovingRows.js";
import "../../styles/findings-c.css";

const ID = "pairs";
const TITLE = "Pairs that matter together";
const SHOWN = 10;
const SENSORY = 1;
const MAP_MODES = [
  { value: "pool", label: "Candidate pool" },
  { value: "pair", label: "Selected pair" },
];

const pairKey = (p) => `${p.type_a}|${p.type_b}`;

/**
 * The candidate pool rebuilt from the type table: types ranked by flow lost per partner edge.
 * Returns null unless the cut is unambiguous and matches the exported pool summary.
 */
function candidatePool(types, size, nonzero) {
  const score = types.name.map((_, i) => {
    const degree = types.in_degree[i] + types.out_degree[i];
    return degree > 0 ? types.flow_drop[i] / degree : 0;
  });
  const order = score.map((_, i) => i).sort((a, b) => score[b] - score[a]);
  if (order.length <= size || score[order[size - 1]] <= score[order[size]]) return null;
  const pool = order.slice(0, size);
  if (pool.filter((i) => types.flow_drop[i] > 0).length !== nonzero) return null;
  return pool;
}

export default function Pairs({ types, atlas }) {
  const { data, missing } = useResult("pairs.json");
  if (missing) return <Pending id={ID} title={TITLE} />;
  return data ? <PairsView data={data} types={types} atlas={atlas} /> : null;
}

function PairsView({ data, types, atlas }) {
  const [selected, setSelected] = useState(0);
  const [expanded, setExpanded] = useState(false);
  const [mode, setMode] = useState("pool");
  const index = useMemo(() => new Map(types.name.map((n, i) => [n, i])), [types]);
  const pool = useMemo(
    () => candidatePool(types, data.pool_size, data.pool_types_with_nonzero_single_impact),
    [types, data],
  );
  const aspect = useMemo(() => atlasAspect(types, atlas), [types, atlas]);

  const pairs = data.top_pairs;
  const rows = expanded ? pairs : pairs.slice(0, SHOWN);
  const top = pairs[0];
  const pair = pairs[Math.min(selected, pairs.length - 1)];
  const additive = data.pairs_evaluated - data.pairs_with_positive_synergy - data.pairs_with_negative_synergy;
  const isSensory = (name) => index.has(name) && types.role[index.get(name)] === SENSORY;
  const sensoryPairs = pairs.filter((p) => isSensory(p.type_a) && isSensory(p.type_b)).length;
  const poolSensory = pool ? pool.filter((i) => types.role[i] === SENSORY).length : null;
  const poolCord = pool ? pool.filter((i) => types.compartment[i] === 1).length : null;
  const poolSet = useMemo(() => new Set(pool ?? []), [pool]);
  const pairSet = new Set([pair.type_a, pair.type_b].filter((n) => index.has(n)).map((n) => index.get(n)));
  const describe = (name) => {
    const i = index.get(name);
    if (i == null) return "Not in the type table";
    const anchor = types.anchor[i] >= 0 ? `, mostly in ${types.anchors[types.anchor[i]]}` : "";
    return `${sentence(superclassName(types.superclasses[types.superclass[i]]))}${anchor}`;
  };

  return (
    <Finding
      id={ID}
      title={TITLE}
      stat={count(data.pairs_with_positive_synergy)}
      statLabel={`of ${count(data.pairs_evaluated)} tested pairs of cell types cost more flow together than their two losses added up`}
    >
      <TextBlock
        notes={
          <>
            <Sidenote title="Synergy">
              The flow capacity lost when both types are removed, minus the two losses when each is removed alone.
              It is counted in routes, out of {count(data.intact_flow)} in the intact graph.
            </Sidenote>
            <Sidenote title="The candidate pool">
              The {count(data.pool_size)} types that cost the most flow per connection when removed alone, counting
              input and output connections. All {count(data.pool_types_with_nonzero_single_impact)} cost some flow on
              their own.
            </Sidenote>
            {poolSensory != null && (
              <Keynote value={`${count(poolSensory)} of ${count(data.pool_size)}`}>candidate types are sensory</Keynote>
            )}
          </>
        }
      >
        <p>
          In genetics, two genes are synthetic lethal when losing either one is tolerated and losing both is not. The
          structural analogue is a pair of cell types whose joint removal cuts sensory-to-motor flow capacity by more
          than the two single removals added together, because one can take over capacity the other leaves unused.
        </p>
        <p>
          Every pair among {count(data.pool_size)} candidate types was removed together, {count(data.pairs_evaluated)}{" "}
          pairs in all. Of these, {count(data.pairs_with_positive_synergy)} cost more than their two single losses,{" "}
          {count(data.pairs_with_negative_synergy)} cost less, and the other {count(additive)} are exactly additive. The
          largest excess is {count(data.max_synergy)} routes of {count(data.intact_flow)}, for{" "}
          <span className="id">{top.type_a}</span> and <span className="id">{top.type_b}</span>.
        </p>
        <p>
          Those pairs are not the ones the search was built to find.{" "}
          {poolSensory != null && (
            <>
              Of the {count(data.pool_size)} candidates, {count(poolSensory)} are sensory types, and every pair with
              positive synergy joins two of them, as do{" "}
              {sensoryPairs === pairs.length ? `all ${count(pairs.length)}` : `${count(sensoryPairs)} of the ${count(pairs.length)}`}{" "}
              strongest pairs below.{" "}
            </>
          )}
          {poolSensory == null &&
            `${sensoryPairs === pairs.length ? `All ${count(pairs.length)}` : `${count(sensoryPairs)} of the ${count(pairs.length)}`} strongest pairs join two sensory types. `}
          Sensory types are where flow enters. When two of them feed the same downstream connections, either can fill
          capacity the other leaves unused, so each removal alone is partly absorbed by the other and removing both
          costs more. Positive synergy
          between sensory types is largely a property of how the flow metric treats its sources. Ranking candidates by
          flow lost per connection filled the pool with sensory types, so it never reached the interneuron pairs it was
          meant to probe.
        </p>
      </TextBlock>

      <div className="fc-duo">
        <Figure
          title="Flow lost beyond the two single losses, for the strongest pairs"
          caption={
            <>
              Each bar is one pair&apos;s synergy: the routes lost when both types go, beyond the routes each costs
              alone. The number after it is everything the pair costs together. Select a pair to place both types on the
              map; hover or focus it for the single losses.
            </>
          }
        >
          <PairChart rows={rows} selected={selected} onSelect={(i) => { setSelected(i); setMode("pair"); }} />
          {pairs.length > SHOWN && (
            <button type="button" className="btn fc-toggle" onClick={() => setExpanded((v) => !v)} aria-expanded={expanded}>
              {expanded ? `Show the top ${SHOWN}` : `Show all ${pairs.length} pairs`}
            </button>
          )}
        </Figure>

        <Figure
          variant="field"
          title="Where the candidates sit"
          controls={
            pool ? <Segmented label="Show on the map" options={MAP_MODES} value={mode} onChange={setMode} /> : null
          }
          caption={
            mode === "pool" && pool
              ? "The male central nervous system, brain above and nerve cord below, one point per cell type. Candidate types are drawn in white."
              : "The male central nervous system, brain above and nerve cord below, one point per cell type. The two types of the selected pair are drawn in white."
          }
        >
          <div className="fc-map" style={{ aspectRatio: `${aspect}`, maxWidth: `calc(40rem * ${aspect})` }}>
            <Atlas
              types={types}
              atlas={atlas}
              tone="field"
              highlight={mode === "pool" && pool ? poolSet : pairSet}
              highlightTone="neutral"
              label={
                mode === "pool" && pool
                  ? `Map of the central nervous system with the ${count(pool.length)} candidate types highlighted; ${count(poolCord)} lie in the nerve cord.`
                  : `Map of the central nervous system with ${pair.type_a} and ${pair.type_b} highlighted`
              }
            />
          </div>
          <div className="fc-map-key" aria-hidden="true">
            <span>
              <svg width="10" height="10" viewBox="-5 -5 10 10">
                <rect x="-3" y="-3" width="6" height="6" style={{ fill: "var(--field-ink)" }} />
              </svg>
              {mode === "pool" && pool ? "Candidate types" : "Selected pair"}
            </span>
            <span>
              <svg width="10" height="10" viewBox="-5 -5 10 10">
                <rect x="-2" y="-2" width="4" height="4" style={{ fill: `var(--field-live, ${FIELD_LIVE})`, opacity: 0.6 }} />
              </svg>
              Other cell types
            </span>
          </div>
          <div className="fc-readout" aria-live="polite">
            {mode === "pool" && pool ? (
              <>
                <strong>
                  {count(poolSensory)} of {count(pool.length)} sensory
                </strong>
                <span>
                  {count(poolCord)} candidates lie in the nerve cord and {count(pool.length - poolCord)} in the brain.
                </span>
              </>
            ) : (
              <>
                <strong>
                  <span className="id">{pair.type_a}</span> and <span className="id">{pair.type_b}</span>
                </strong>
                <span>
                  <span className="id">{pair.type_a}</span>: {describe(pair.type_a)}
                </span>
                <span>
                  <span className="id">{pair.type_b}</span>: {describe(pair.type_b)}
                </span>
                <span>
                  Alone they cost {count(pair.impact_a)} and {count(pair.impact_b)} routes; together{" "}
                  {count(pair.joint_impact)}, a synergy of {signedCount(pair.synergy)}.
                </span>
              </>
            )}
          </div>
        </Figure>
      </div>

      <dl className="facts">
        <div>
          <dt>Pairs tested, every pair among {count(data.pool_size)} candidates</dt>
          <dd>{count(data.pairs_evaluated)}</dd>
        </div>
        <div>
          <dt>Cost more together than their two single losses</dt>
          <dd>{count(data.pairs_with_positive_synergy)}</dd>
        </div>
        <div>
          <dt>Cost less, because the two losses overlap</dt>
          <dd>{count(data.pairs_with_negative_synergy)}</dd>
        </div>
        <div>
          <dt>Exactly additive</dt>
          <dd>{count(additive)}</dd>
        </div>
      </dl>

      <details className="more">
        <summary>The {pairs.length} strongest pairs as a table</summary>
        <div className="table-wrap">
          <table className="data">
            <thead>
              <tr>
                <th>First type</th>
                <th>Second type</th>
                <th className="num">First alone</th>
                <th className="num">Second alone</th>
                <th className="num">Together</th>
                <th className="num">Synergy</th>
                <th className="num">Flow left</th>
              </tr>
            </thead>
            <tbody>
              {pairs.map((p) => (
                <tr key={pairKey(p)}>
                  <td>
                    <span className="id">{p.type_a}</span>
                  </td>
                  <td>
                    <span className="id">{p.type_b}</span>
                  </td>
                  <td className="num">{count(p.impact_a)}</td>
                  <td className="num">{count(p.impact_b)}</td>
                  <td className="num">{count(p.joint_impact)}</td>
                  <td className="num">{signedCount(p.synergy)}</td>
                  <td className="num">{count(p.flow_after)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </details>
    </Finding>
  );
}

function PairChart({ rows, selected, onSelect }) {
  const [wrapRef, width] = useWidth();
  const [hover, setHover] = useState(null);
  const rowsRef = useRef(rows);
  rowsRef.current = rows;
  const keys = rows.map(pairKey);
  const rowProps = useRovingRows(keys, (key) => setHover(key == null ? null : keys.indexOf(key)));
  const wide = width >= 520;
  const rowH = wide && !coarsePointer() ? 30 : 46;
  const margin = { top: 12, right: 12, bottom: 46, left: wide ? 196 : 0 };
  const height = rows.length * rowH + margin.top + margin.bottom;
  const barY = wide ? rowH / 2 : 32;
  const peak = Math.max(1, ...rows.map((r) => r.synergy));
  const reserve = 96;

  return (
    <div ref={wrapRef}>
      <ChartFrame
        height={height}
        margin={margin}
        role="group"
        label={`Synergy of the ${rows.length} strongest pairs of cell types, from ${signedCount(rows[0].synergy)} down to ${signedCount(rows.at(-1).synergy)} routes`}
        onPointer={(_x, y) => {
          const i = Math.floor(y / rowH);
          setHover(i >= 0 && i < rowsRef.current.length ? i : null);
        }}
        onLeave={() => setHover(null)}
        overlay={({ margin: m, width: w }) => {
          if (hover == null || hover >= rows.length) return null;
          const r = rows[hover];
          const x = linear([0, peak], [0, Math.max(10, w - m.left - m.right - reserve)]);
          return (
            <Tooltip x={m.left + x(r.synergy)} y={m.top + hover * rowH + barY - 8} width={w}>
              <div className="fc-tip">
                <strong>
                  <span className="id">{r.type_a}</span> and <span className="id">{r.type_b}</span>
                </strong>
                <Row label={`${r.type_a} alone`} value={count(r.impact_a)} />
                <Row label={`${r.type_b} alone`} value={count(r.impact_b)} />
                <Row label="Both together" value={count(r.joint_impact)} />
                <Row label="Synergy" value={signedCount(r.synergy)} />
                <Row label="Routes left" value={count(r.flow_after)} />
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
                  Routes lost beyond the two single losses
                </text>
              </g>
              {rows.map((r, i) => {
                const on = i === selected;
                const y = i * rowH;
                const end = x(r.synergy);
                return (
                  <g
                    key={keys[i]}
                    {...rowProps(keys[i])}
                    className="fc-row"
                    transform={`translate(0,${y})`}
                    role="button"
                    aria-pressed={on}
                    aria-label={`${r.type_a} and ${r.type_b}: alone ${r.impact_a} and ${r.impact_b}, together ${r.joint_impact}, synergy ${r.synergy}`}
                    onClick={() => onSelect(i)}
                    onKeyDown={(event) => activateOr(event, () => onSelect(i), rowProps(keys[i]).onKeyDown)}
                  >
                    <rect
                      className="fc-band"
                      x={-margin.left}
                      width={inner.width + margin.left + margin.right}
                      height={rowH}
                      rx={3}
                      style={{ opacity: on || i === hover ? 1 : 0 }}
                    />
                    <text
                      className="fc-row-label"
                      x={wide ? -12 : 0}
                      y={wide ? rowH / 2 : 15}
                      dy="0.32em"
                      textAnchor={wide ? "end" : "start"}
                    >
                      {r.type_a} and {r.type_b}
                    </text>
                    <rect
                      className={on ? "fc-bar-on" : "fc-bar"}
                      x={0}
                      y={barY - 5}
                      width={Math.max(1, end)}
                      height={10}
                      rx={1}
                    />
                    <text className="fc-value" x={end + 6} y={barY} dy="0.32em">
                      {signedCount(r.synergy)}
                      <tspan className="fc-value-quiet" dx={6}>
                        {count(r.joint_impact)} in all
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
