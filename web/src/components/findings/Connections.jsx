import { useState } from "react";
import { ChartFrame, Row, Tooltip, XAxis, YAxis } from "../Chart.jsx";
import { Figure, Keynote, Segmented, Sidenote, TextBlock } from "../ui.jsx";
import { Finding, Pending, useResult } from "./Finding.jsx";
import { LineLabels, inkColor, labelRoom, sentence, xTicks } from "./marks.jsx";
import { count, indexAt, percent, strategyLabel } from "../../lib/format.js";
import { useWidth } from "../../lib/hooks.js";
import { line, linear } from "../../lib/scales.js";
import "../../styles/findings-b.css";

const ID = "connections";
const TITLE = "Connections, not types";
const ORDERS = [
  { id: "strongest", label: "strongest first", stroke: "var(--ink)", dash: undefined },
  { id: "weakest", label: "weakest first", stroke: "var(--ink-2)", dash: "1.5 4" },
  { id: "random", label: "random order", stroke: inkColor("random"), dash: "7 5" },
];
const METRICS = [
  { value: "flow", label: "Flow capacity", axis: "Flow capacity, share of intact" },
  { value: "reachable_pairs", label: "Reachable pairs", axis: "Reachable sensory-motor pairs, share of intact" },
];
const TIP_HALF = 120;

export default function Connections({ percolation }) {
  const { data, missing } = useResult("edges.json");
  if (missing) return <Pending id={ID} title={TITLE} />;
  return data ? <ConnectionsView data={data} percolation={percolation} /> : null;
}

/** Summary of the random order's halving point: the mean over trials with their range when those were exported. */
function randomSummary(order) {
  if (!order || order.critical_fraction == null) return null;
  const trials = (order.critical_fraction_trials ?? []).filter((v) => v != null);
  const range = order.critical_fraction_range;
  return {
    value: order.critical_fraction,
    trials: trials.length > 1 ? trials.length : null,
    range: trials.length > 1 && range?.length === 2 ? range : null,
  };
}

function ConnectionsView({ data, percolation }) {
  const orders = ORDERS.filter((o) => data.orders[o.id]);
  const fc = (id) => data.orders[id]?.critical_fraction ?? null;
  const strongest = fc("strongest");
  const random = randomSummary(data.orders.random);
  const weakest = data.orders.weakest;
  const typeTarget = percolation.strategies.out_strength?.critical_fraction;
  const typeRandom = percolation.strategies.random?.critical_fraction;
  const edgeRatio = strongest && random ? random.value / strongest : null;
  const typeRatio = typeTarget && typeRandom ? typeRandom / typeTarget : null;
  const weakestEnd = weakest ? weakest.flow.at(-1) / weakest.flow[0] : null;
  const weakestLast = weakest ? weakest.fraction_removed.at(-1) : null;

  const randomText = random
    ? random.trials
      ? `a mean of ${percent(random.value)} over ${count(random.trials)} random orders${random.range ? ` (range ${percent(random.range[0])} to ${percent(random.range[1])})` : ""}`
      : `${percent(random.value)} for a random order`
    : null;

  return (
    <Finding
      id={ID}
      title={TITLE}
      stat={percent(strongest)}
      statLabel="of connections removed, strongest first, halves sensory-to-motor flow capacity"
    >
      <TextBlock
        notes={
          <>
            <Sidenote title="A connection">
              A directed edge between two cell types, kept when it supplies enough of the target type&apos;s input
              synapses to pass the graph&apos;s threshold; there are {count(data.edges)} of them.
            </Sidenote>
            {typeTarget != null && (
              <Keynote value={percent(typeTarget)}>
                of cell types removed by {strategyLabel("out_strength")} halves flow, against {percent(typeRandom)} at random
              </Keynote>
            )}
          </>
        }
      >
        <p>
          Here the unit of removal is the connection between two cell types rather than the type. Connections are taken
          away in batches of {percent(data.batch_fraction_of_edges, 0)} of all {count(data.edges)}, ordered by synapse
          count: strongest first, weakest first, or in a random order.
        </p>
        <p>
          Strongest first halves flow capacity at {percent(strongest)} of connections removed
          {randomText ? `, against ${randomText}` : ""}.{" "}
          {weakest &&
            (fc("weakest") == null
              ? `Weakest first never halves it: with ${percent(weakestLast, 0)} of connections gone, ${percent(weakestEnd, 0)} of the flow capacity is still there.`
              : `Weakest first halves it at ${percent(fc("weakest"))}.`)}
        </p>
        {edgeRatio != null && typeRatio != null && (
          <p>
            Ranking connections by synapse count speeds up the loss, but far less than ranking cell types does. A random
            order of connections takes {edgeRatio.toFixed(1)} times as long as strongest first to halve flow; for cell
            types, random removal takes {typeRatio.toFixed(1)} times as long as removal by {strategyLabel("out_strength")}.
          </p>
        )}
        <p>
          Flow capacity counts each connection once, whatever its synapse count. A heavy connection running alongside
          others can go without costing a route, while a light connection that is the only way across cannot. In this
          measure, routing depends more on the cell types where many connections meet than on the heaviest single
          connections.
        </p>
      </TextBlock>

      <ConnectionsChart data={data} orders={orders} random={random} />

      <details className="more">
        <summary>Curves as a table</summary>
        <div className="table-wrap">
          <table className="data">
            <thead>
              <tr>
                <th className="num">Connections removed</th>
                {orders.map((o) => (
                  <th key={o.id} className="num">
                    Flow, {o.label}
                  </th>
                ))}
                {orders.map((o) => (
                  <th key={o.id} className="num">
                    Pairs, {o.label}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {data.orders[orders[0].id].fraction_removed.map((f, i, all) =>
                i % 5 === 0 || i === all.length - 1 ? (
                  <tr key={f}>
                    <td className="num">{percent(f)}</td>
                    {orders.map((o) => (
                      <td key={o.id} className="num">
                        {count(data.orders[o.id].flow[i])}
                      </td>
                    ))}
                    {orders.map((o) => (
                      <td key={o.id} className="num">
                        {count(data.orders[o.id].reachable_pairs[i])}
                      </td>
                    ))}
                  </tr>
                ) : null,
              )}
            </tbody>
          </table>
        </div>
      </details>
    </Finding>
  );
}

function ConnectionsChart({ data, orders, random }) {
  const [metric, setMetric] = useState("flow");
  const [hover, setHover] = useState(null);
  const [sizer, width] = useWidth();
  const narrow = width < 620;
  const current = METRICS.find((m) => m.value === metric);
  const fractions = data.orders[orders[0].id].fraction_removed;
  const xMax = Math.max(0.5, fractions.at(-1));
  const margin = { top: 32, right: labelRoom(orders.map((o) => o.label), narrow), bottom: 46, left: 54 };
  const share = (id, i) => data.orders[id][metric][i] / data.orders[id][metric][0];
  const randomTrials = data.random_trials;

  return (
    <Figure
      title="What remains as connections are removed"
      controls={<Segmented label="Measure" options={METRICS} value={metric} onChange={setMetric} />}
      caption={
        <>
          Each line follows one removal order as a share of the intact value. A connection counts once in flow capacity
          whatever its synapse count.{" "}
          {metric === "flow"
            ? `Red marks show where flow capacity falls to half${orders.some((o) => data.orders[o.id].critical_fraction == null) ? `; ${orders.filter((o) => data.orders[o.id].critical_fraction == null).map((o) => o.label).join(" and ")} never gets there` : ""}. `
            : ""}
          {randomTrials > 1 &&
            `The random line is the first of ${count(randomTrials)} random orders${metric === "flow" && random?.range ? `; the red bracket spans the halving points of all ${count(random.trials)}, and its dot their mean` : ""}.`}{" "}
          Hover to read the orders at one level.
        </>
      }
    >
      <div ref={sizer}>
        <ChartFrame
          height={narrow ? 320 : 380}
          margin={margin}
          label={`Line chart of ${current.axis} against the share of connections removed, for ${orders.map((o) => o.label).join(", ")}`}
          onPointer={(x, _y, inner) => setHover(indexAt(fractions, Math.max(0, Math.min(xMax, (x / inner.width) * xMax))))}
          onLeave={() => setHover(null)}
          overlay={({ width: full, height, margin: m }) => {
            if (hover == null) return null;
            const w = full - m.left - m.right;
            const x = m.left + (fractions[hover] / xMax) * w;
            const flip = x > m.left + w / 2;
            const left = Math.max(TIP_HALF, Math.min(full - TIP_HALF, x + (flip ? -TIP_HALF - 12 : TIP_HALF + 12)));
            return (
              <Tooltip x={left} y={m.top + height * 0.55} width={full}>
                <strong className="fb-tip-head">{percent(fractions[hover])} of connections removed</strong>
                {orders.map((o) => (
                  <Row
                    key={o.id}
                    label={sentence(o.label)}
                    value={`${count(data.orders[o.id][metric][hover])} (${percent(share(o.id, hover), 0)})`}
                    color={o.stroke}
                  />
                ))}
              </Tooltip>
            );
          }}
        >
          {(inner) => {
            const xs = linear([0, xMax], [0, inner.width]);
            const ys = linear([0, 1], [inner.height, 0]);
            const half = ys(0.5);
            return (
              <>
                <YAxis
                  scale={ys}
                  ticks={[0, 0.25, 0.5, 0.75, 1]}
                  width={inner.width}
                  format={(v) => percent(v, 0)}
                  title={narrow ? "Share of intact" : current.axis}
                />
                <XAxis
                  scale={xs}
                  ticks={xTicks(xMax, narrow)}
                  height={inner.height}
                  width={inner.width}
                  format={(v) => percent(v, 0)}
                  title="Connections removed"
                />
                <line className="fb-ref" x1={0} x2={inner.width} y1={half} y2={half} />
                <text className="fb-note" x={6} y={half + 16}>
                  Half of intact
                </text>
                {orders.map((o) => (
                  <path
                    key={o.id}
                    className="fb-series"
                    d={line(data.orders[o.id][metric].map((_, i) => [xs(fractions[i]), ys(share(o.id, i))]))}
                    style={{ stroke: o.stroke, strokeDasharray: o.dash }}
                  />
                ))}
                {metric === "flow" &&
                  orders.map((o) => {
                    const f = data.orders[o.id].critical_fraction;
                    if (f == null) return null;
                    const range = o.id === "random" ? random?.range : null;
                    return (
                      <g key={o.id}>
                        <line className="fb-drop" x1={xs(f)} x2={xs(f)} y1={half} y2={inner.height} />
                        {range && (
                          <path
                            className="fb-bracket"
                            d={`M${xs(range[0])} ${half - 5}V${half + 5}M${xs(range[0])} ${half}H${xs(range[1])}M${xs(range[1])} ${half - 5}V${half + 5}`}
                          />
                        )}
                        <circle className="fb-halving" cx={xs(f)} cy={half} r={4.5} />
                        <text className="fb-value" x={xs(f) + (o.id === "random" ? -8 : 8)} y={o.id === "random" ? half + 20 : half - 12} textAnchor={o.id === "random" ? "end" : "start"}>
                          {percent(f)}
                          {o.id === "random" && random?.trials ? `, mean of ${count(random.trials)}` : ""}
                        </text>
                      </g>
                    );
                  })}
                {hover != null && (
                  <g>
                    <line className="fb-crosshair" x1={xs(fractions[hover])} x2={xs(fractions[hover])} y1={0} y2={inner.height} />
                    {orders.map((o) => (
                      <circle
                        key={o.id}
                        className="fb-point"
                        cx={xs(fractions[hover])}
                        cy={ys(share(o.id, hover))}
                        r={4}
                        style={{ fill: o.stroke }}
                      />
                    ))}
                  </g>
                )}
                <LineLabels
                  width={inner.width}
                  height={inner.height}
                  narrow={narrow}
                  items={orders.map((o) => ({
                    id: o.id,
                    label: sentence(o.label),
                    y: ys(share(o.id, fractions.length - 1)),
                    stroke: o.stroke,
                    dash: o.dash,
                  }))}
                />
              </>
            );
          }}
        </ChartFrame>
      </div>
    </Figure>
  );
}
