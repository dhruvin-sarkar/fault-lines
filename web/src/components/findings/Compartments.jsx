import { useState } from "react";
import { ChartFrame, Row, Tooltip, XAxis, YAxis } from "../Chart.jsx";
import { Figure, Keynote, Segmented, Sidenote, TextBlock } from "../ui.jsx";
import { Finding, Pending, useResult } from "./Finding.jsx";
import { LineLabels, inkColor, labelRoom, sentence, spread, xTicks } from "./marks.jsx";
import { count, fixed, indexAt, pValue, percent, strategyLabel } from "../../lib/format.js";
import { useWidth } from "../../lib/hooks.js";
import { line, linear, niceTicks } from "../../lib/scales.js";
import "../../styles/findings-b.css";

const ID = "brain-nerve-cord";
const TITLE = "Brain and nerve cord";
const PARTS = [
  { id: "brain", label: "Brain" },
  { id: "vnc", label: "Nerve cord" },
];
const TIP_HALF = 118;
const SIGNIFICANCE = 0.05;

const color = inkColor;
const dash = (id) => (id === "random" ? "6 5" : undefined);

export default function Compartments({ meta }) {
  const { data, missing } = useResult("compartments.json");
  if (missing) return <Pending id={ID} title={TITLE} />;
  return data?.compartments?.brain && data.compartments.vnc ? <CompartmentsView data={data} meta={meta} /> : null;
}

function CompartmentsView({ data, meta }) {
  const [focus, setFocus] = useState("all");
  const [fraction, setFraction] = useState(null);

  const parts = PARTS.filter((p) => data.compartments[p.id]);
  const strategies = meta.strategies.filter((s) => parts.every((p) => data.compartments[p.id].curves[s.id]));
  const labels = Object.fromEntries(strategies.map((s) => [s.id, strategyLabel(s.id)]));
  const brain = data.compartments.brain;
  const cord = data.compartments.vnc;
  const targeted = strategies.filter((s) => s.id !== "random");
  const fastest = (entry) => targeted.reduce((a, s) => (entry.f_c[s.id] < entry.f_c[a] ? s.id : a), targeted[0].id);
  const brainFastest = fastest(brain);
  const cordFastest = fastest(cord);
  const gap = (id) => Math.abs(brain.f_c[id] - cord.f_c[id]);
  const widest = targeted.reduce((a, s) => (gap(s.id) > gap(a) ? s.id : a), targeted[0].id);
  const welch = data.welch_random_trials;
  const trials = brain.scores.random?.trials;
  const alike = welch && welch.auc_flow.p_value >= SIGNIFICANCE && welch.auc_reachability.p_value >= SIGNIFICANCE;
  const focusId = focus === "all" ? null : focus;
  const options = [
    { value: "all", label: "All" },
    ...strategies.map((s) => ({ value: s.id, label: sentence(strategyLabel(s.id)), color: color(s.id) })),
  ];

  return (
    <Finding
      id={ID}
      title={TITLE}
      stat={percent(brain.f_c[brainFastest])}
      statLabel={`of brain cell types removed by ${labels[brainFastest]} halves flow within the brain`}
    >
      <TextBlock
        notes={
          <>
            <Keynote value={percent(cord.f_c[cordFastest])}>
              of nerve cord types removed by {labels[cordFastest]} halves flow within the nerve cord
            </Keynote>
            <Sidenote title="Two graphs, not one effect">
              The parts differ in size, density and in their sensory and motor sets, and each targeted strategy is a
              single deterministic run, so the numbers describe these two graphs rather than estimate a general
              difference.
            </Sidenote>
          </>
        }
      >
        <p>
          Each cell type is assigned to the brain or the ventral nerve cord by where most of its synapses are, and each
          part is then analyzed as a graph of its own, with the sensory and descending or motor types that fall inside
          it, under the same removal protocol. The brain graph has {count(brain.types)} types and an intact flow
          capacity of {count(brain.intact_flow)}; the nerve cord has {count(cord.types)} types and{" "}
          {count(cord.intact_flow)}.
        </p>
        <p>
          {welch && (
            <>
              {alike ? "Random removal wears both parts down alike" : "Random removal wears the two parts down differently"}
              : the area under the flow curve {alike ? "does not differ" : "differs"} between the{" "}
              {trials != null ? `${count(trials)} ` : ""}brain and nerve cord trials (Welch t = {fixed(welch.auc_flow.t)}
              , p = {pValue(welch.auc_flow.p_value)}; for reachability t = {fixed(welch.auc_reachability.t)}, p ={" "}
              {pValue(welch.auc_reachability.p_value)}).{" "}
            </>
          )}
          Targeted removal does not treat them alike. The brain breaks fastest under {labels[brainFastest]} (
          {percent(brain.f_c[brainFastest])}), the nerve cord under {labels[cordFastest]} (
          {percent(cord.f_c[cordFastest])}). The widest gap is {labels[widest]}: {percent(brain.f_c[widest])} in the
          brain against {percent(cord.f_c[widest])} in the nerve cord.
        </p>
      </TextBlock>

      <Figure
        title="Flow capacity as types are removed, each part on its own"
        controls={<Segmented label="Bring a strategy forward" options={options} value={focus} onChange={setFocus} />}
        caption={
          <>
            Flow is shown as a share of each part&apos;s own intact flow, so both panels share one vertical scale. Hover
            either panel to read both at the same removal level; pick a strategy to bring it forward.
            {trials != null && ` The random line is the first of ${count(trials)} trials.`}
          </>
        }
      >
        <div className="fb-panels">
          {parts.map((p) => (
            <Panel
              key={p.id}
              part={p}
              entry={data.compartments[p.id]}
              strategies={strategies}
              focus={focusId}
              fraction={fraction}
              setFraction={setFraction}
            />
          ))}
        </div>
      </Figure>

      <Figure
        title="Types removed when flow halves, brain against nerve cord"
        caption={
          <>
            Each line joins one strategy&apos;s halving point in the brain, left, to its halving point in the nerve cord,
            right. Lower means the part loses half its routing capacity after fewer removals.
            {trials != null && ` The random value is the mean of ${count(trials)} trials in each part.`}
          </>
        }
      >
        <Slope brain={brain} cord={cord} strategies={strategies} focus={focusId} />
      </Figure>

      <details className="more">
        <summary>Scores as a table</summary>
        <div className="table-wrap">
          <table className="data">
            <thead>
              <tr>
                <th>Strategy</th>
                <th className="num">Brain, flow halves</th>
                <th className="num">Nerve cord, flow halves</th>
                <th className="num">Brain, flow AUC</th>
                <th className="num">Nerve cord, flow AUC</th>
              </tr>
            </thead>
            <tbody>
              {strategies.map((s) => (
                <tr key={s.id}>
                  <td>{strategyLabel(s.id)}</td>
                  <td className="num">{percent(brain.f_c[s.id])}</td>
                  <td className="num">{percent(cord.f_c[s.id])}</td>
                  <td className="num">{fixed(brain.scores[s.id]?.auc_flow, 3)}</td>
                  <td className="num">{fixed(cord.scores[s.id]?.auc_flow, 3)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </details>
    </Finding>
  );
}

function Panel({ part, entry, strategies, focus, fraction, setFraction }) {
  const [sizer, width] = useWidth();
  const narrow = width < 520;
  const margin = { top: 32, right: labelRoom(strategies.map((s) => strategyLabel(s.id)), narrow), bottom: 46, left: 54 };
  const xMax = Math.max(0.5, ...strategies.map((s) => entry.curves[s.id].fraction_removed.at(-1)));
  const at = (id, f) => {
    const curve = entry.curves[id];
    const i = indexAt(curve.fraction_removed, f);
    return { f: curve.fraction_removed[i], v: curve.flow[i] / entry.intact_flow };
  };
  const dim = (id) => (focus && focus !== id ? 0.18 : 1);

  return (
    <div ref={sizer} className="fb-panel">
      <div className="fb-panel-head">
        <strong>{part.label}</strong>
        <span>
          {count(entry.types)} types, intact flow {count(entry.intact_flow)}
        </span>
      </div>
      <ChartFrame
        height={narrow ? 300 : 320}
        margin={margin}
        label={`${part.label}: flow capacity as a share of intact against the fraction of types removed, ${strategies.length} strategies`}
        onPointer={(x, _y, inner) => setFraction(Math.max(0, Math.min(xMax, (x / inner.width) * xMax)))}
        onLeave={() => setFraction(null)}
        overlay={({ width: full, height, margin: m }) => {
          if (fraction == null) return null;
          const w = full - m.left - m.right;
          const f = at(strategies[0].id, fraction).f;
          const x = m.left + (f / xMax) * w;
          const flip = x > m.left + w / 2;
          const left = Math.max(TIP_HALF, Math.min(full - TIP_HALF, x + (flip ? -TIP_HALF - 10 : TIP_HALF + 10)));
          const rows = strategies.map((s) => ({ ...s, v: at(s.id, fraction).v })).sort((a, b) => a.v - b.v);
          return (
            <Tooltip x={left} y={m.top + height * 0.62} width={full}>
              <strong className="fb-tip-head">
                {part.label}, {percent(f)} removed
              </strong>
              {rows.map((r) => (
                <Row key={r.id} label={sentence(strategyLabel(r.id))} value={percent(r.v, 0)} color={color(r.id)} />
              ))}
            </Tooltip>
          );
        }}
      >
        {(inner) => {
          const xs = linear([0, xMax], [0, inner.width]);
          const ys = linear([0, 1], [inner.height, 0]);
          return (
            <>
              <YAxis
                scale={ys}
                ticks={[0, 0.25, 0.5, 0.75, 1]}
                width={inner.width}
                format={(v) => percent(v, 0)}
                title="Flow, share of intact"
              />
              <XAxis
                scale={xs}
                ticks={xTicks(xMax, narrow)}
                height={inner.height}
                width={inner.width}
                format={(v) => percent(v, 0)}
                title="Types removed"
              />
              <line className="fb-ref" x1={0} x2={inner.width} y1={ys(0.5)} y2={ys(0.5)} />
              {strategies.map((s) => {
                const curve = entry.curves[s.id];
                return (
                  <path
                    key={s.id}
                    className="fb-series"
                    d={line(curve.flow.map((v, i) => [xs(curve.fraction_removed[i]), ys(v / entry.intact_flow)]))}
                    style={{
                      stroke: color(s.id),
                      strokeWidth: focus === s.id ? 2.75 : 2,
                      strokeDasharray: dash(s.id),
                      opacity: dim(s.id),
                    }}
                  />
                );
              })}
              {fraction != null && (
                <g>
                  <line
                    className="fb-crosshair"
                    x1={xs(at(strategies[0].id, fraction).f)}
                    x2={xs(at(strategies[0].id, fraction).f)}
                    y1={0}
                    y2={inner.height}
                  />
                  {strategies.map((s) => {
                    const p = at(s.id, fraction);
                    return (
                      <circle
                        key={s.id}
                        className="fb-point"
                        cx={xs(p.f)}
                        cy={ys(p.v)}
                        r={4}
                        style={{ fill: color(s.id), opacity: dim(s.id) }}
                      />
                    );
                  })}
                </g>
              )}
              <LineLabels
                width={inner.width}
                height={inner.height}
                narrow={narrow}
                dim={dim}
                items={strategies.map((s) => {
                  const curve = entry.curves[s.id];
                  return {
                    id: s.id,
                    label: sentence(strategyLabel(s.id)),
                    y: ys(curve.flow.at(-1) / entry.intact_flow),
                    stroke: color(s.id),
                    dash: dash(s.id),
                  };
                })}
              />
            </>
          );
        }}
      </ChartFrame>
    </div>
  );
}

function Slope({ brain, cord, strategies, focus }) {
  const [sizer, width] = useWidth();
  const [hovered, setHovered] = useState(null);
  const narrow = width < 560;
  const active = hovered ?? focus;
  const values = strategies.flatMap((s) => [brain.f_c[s.id], cord.f_c[s.id]]);
  const ticks = niceTicks([0, Math.max(...values)], 4);
  const top = ticks.at(-1) >= Math.max(...values) ? ticks.at(-1) : ticks.at(-1) + (ticks[1] - ticks[0]);
  const right = narrow ? 56 : labelRoom(strategies.map((s) => `00.0%  ${strategyLabel(s.id)}`), false);
  const margin = { top: 40, right, bottom: 16, left: narrow ? 56 : 90 };
  const dim = (id) => (active && active !== id ? 0.2 : 1);

  return (
    <div ref={sizer} className="fb-slope">
      <ChartFrame
        height={360}
        margin={margin}
        label={`Slope chart of the fraction of types removed when flow halves, brain on the left and nerve cord on the right, for ${strategies.length} strategies`}
        onPointer={(x, y, inner) => {
          const t = Math.max(0, Math.min(1, x / inner.width));
          const ys = linear([0, top], [inner.height, 0]);
          let best = null;
          let distance = 18;
          for (const s of strategies) {
            const d = Math.abs(ys(brain.f_c[s.id] + t * (cord.f_c[s.id] - brain.f_c[s.id])) - y);
            if (d < distance) {
              distance = d;
              best = s.id;
            }
          }
          setHovered(best);
        }}
        onLeave={() => setHovered(null)}
      >
        {(inner) => {
          const ys = linear([0, top], [inner.height, 0]);
          const left = spread(
            strategies.map((s) => ({ id: s.id, y: ys(brain.f_c[s.id]), v: brain.f_c[s.id] })),
            17,
            0,
            inner.height,
          );
          const rightLabels = spread(
            strategies.map((s) => ({ id: s.id, label: strategyLabel(s.id), y: ys(cord.f_c[s.id]), v: cord.f_c[s.id] })),
            17,
            0,
            inner.height,
          );
          return (
            <>
              <text className="fb-column" x={0} y={-22} textAnchor="middle">
                Brain
              </text>
              <text className="fb-column" x={inner.width} y={-22} textAnchor="middle">
                Nerve cord
              </text>
              <line className="fb-post" x1={0} x2={0} y1={-8} y2={inner.height} />
              <line className="fb-post" x1={inner.width} x2={inner.width} y1={-8} y2={inner.height} />
              {strategies.map((s) => (
                <g key={s.id} className="fb-fade" style={{ opacity: dim(s.id) }}>
                  <line
                    x1={0}
                    x2={inner.width}
                    y1={ys(brain.f_c[s.id])}
                    y2={ys(cord.f_c[s.id])}
                    style={{ stroke: color(s.id), strokeWidth: active === s.id ? 3 : 2, strokeDasharray: dash(s.id) }}
                  />
                  <circle className="fb-point" cx={0} cy={ys(brain.f_c[s.id])} r={5} style={{ fill: color(s.id) }} />
                  <circle className="fb-point" cx={inner.width} cy={ys(cord.f_c[s.id])} r={5} style={{ fill: color(s.id) }} />
                </g>
              ))}
              {left.map((l) => (
                <text key={l.id} className="fb-value" x={-12} y={l.y} dy="0.32em" textAnchor="end" style={{ opacity: dim(l.id) }}>
                  {percent(l.v)}
                </text>
              ))}
              {rightLabels.map((l) => (
                <text key={l.id} className="fb-value" x={inner.width + 12} y={l.y} dy="0.32em" style={{ opacity: dim(l.id) }}>
                  {percent(l.v)}
                  {!narrow && (
                    <tspan className="fb-note" dx={8}>
                      {sentence(l.label)}
                    </tspan>
                  )}
                </text>
              ))}
            </>
          );
        }}
      </ChartFrame>
      {narrow && (
        <ul className="legend fb-key" aria-label="Strategies">
          {strategies.map((s) => (
            <li key={s.id}>
              <svg width="18" height="4" aria-hidden="true">
                <line x1="0" x2="18" y1="2" y2="2" style={{ stroke: color(s.id), strokeWidth: 2, strokeDasharray: dash(s.id) }} />
              </svg>
              {sentence(strategyLabel(s.id))}
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
