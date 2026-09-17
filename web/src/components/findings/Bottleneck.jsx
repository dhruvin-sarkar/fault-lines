import { useMemo, useState } from "react";
import Atlas, { FIELD_LIVE, atlasAspect } from "../Atlas.jsx";
import { ChartFrame, Row, Tooltip } from "../Chart.jsx";
import { Figure, Keynote, Segmented, Sidenote, TextBlock } from "../ui.jsx";
import { useWidth } from "../../lib/hooks.js";
import { count, fixed, numberWord, percent, sentence, superclassName } from "../../lib/format.js";
import { linear } from "../../lib/scales.js";
import { Finding, Pending, useResult } from "./Finding.jsx";
import { activateOr, coarsePointer, useRovingRows } from "./useRovingRows.js";
import "../../styles/findings-c.css";

const ID = "bottleneck";
const TITLE = "A hidden bottleneck";

const plural = (n, one, many) => (n === 1 ? one : many);

function ordinal(n) {
  const tens = n % 100;
  if (tens >= 11 && tens <= 13) return `${n}th`;
  return `${n}${["th", "st", "nd", "rd"][n % 10] ?? "th"}`;
}

export default function Bottleneck({ types, atlas }) {
  const { data, missing } = useResult("bottleneck.json");
  if (missing) return <Pending id={ID} title={TITLE} />;
  return data?.example ? <BottleneckView data={data} types={types} atlas={atlas} /> : null;
}

function BottleneckView({ data, types, atlas }) {
  const ex = data.example;
  const criteria = data.criteria;
  const candidates = data.candidates?.length ? data.candidates : [
    {
      cell_type: ex.cell_type,
      superclass: ex.superclass,
      degree: ex.degree,
      degree_pct: ex.degree_percentile,
      pagerank_pct: ex.pagerank_percentile,
      sm_betweenness: ex.sm_betweenness,
      sm_betweenness_pct: ex.sm_betweenness_percentile,
    },
  ];
  const [selected, setSelected] = useState(ex.cell_type);
  const index = useMemo(() => new Map(types.name.map((n, i) => [n, i])), [types]);
  const aspect = useMemo(() => atlasAspect(types, atlas), [types, atlas]);
  const marked = useMemo(
    () => new Set(candidates.map((c) => index.get(c.cell_type)).filter((i) => i != null)),
    [candidates, index],
  );

  const lost = ex.intact_flow - ex.flow_after_removal;
  const topShare = 100 - criteria.sm_betweenness_percentile_at_least;
  const current = candidates.find((c) => c.cell_type === selected) ?? candidates[0];
  const currentIndex = index.get(current.cell_type);
  const n = data.n_candidates;

  return (
    <Finding
      id={ID}
      title={TITLE}
      stat={percent(ex.share_of_shortest_routes, 2)}
      statLabel={`of shortest sensory-to-motor routes pass through ${ex.cell_type}, a type of ${count(ex.n_neurons)} ${plural(ex.n_neurons, "neuron", "neurons")}`}
    >
      <TextBlock
        notes={
          <>
            <Sidenote title="Degree">
              Input partner types plus output partner types, so a partner connected in both directions counts twice.
              The median type has {count(ex.median_degree)}.
            </Sidenote>
            <Sidenote title="Sensory-motor betweenness">
              The number of shortest routes from sensory types to descending or motor types that pass through a type,
              summed over all {count(ex.reachable_pairs)} connected pairs.
            </Sidenote>
            <Keynote value={`${count(lost)} of ${count(ex.intact_flow)}`}>
              routes lost when <span className="id">{ex.cell_type}</span> is removed
            </Keynote>
          </>
        }
      >
        <p>
          Degree and PageRank are the usual shortcuts for finding important nodes. {count(n)} cell{" "}
          {plural(n, "type ranks", "types rank")} in the bottom half by both, yet in the top {fixed(topShare, 0)}% by
          sensory-motor betweenness.
        </p>
        <p>
          The most extreme is <span className="id">{ex.cell_type}</span>, a {superclassName(ex.superclass)} type of{" "}
          {count(ex.n_neurons)} {plural(ex.n_neurons, "neuron", "neurons")} with {count(ex.in_degree)} input and{" "}
          {count(ex.out_degree)} output partner types. It sits at the {ordinal(Math.round(ex.pagerank_percentile))} percentile
          by PageRank, and ranks {count(ex.sm_betweenness_rank)} of {count(types.name.length)} by the routes between
          sensory input and motor output.
        </p>
        <p>
          Lying on many shortest routes is not the same as being needed. Removing{" "}
          <span className="id">{ex.cell_type}</span> alone costs {count(lost)} of {count(ex.intact_flow)} routes and
          disconnects {count(ex.pairs_lost_when_removed)} sensory-motor pairs, while{" "}
          {count(ex.pairs_with_longer_shortest_path_when_removed)} pairs take a longer route. Parallel routes exist; they
          are longer. Whether the fly depends on this type has not been tested.
        </p>
      </TextBlock>

      <div className="fc-duo">
        <Figure
          title={`Where the ${numberWord(candidates.length)} ${plural(candidates.length, "candidate ranks", "candidates rank")} among all types`}
          caption={
            <>
              Percentiles among all {count(types.name.length)} types. The shaded span is where a type must fall to
              qualify, and the dashed line is the cut. Betweenness is drawn from{" "}
              {fixed(betweennessFloor(candidates, criteria), 0)} to 100 so the candidates separate. Select a row to
              find that type on the map.
            </>
          }
        >
          <CandidateChart candidates={candidates} criteria={criteria} selected={current.cell_type} onSelect={setSelected} />
        </Figure>

        <Figure
          variant="field"
          title="Where they sit in the nervous system"
          controls={
            candidates.length > 1 ? (
              <Segmented
                label="Candidate"
                options={candidates.map((c) => ({ value: c.cell_type, label: c.cell_type }))}
                value={current.cell_type}
                onChange={setSelected}
              />
            ) : null
          }
          caption="Brain above, nerve cord below, one point per cell type. The candidates are drawn in white; the selected one is ringed."
        >
          <div className="fc-map" style={{ aspectRatio: `${aspect}`, maxWidth: `calc(40rem * ${aspect})` }}>
            <Atlas
              types={types}
              atlas={atlas}
              tone="field"
              highlight={marked}
              highlightTone="neutral"
              focus={currentIndex}
              label={`Map of the central nervous system with the ${count(marked.size)} candidate types highlighted and ${current.cell_type} ringed`}
            />
          </div>
          <div className="fc-map-key" aria-hidden="true">
            <span>
              <svg width="14" height="14" viewBox="-7 -7 14 14">
                <circle r="5.5" style={{ fill: "none", stroke: "var(--field-ink)", strokeWidth: 1.5 }} />
              </svg>
              Selected
            </span>
            <span>
              <svg width="10" height="10" viewBox="-5 -5 10 10">
                <rect x="-3" y="-3" width="6" height="6" style={{ fill: "var(--field-ink)" }} />
              </svg>
              Candidates
            </span>
            <span>
              <svg width="10" height="10" viewBox="-5 -5 10 10">
                <rect x="-2" y="-2" width="4" height="4" style={{ fill: `var(--field-live, ${FIELD_LIVE})`, opacity: 0.6 }} />
              </svg>
              Other cell types
            </span>
          </div>
          {currentIndex != null && (
            <div className="fc-readout" aria-live="polite">
              <strong>
                <span className="id">{current.cell_type}</span>
              </strong>
              <span>
                {sentence(superclassName(current.superclass))}, {count(types.neurons[currentIndex])}{" "}
                {plural(types.neurons[currentIndex], "neuron", "neurons")}
                {types.anchor[currentIndex] >= 0 ? `, mostly in ${types.anchors[types.anchor[currentIndex]]}` : ""}
              </span>
              <span>
                {count(types.in_degree[currentIndex])} input and {count(types.out_degree[currentIndex])} output partner
                types. Removed alone it costs {count(types.flow_drop[currentIndex])} of {count(ex.intact_flow)} routes.
              </span>
            </div>
          )}
        </Figure>
      </div>

      <Figure
        title={`The strongest partners of ${ex.cell_type}`}
        caption={
          <>
            The five strongest of {count(ex.in_degree)} input and {count(ex.out_degree)} output partner types, with
            synapse counts. Line width scales with synapses. Hover or focus a partner for its superclass.
          </>
        }
      >
        <PartnerDiagram example={ex} />
      </Figure>

      <dl className="facts">
        <div>
          <dt>
            Routes left without <span className="id">{ex.cell_type}</span>, of {count(ex.intact_flow)}
          </dt>
          <dd>{count(ex.flow_after_removal)}</dd>
        </div>
        <div>
          <dt>Sensory-motor pairs disconnected when it alone is removed</dt>
          <dd>{count(ex.pairs_lost_when_removed)}</dd>
        </div>
        <div>
          <dt>Pairs whose shortest route gets longer without it</dt>
          <dd>{count(ex.pairs_with_longer_shortest_path_when_removed)}</dd>
        </div>
        <div>
          <dt>Synapses in and out, within the graph</dt>
          <dd>
            {count(ex.in_strength)} / {count(ex.out_strength)}
          </dd>
        </div>
      </dl>

      <details className="more">
        <summary>
          All {numberWord(candidates.length)} {plural(candidates.length, "candidate", "candidates")} as a table
        </summary>
        <div className="table-wrap">
          <table className="data">
            <thead>
              <tr>
                <th>Cell type</th>
                <th>Superclass</th>
                <th className="num">Degree, in + out</th>
                <th className="num">Degree percentile</th>
                <th className="num">PageRank percentile</th>
                <th className="num">Sensory-motor betweenness</th>
                <th className="num">Percentile</th>
              </tr>
            </thead>
            <tbody>
              {candidates.map((c) => {
                const i = index.get(c.cell_type);
                return (
                  <tr key={c.cell_type}>
                    <td>
                      <span className="id">{c.cell_type}</span>
                    </td>
                    <td>{sentence(superclassName(c.superclass))}</td>
                    <td className="num">
                      {count(c.degree)}
                      {i != null && types.in_degree[i] + types.out_degree[i] === c.degree
                        ? ` (${count(types.in_degree[i])} + ${count(types.out_degree[i])})`
                        : ""}
                    </td>
                    <td className="num">{fixed(c.degree_pct, 1)}</td>
                    <td className="num">{fixed(c.pagerank_pct, 1)}</td>
                    <td className="num">{count(c.sm_betweenness)}</td>
                    <td className="num">{fixed(c.sm_betweenness_pct, 2)}</td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </details>
    </Finding>
  );
}

/** Lower edge of the betweenness axis: one whole percentile below the lowest candidate or the cut. */
function betweennessFloor(candidates, criteria) {
  const low = Math.min(criteria.sm_betweenness_percentile_at_least, ...candidates.map((c) => c.sm_betweenness_pct));
  return Math.max(0, Math.floor(low) - 1);
}

function CandidateChart({ candidates, criteria, selected, onSelect }) {
  const [wrapRef, width] = useWidth();
  const floor = betweennessFloor(candidates, criteria);
  const measures = [
    {
      key: "degree_pct",
      title: "Degree",
      rule: `Qualifies below ${fixed(criteria.degree_percentile_below, 0)}`,
      domain: [0, 100],
      cut: criteria.degree_percentile_below,
      below: true,
      digits: 0,
    },
    {
      key: "pagerank_pct",
      title: "PageRank",
      rule: `Qualifies below ${fixed(criteria.pagerank_percentile_below, 0)}`,
      domain: [0, 100],
      cut: criteria.pagerank_percentile_below,
      below: true,
      digits: 0,
    },
    {
      key: "sm_betweenness_pct",
      title: "Sensory-motor betweenness",
      rule: `Qualifies from ${fixed(criteria.sm_betweenness_percentile_at_least, 0)}`,
      domain: [floor, 100],
      cut: criteria.sm_betweenness_percentile_at_least,
      below: false,
      digits: 2,
    },
  ];
  const keys = candidates.map((c) => c.cell_type);
  const rowProps = useRovingRows(keys, () => {});
  const wide = width >= 440;
  const rowH = wide && !coarsePointer() ? 28 : 40;
  const headH = wide ? 26 : 40;
  const axisH = 26;
  const gap = 22;
  const groupH = headH + candidates.length * rowH + axisH;
  const margin = { top: 4, right: 0, bottom: 4, left: wide ? 96 : 84 };
  const height = measures.length * (groupH + gap) - gap + margin.top + margin.bottom;

  return (
    <div ref={wrapRef}>
      <ChartFrame
        height={height}
        margin={margin}
        role="group"
        label={`Percentiles of the ${candidates.length} candidates by degree, PageRank and sensory-motor betweenness`}
      >
        {(inner) => {
          const valueW = 44;
          return measures.map((m, g) => {
            const top = g * (groupH + gap);
            const x = linear(m.domain, [0, Math.max(10, inner.width - valueW - 8)]);
            const span = x.domain;
            const cx = x(m.cut);
            const zone = m.below ? [x(span[0]), cx] : [cx, x(span[1])];
            const tracksTop = top + headH;
            const tracksH = candidates.length * rowH;
            const ticks = m.domain[0] === 0 ? [0, 50, 100] : [m.domain[0], m.cut, 100].filter((v, i, a) => a.indexOf(v) === i);
            return (
              <g key={m.key}>
                <text className="fc-head" x={-margin.left} y={top + 13} style={{ fill: "var(--ink)" }} aria-hidden="true">
                  {m.title} percentile
                </text>
                <text className="fc-row-sub" x={wide ? inner.width : -margin.left} y={wide ? top + 13 : top + 29} textAnchor={wide ? "end" : "start"}>
                  {m.rule}
                </text>
                <rect className="fc-zone" x={zone[0]} y={tracksTop} width={Math.max(0, zone[1] - zone[0])} height={tracksH} />
                <line className="fc-criterion" x1={cx} x2={cx} y1={tracksTop - 3} y2={tracksTop + tracksH + 3} />
                {candidates.map((c, r) => {
                  const on = c.cell_type === selected;
                  const y = tracksTop + r * rowH;
                  const cy = y + rowH / 2;
                  const value = c[m.key];
                  const keyboard =
                    g === 0
                      ? {
                          ...rowProps(c.cell_type),
                          role: "button",
                          "aria-pressed": on,
                          "aria-label": `${c.cell_type}: degree percentile ${fixed(c.degree_pct, 1)}, PageRank percentile ${fixed(c.pagerank_pct, 1)}, sensory-motor betweenness percentile ${fixed(c.sm_betweenness_pct, 2)}`,
                          onKeyDown: (event) => activateOr(event, () => onSelect(c.cell_type), rowProps(c.cell_type).onKeyDown),
                        }
                      : { "aria-hidden": true };
                  return (
                    <g key={c.cell_type} {...keyboard} className="fc-row" onClick={() => onSelect(c.cell_type)}>
                      <rect className="fc-hit" x={-margin.left} y={y} width={inner.width + margin.left} height={rowH} />
                      <text className={on ? "fc-row-label" : "fc-row-label is-off"} x={-margin.left} y={cy} dy="0.32em">
                        {c.cell_type}
                      </text>
                      <line className="fc-track" x1={0} x2={x(span[1])} y1={cy} y2={cy} />
                      {on ? (
                        <circle cx={x(value)} cy={cy} r={5.5} className="fc-dot" />
                      ) : (
                        <circle cx={x(value)} cy={cy} r={4.5} className="fc-ring" />
                      )}
                      <text className={on ? "fc-value" : "fc-value-quiet"} x={inner.width} y={cy} dy="0.32em" textAnchor="end">
                        {fixed(value, m.digits)}
                      </text>
                    </g>
                  );
                })}
                <g transform={`translate(0,${tracksTop + tracksH})`}>
                  {ticks.map((t) => (
                    <text key={t} x={x(t)} y={17} textAnchor={t === span[0] ? "start" : t === span[1] ? "end" : "middle"}>
                      {count(t)}
                    </text>
                  ))}
                </g>
              </g>
            );
          });
        }}
      </ChartFrame>
    </div>
  );
}

function PartnerDiagram({ example }) {
  const [ref, width] = useWidth();
  const [active, setActive] = useState(null);
  const inputs = example.strongest_inputs;
  const outputs = example.strongest_outputs;
  const rows = Math.max(inputs.length, outputs.length, 1);
  const rowH = 40;
  const top = 30;
  const height = top + rows * rowH + 8;
  const labelW = Math.max(84, Math.min(170, width * 0.26));
  const cx = width / 2;
  const cy = top + (rows * rowH) / 2;
  const max = Math.max(1, ...inputs.map((p) => p.synapses), ...outputs.map((p) => p.synapses));
  const stroke = (s) => 1.25 + 10 * Math.sqrt(s / max);
  const hovered = active && [...inputs.map((p, i) => ({ ...p, side: "in", i })), ...outputs.map((p, i) => ({ ...p, side: "out", i }))].find(
    (p) => `${p.side}-${p.cell_type}` === active,
  );
  const rowY = (list, i) => top + i * rowH + rowH / 2 + ((rows - list.length) * rowH) / 2;
  const keys = [...inputs.map((p) => `in-${p.cell_type}`), ...outputs.map((p) => `out-${p.cell_type}`)];
  const rowProps = useRovingRows(keys, setActive);

  const side = (list, dir) =>
    list.map((p, i) => {
      const y = rowY(list, i);
      const lx = dir === "in" ? labelW : width - labelW;
      const x0 = dir === "in" ? lx + 8 : cx + 12;
      const x1 = dir === "in" ? cx - 12 : lx - 8;
      const ya = dir === "in" ? y : cy;
      const yb = dir === "in" ? cy : y;
      const mid = (x0 + x1) / 2;
      const key = `${dir}-${p.cell_type}`;
      const on = active === key;
      const dim = active && !on;
      return (
        <g
          key={key}
          {...rowProps(key)}
          className="fc-row fc-row-static"
          role="img"
          aria-label={`${dir === "in" ? "Input from" : "Output to"} ${p.cell_type}, ${superclassName(p.superclass)}, ${count(p.synapses)} synapses`}
          onPointerEnter={() => setActive(key)}
        >
          <path
            className="fc-link"
            d={`M${x0} ${ya}C${mid} ${ya} ${mid} ${yb} ${x1} ${yb}`}
            strokeWidth={stroke(p.synapses)}
            style={{ opacity: dim ? 0.16 : on ? 0.9 : 0.4 }}
          />
          <text className="fc-row-label" x={lx} y={y - 2} textAnchor={dir === "in" ? "end" : "start"} style={{ opacity: dim ? 0.5 : 1 }}>
            {p.cell_type}
          </text>
          <text className="fc-value-quiet" x={lx} y={y + 12} textAnchor={dir === "in" ? "end" : "start"}>
            {count(p.synapses)}
          </text>
          <rect
            className="fc-hit"
            x={dir === "in" ? 0 : cx}
            y={y - rowH / 2}
            width={Math.max(0, dir === "in" ? cx : width - cx)}
            height={rowH}
            rx={3}
          />
        </g>
      );
    });

  if (!width) return <div ref={ref} className="chart" style={{ height }} />;

  return (
    <div ref={ref} className="chart">
      <svg
        width={width}
        height={height}
        role="group"
        aria-label={`Strongest input and output partner types of ${example.cell_type}`}
        onPointerLeave={() => setActive(null)}
      >
        <text className="fc-head" x={labelW} y={12} textAnchor="end" aria-hidden="true">
          Inputs
        </text>
        <text className="fc-head" x={width - labelW} y={12} textAnchor="start" aria-hidden="true">
          Outputs
        </text>
        {side(inputs, "in")}
        {side(outputs, "out")}
        <circle cx={cx} cy={cy} r={8} className="fc-dot" />
        <text className="fc-row-label" x={cx} y={cy - 16} textAnchor="middle" aria-hidden="true">
          {example.cell_type}
        </text>
      </svg>
      {hovered && (
        <Tooltip x={hovered.side === "in" ? labelW / 2 + 40 : width - labelW / 2 - 40} y={rowY(hovered.side === "in" ? inputs : outputs, hovered.i) - 14} width={width}>
          <div className="fc-tip">
            <strong>
              <span className="id">{hovered.cell_type}</span>
            </strong>
            <span className="fc-tip-sub">{sentence(superclassName(hovered.superclass))}</span>
            <Row
              label={hovered.side === "in" ? `Synapses onto ${example.cell_type}` : `Synapses from ${example.cell_type}`}
              value={count(hovered.synapses)}
            />
          </div>
        </Tooltip>
      )}
    </div>
  );
}
