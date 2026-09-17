import { useMemo, useRef, useState } from "react";
import { ChartFrame, XAxis, YAxis } from "./Chart.jsx";
import { Figure, HeadingLevel, Sidenote, TextBlock } from "./ui.jsx";
import { useWidth } from "../lib/hooks.js";
import { count, fixed, numberWord, percent, sentence, strategyLabel } from "../lib/format.js";
import { line, linear } from "../lib/scales.js";
import "../styles/measure.css";

const STRATEGY_ORDER = ["sm_betweenness", "betweenness", "pagerank", "out_strength", "in_strength", "random"];

const STRATEGY_TEXT = {
  sm_betweenness: () =>
    "Takes first the types that lie on the most shortest paths from a sensory type to a motor type, the routes this study measures.",
  betweenness: () => "Takes first the types that lie on the most shortest paths between any two types in the graph.",
  pagerank: () =>
    "Takes first the types where a random walk along connections, weighted by synapse count, spends the most time.",
  out_strength: () => "Takes first the types that send the most synapses along their connections.",
  in_strength: () => "Takes first the types that receive the most synapses along their connections.",
  random: (trials) => `Removes types in an order that ignores the wiring, repeated over ${trials} seeded orders as the baseline.`,
};

// `at` places a node along its layer (0 to 1), `nudge` shifts it across layers. Random picks index this order.
const NODES = [
  { id: "s1", kind: "sensory", layer: 0, at: 0.1, nudge: 0 },
  { id: "s2", kind: "sensory", layer: 0, at: 0.3, nudge: 0.02 },
  { id: "s3", kind: "sensory", layer: 0, at: 0.5, nudge: -0.01 },
  { id: "s4", kind: "sensory", layer: 0, at: 0.7, nudge: 0.02 },
  { id: "s5", kind: "sensory", layer: 0, at: 0.9, nudge: 0 },
  { id: "p1", kind: "inter", layer: 1, at: 0.05, nudge: -0.06 },
  { id: "p2", kind: "inter", layer: 1, at: 0.27, nudge: 0.05 },
  { id: "a", kind: "inter", layer: 1, at: 0.52, nudge: -0.02 },
  { id: "p3", kind: "inter", layer: 1, at: 0.75, nudge: 0.06 },
  { id: "p4", kind: "inter", layer: 1, at: 0.95, nudge: -0.03 },
  { id: "q1", kind: "inter", layer: 2, at: 0.06, nudge: 0.04 },
  { id: "q2", kind: "inter", layer: 2, at: 0.28, nudge: -0.05 },
  { id: "b", kind: "inter", layer: 2, at: 0.49, nudge: 0.03 },
  { id: "q3", kind: "inter", layer: 2, at: 0.73, nudge: -0.04 },
  { id: "q4", kind: "inter", layer: 2, at: 0.94, nudge: 0.05 },
  { id: "m1", kind: "motor", layer: 3, at: 0.1, nudge: 0 },
  { id: "m2", kind: "motor", layer: 3, at: 0.3, nudge: -0.02 },
  { id: "m3", kind: "motor", layer: 3, at: 0.5, nudge: 0.01 },
  { id: "m4", kind: "motor", layer: 3, at: 0.7, nudge: -0.02 },
  { id: "m5", kind: "motor", layer: 3, at: 0.9, nudge: 0 },
];

const EDGES = [
  "s1 a", "s2 a", "s3 a", "s4 a", "s5 a",
  "s1 p1", "s2 p1", "s3 p1", "s1 p2", "s2 p2", "s3 p2", "s3 p3", "s4 p3", "s5 p3", "s4 p4", "s5 p4",
  "a q1", "a q2", "a b", "a q3", "p1 b", "p2 b", "p3 b", "p1 q1", "p2 q2", "p3 q3", "p4 q4",
  "b m1", "b m2", "b m3", "b m4", "b m5",
  "q1 m1", "q1 m2", "q1 m3", "q2 m1", "q2 m2", "q2 m3", "q3 m3", "q3 m4", "q3 m5", "q4 m4", "q4 m5",
].map((pair) => pair.split(" "));

const RANDOM_SEED = 543;
const KIND_NAME = { sensory: "sensory type", inter: "intermediate type", motor: "motor type" };
const withArticle = (kind) => `${kind === "inter" ? "an" : "a"} ${KIND_NAME[kind]}`;
const INDEX = new Map(NODES.map((node, i) => [node.id, i]));
const DEGREE = NODES.map((node) => EDGES.filter(([a, b]) => a === node.id || b === node.id).length);
const RADIUS = DEGREE.map((d) => 4.5 + 0.95 * d);
const ORDINAL = NODES.map((node, i) => NODES.slice(0, i + 1).filter((n) => n.kind === node.kind).length);
const SENSORY_COUNT = NODES.filter((n) => n.kind === "sensory").length;
const MOTOR_COUNT = NODES.filter((n) => n.kind === "motor").length;

/**
 * Unit-capacity maximum flow from a super-source over the present sensory nodes to a super-sink over the present
 * motor nodes (Edmonds-Karp), with the source-side minimum cut and each node's share of the routes.
 */
function analyze(removed) {
  const n = NODES.length;
  const source = n;
  const sink = n + 1;
  const adjacency = Array.from({ length: n + 2 }, () => []);
  const head = [];
  const capacity = [];
  const addArc = (from, to, cap) => {
    adjacency[from].push(head.length);
    head.push(to);
    capacity.push(cap);
    adjacency[to].push(head.length);
    head.push(from);
    capacity.push(0);
  };
  const arcs = EDGES.map(([a, b]) => {
    if (removed.has(a) || removed.has(b)) return -1;
    const arc = head.length;
    addArc(INDEX.get(a), INDEX.get(b), 1);
    return arc;
  });
  NODES.forEach((node, i) => {
    if (removed.has(node.id)) return;
    if (node.kind === "sensory") addArc(source, i, EDGES.length + 1);
    if (node.kind === "motor") addArc(i, sink, EDGES.length + 1);
  });

  let flow = 0;
  let via;
  for (;;) {
    via = new Array(n + 2).fill(-1);
    via[source] = -2;
    const queue = [source];
    for (let q = 0; q < queue.length && via[sink] === -1; q += 1) {
      for (const arc of adjacency[queue[q]]) {
        if (capacity[arc] > 0 && via[head[arc]] === -1) {
          via[head[arc]] = arc;
          queue.push(head[arc]);
        }
      }
    }
    if (via[sink] === -1) break;
    // Arcs are stored in forward and reverse pairs, so arc ^ 1 is the partner.
    for (let v = sink; v !== source; v = head[via[v] ^ 1]) {
      capacity[via[v]] -= 1;
      capacity[via[v] ^ 1] += 1;
    }
    flow += 1;
  }

  // After the last search, `via` marks the nodes still reachable from the source in the residual graph.
  const used = new Set();
  const cut = new Set();
  const load = new Array(n).fill(0);
  arcs.forEach((arc, i) => {
    if (arc < 0) return;
    const from = INDEX.get(EDGES[i][0]);
    const to = INDEX.get(EDGES[i][1]);
    if (capacity[arc] === 0) {
      used.add(i);
      load[to] += 1;
      if (NODES[from].kind === "sensory") load[from] += 1;
    }
    if (via[from] !== -1 && via[to] === -1) cut.add(i);
  });

  const out = NODES.map(() => []);
  EDGES.forEach(([a, b]) => {
    if (!removed.has(a) && !removed.has(b)) out[INDEX.get(a)].push(INDEX.get(b));
  });
  let pairs = 0;
  NODES.forEach((node, i) => {
    if (node.kind !== "sensory" || removed.has(node.id)) return;
    const seen = new Set([i]);
    const stack = [i];
    while (stack.length) {
      for (const next of out[stack.pop()]) {
        if (!seen.has(next)) {
          seen.add(next);
          stack.push(next);
        }
      }
    }
    seen.forEach((j) => NODES[j].kind === "motor" && (pairs += 1));
  });

  return { flow, used, cut, load, pairs };
}

/** Deterministic uniform numbers in [0, 1) from a 32-bit seed (mulberry32). */
function seeded(seed) {
  let state = seed >>> 0;
  return () => {
    state = (state + 0x6d2b79f5) >>> 0;
    let t = state;
    t = Math.imul(t ^ (t >>> 15), t | 1);
    t ^= t + Math.imul(t ^ (t >>> 7), t | 61);
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

function busiest(removed, state) {
  let best = -1;
  NODES.forEach((node, i) => {
    if (!removed.has(node.id) && state.load[i] > 0 && (best < 0 || state.load[i] > state.load[best])) best = i;
  });
  return best;
}

const INTACT = analyze(new Set());
const HUBS_REMOVED = (() => {
  const removed = new Set();
  for (let k = 0; k < 2; k += 1) removed.add(NODES[busiest(removed, analyze(removed))].id);
  return analyze(removed);
})();

const routes = (k) => `${k} ${k === 1 ? "route" : "routes"}`;

export default function Measure({ meta, percolation }) {
  const { graph, protocol, sets } = meta;
  const byId = new Map(meta.strategies.map((s) => [s.id, s]));
  const strategies = STRATEGY_ORDER.filter((id) => byId.has(id)).map((id) => byId.get(id));
  const range = protocol.auc_range;

  return (
    <section className="section" id="measure" aria-labelledby="measure-title">
      <div className="wrap">
        <div className="section-head">
          <h2 id="measure-title">How fragility is measured</h2>
          <TextBlock
            notes={
              <>
                <Sidenote title="Sensory set">
                  {count(graph.sensory_types)} types of primary sensory neuron in {sets?.sensory_superclasses ?? "several"}{" "}
                  superclasses, from photoreceptors and olfactory receptor neurons to the mechanosensors of the legs.
                </Sidenote>
                <Sidenote title="Motor set">
                  {count(graph.motor_types)} descending and motor neuron types, from {sets?.motor_superclasses ?? "several"}{" "}
                  superclasses. Descending neurons carry commands from the brain to the nerve cord; motor neurons drive
                  the muscles.
                </Sidenote>
                <Sidenote title="Flow capacity">
                  The maximum flow from a super-source over the sensory set to a super-sink over the motor set, with one
                  unit of capacity per connection. It counts routes that share no connection and, by Menger&apos;s
                  theorem, equals the fewest connections whose loss separates the two sets.
                </Sidenote>
                <Sidenote title="Reachable pairs">
                  Sensory and motor types joined by at least one directed path, out of{" "}
                  {count(graph.sensory_motor_pairs)} possible pairs.
                </Sidenote>
              </>
            }
          >
            <p>
              The wiring diagram is reduced to a graph of {count(graph.cell_types)} cell types joined by{" "}
              {count(graph.edges)} directed connections. A connection from type A to type B is kept when A supplies at
              least {percent(graph.edge_min_input_fraction ?? 0.01, 0)} of the synapses B receives, and it is weighted
              by their synapse count.
            </p>
            <p>
              Fragility is asked of one passage through that graph: from the {count(graph.sensory_types)} sensory types,
              where signals enter, to the {count(graph.motor_types)} descending and motor types, where commands leave.
              Two numbers follow it while types are taken away. <strong>Flow capacity</strong> counts how many routes
              can run at once without sharing a connection; the intact graph has {count(graph.intact_flow)}.{" "}
              <strong>Reachability</strong> asks only whether a sensory type can still reach a motor type at all, and{" "}
              {count(graph.intact_reachable_pairs)} of the {count(graph.sensory_motor_pairs)} pairs can.
            </p>
            <p>
              The two measure different things. A network can keep almost every pair connected while most of its
              parallel routes are gone, because a single thin path is enough to connect a pair. The small network below
              computes both, live, as you remove its nodes.
            </p>
          </TextBlock>
        </div>

        <Toy />

        <div className="ms-part">
          <h3 className="ms-subhead">{sentence(numberWord(strategies.length))} ways to choose what goes</h3>
          <TextBlock>
            <p>
              Every attack is adaptive. Each batch removes {percent(protocol.batch_fraction_of_remaining, 0)} of the
              types still present, those with the highest score, and then scores the damaged graph again before the next
              batch, so an attack on hubs keeps finding the new hubs as the old ones go. Removal continues until{" "}
              {percent(range[1], 0)} of types are gone.
            </p>
          </TextBlock>
          <ul className="ms-strategies">
            {strategies.map((s) => (
              <li key={s.id}>
                <span className="ms-strategy-name">
                  <span className="swatch" style={{ background: `var(--s-${s.id}-ink)` }} aria-hidden="true" />
                  {strategyLabel(s.id, { capital: true })}
                </span>
                <p>{STRATEGY_TEXT[s.id]?.(protocol.random_trials)}</p>
              </li>
            ))}
          </ul>
        </div>

        <div className="ms-part">
          <h3 className="ms-subhead">Two numbers for a whole attack</h3>
          <TextBlock
            notes={
              <>
                <Sidenote
                  title={
                    <>
                      Halving point, <i>f</i>
                      <sub>c</sub>
                    </>
                  }
                >
                  The share of types removed when flow capacity first falls below half its intact value, interpolated
                  between the last step above half and the first step below.
                </Sidenote>
                <Sidenote title="Area under the curve">
                  The area under the remaining-flow curve from {percent(range[0], 0)} to {percent(range[1], 0)} removed,
                  divided by that range. It is the average share of routes kept over the attack.
                </Sidenote>
              </>
            }
          >
            <p>
              An attack traces a curve: flow capacity, as a share of its intact value, against the share of types
              removed. Two numbers condense it. The halving point <i>f</i>
              <sub>c</sub> says when the network has lost half its routes. The area under the curve, or AUC, says how
              much was lost along the whole way, so a network that lost nothing would score 1. For both, lower means more
              fragile.
            </p>
          </TextBlock>
          <HeadingLevel level={4}>
            <Summary meta={meta} percolation={percolation} />
          </HeadingLevel>
        </div>
      </div>
    </section>
  );
}

function Toy() {
  const [removed, setRemoved] = useState(() => new Set());
  const [draws, setDraws] = useState(0);
  const [focus, setFocus] = useState(null);
  const [message, setMessage] = useState("");
  const [announcement, setAnnouncement] = useState("");
  const [active, setActive] = useState(0);
  const nodeRefs = useRef([]);
  const [box, width] = useWidth(720);
  const state = useMemo(() => analyze(removed), [removed]);

  const vertical = width < 560;
  const size = vertical ? { w: width, h: 400 } : { w: width, h: Math.round(Math.max(360, Math.min(460, width * 0.56))) };
  const pad = vertical ? { l: 22, r: 22, t: 34, b: 34 } : { l: 26, r: 26, t: 40, b: 20 };
  const points = NODES.map((node) => {
    const across = (node.layer + node.nudge) / 3;
    const along = node.at;
    return vertical
      ? { x: pad.l + along * (size.w - pad.l - pad.r), y: pad.t + across * (size.h - pad.t - pad.b) }
      : { x: pad.l + across * (size.w - pad.l - pad.r), y: pad.t + along * (size.h - pad.t - pad.b) };
  });

  function apply(next, text, carried = 0) {
    setRemoved(next);
    const after = analyze(next);
    let change = `Flow ${after.flow < state.flow ? "falls" : "rises"} from ${state.flow} to ${after.flow}.`;
    if (after.flow === state.flow) {
      change = carried > 0 ? `${carried === 1 ? "Its route found another path" : "Its routes found other paths"}, so flow stays at ${after.flow}.` : `Flow stays at ${after.flow}.`;
    }
    setMessage(`${text} ${change}`);
    setAnnouncement(`Flow ${after.flow} of ${INTACT.flow} routes, ${after.pairs} of ${INTACT.pairs} pairs reachable.`);
  }

  // Arrow keys move to the nearest node in that direction, favoring nodes straight ahead.
  function neighbor(from, key) {
    const [ux, uy] = { ArrowRight: [1, 0], ArrowLeft: [-1, 0], ArrowDown: [0, 1], ArrowUp: [0, -1] }[key];
    const pick = (cone) => {
      let best = -1;
      let score = Infinity;
      points.forEach((p, i) => {
        const dx = p.x - points[from].x;
        const dy = p.y - points[from].y;
        const ahead = dx * ux + dy * uy;
        const aside = Math.abs(dx * uy - dy * ux);
        if (i === from || ahead <= 4 || (cone && aside > ahead)) return;
        if (ahead + 2 * aside < score) {
          score = ahead + 2 * aside;
          best = i;
        }
      });
      return best;
    };
    const inCone = pick(true);
    return inCone >= 0 ? inCone : pick(false);
  }

  function onNodeKey(event, i) {
    let target = -1;
    if (event.key === "Enter" || event.key === " ") {
      event.preventDefault();
      toggle(i);
      return;
    }
    if (event.key.startsWith("Arrow")) target = neighbor(i, event.key);
    else if (event.key === "Home") target = 0;
    else if (event.key === "End") target = NODES.length - 1;
    else return;
    event.preventDefault();
    if (target >= 0) {
      setActive(target);
      nodeRefs.current[target]?.focus();
    }
  }

  function toggle(i) {
    const node = NODES[i];
    const next = new Set(removed);
    if (next.has(node.id)) {
      next.delete(node.id);
      apply(next, `Restored ${withArticle(node.kind)}.`);
    } else {
      next.add(node.id);
      apply(next, `Removed ${withArticle(node.kind)} that carried ${routes(state.load[i])}.`, state.load[i]);
    }
  }

  function removeBusiest() {
    const i = busiest(removed, state);
    if (i < 0) return;
    apply(new Set(removed).add(NODES[i].id), `Removed the busiest type, ${withArticle(NODES[i].kind)} carrying ${routes(state.load[i])}.`, state.load[i]);
  }

  function removeRandom() {
    const present = NODES.map((node, i) => i).filter((i) => !removed.has(NODES[i].id));
    if (!present.length) return;
    const next = seeded(RANDOM_SEED);
    for (let k = 0; k < draws; k += 1) next();
    const i = present[Math.floor(next() * present.length)];
    setDraws(draws + 1);
    apply(new Set(removed).add(NODES[i].id), `Removed ${withArticle(NODES[i].kind)} at random; it carried ${routes(state.load[i])}.`, state.load[i]);
  }

  function reset() {
    setRemoved(new Set());
    setDraws(0);
    setMessage(`Restored every type. Flow is back to ${INTACT.flow}.`);
    setAnnouncement(`Flow ${INTACT.flow} of ${INTACT.flow} routes, ${INTACT.pairs} of ${INTACT.pairs} pairs reachable.`);
  }

  const broken = state.flow < INTACT.flow;
  const belowHalf = state.flow < INTACT.flow / 2;
  const focusNode = focus != null ? NODES[focus] : null;
  let note = message || "Select any type to remove it, or use the buttons, and watch the routes find their way around.";
  if (focusNode) {
    note = removed.has(focusNode.id)
      ? `This ${KIND_NAME[focusNode.kind]} is removed. Select it to restore it.`
      : `${sentence(withArticle(focusNode.kind))} with ${DEGREE[focus]} connections, carrying ${routes(state.load[focus])} of ${state.flow}. Select it to remove it.`;
  }

  const controls = (
    <div className="ms-actions">
      <button type="button" className="btn" onClick={removeBusiest} disabled={state.flow === 0}>
        Remove the busiest
      </button>
      <button type="button" className="btn" onClick={removeRandom} disabled={removed.size === NODES.length}>
        Remove one at random
      </button>
    </div>
  );

  const caption = (
    <>
      A network of {NODES.length} cell types in four layers, with signals running from the sensory types to the descending and motor types.
      Bright lines trace one set of routes that achieves the maximum flow; no two of them share a connection. Select a
      type to remove it and again to restore it. Once flow drops, red bars mark a minimum cut: as many connections as
      there are routes left, whose loss would separate the two sets. Removing the busiest type twice takes flow from{" "}
      {INTACT.flow} to {HUBS_REMOVED.flow}. Random picks follow a fixed seed, so they repeat after Reset; most land on
      types that carry one or two routes or have spare connections.
    </>
  );

  return (
    <Figure id="measure-toy" title="Routes through a small network" variant="field" controls={controls} caption={caption}>
      <div className="ms-toy">
        <div className="ms-toy-graph" ref={box}>
          <svg
            className="ms-svg"
            width={size.w}
            height={size.h}
            viewBox={`0 0 ${size.w} ${size.h}`}
            role="group"
            aria-label={`A network of ${NODES.length} cell types: ${SENSORY_COUNT} sensory, ${
              NODES.length - SENSORY_COUNT - MOTOR_COUNT
            } intermediate and ${MOTOR_COUNT} motor. Each type is a button that removes or restores it; arrow keys move between types.`}
          >
            <LayerLabels points={points} vertical={vertical} size={size} />
            <g aria-hidden="true">
              {EDGES.map(([a, b], i) => {
                const gone = removed.has(a) || removed.has(b);
                if (state.used.has(i)) return null;
                return <Edge key={i} from={points[INDEX.get(a)]} to={points[INDEX.get(b)]} className={gone ? "is-gone" : ""} />;
              })}
            </g>
            <g className="ms-routes" aria-hidden="true">
              {EDGES.map(([a, b], i) =>
                state.used.has(i) ? <Edge key={i} from={points[INDEX.get(a)]} to={points[INDEX.get(b)]} className="is-route" /> : null,
              )}
            </g>
            {broken && (
              <g className="ms-cut" aria-hidden="true">
                {cutMarks(state.cut, points).map((m) => (
                  <line key={m.i} x1={m.x1} y1={m.y1} x2={m.x2} y2={m.y2} />
                ))}
              </g>
            )}
            <g>
              {NODES.map((node, i) => {
                const gone = removed.has(node.id);
                const idle = !gone && state.load[i] === 0;
                const { x, y } = points[i];
                const r = RADIUS[i];
                return (
                  <g
                    key={node.id}
                    className={`ms-node ${gone ? "is-removed" : ""} ${idle ? "is-idle" : ""}`}
                    role="button"
                    ref={(el) => (nodeRefs.current[i] = el)}
                    tabIndex={i === active ? 0 : -1}
                    aria-pressed={gone}
                    aria-label={`${sentence(KIND_NAME[node.kind])} ${ORDINAL[i]}, ${
                      gone ? "removed" : `carrying ${routes(state.load[i])}`
                    }`}
                    onClick={() => toggle(i)}
                    onKeyDown={(event) => onNodeKey(event, i)}
                    onPointerEnter={(event) => event.pointerType === "mouse" && setFocus(i)}
                    onPointerLeave={() => setFocus((f) => (f === i ? null : f))}
                    onFocus={() => {
                      setFocus(i);
                      setActive(i);
                    }}
                    onBlur={() => setFocus((f) => (f === i ? null : f))}
                  >
                    <circle className="ms-hit" cx={x} cy={y} r={22} />
                    <circle className="ms-ring" cx={x} cy={y} r={r + 5} />
                    <circle className="ms-dot" cx={x} cy={y} r={r} />
                    {gone && <path className="ms-cross" d={`M${x - r * 0.45} ${y - r * 0.45}L${x + r * 0.45} ${y + r * 0.45}M${x + r * 0.45} ${y - r * 0.45}L${x - r * 0.45} ${y + r * 0.45}`} />}
                  </g>
                );
              })}
            </g>
          </svg>
          <ul className="ms-legend" aria-label="Key">
            <li>
              <svg viewBox="0 0 24 12" aria-hidden="true">
                <line x1="1" y1="6" x2="23" y2="6" className="ms-key-route" />
              </svg>
              Route in use
            </li>
            <li>
              <svg viewBox="0 0 24 12" aria-hidden="true">
                <line x1="1" y1="6" x2="23" y2="6" className="ms-key-edge" />
              </svg>
              Unused connection
            </li>
            <li>
              <svg viewBox="0 0 24 12" aria-hidden="true">
                <line x1="1" y1="6" x2="23" y2="6" className="ms-key-edge" />
                <line x1="12" y1="0.5" x2="12" y2="11.5" className="ms-key-cut" />
              </svg>
              Minimum cut
            </li>
            <li>
              <svg viewBox="0 0 12 12" aria-hidden="true">
                <circle cx="6" cy="6" r="4.2" className="ms-key-idle" />
              </svg>
              Type carrying no route
            </li>
            <li>
              <svg viewBox="0 0 12 12" aria-hidden="true">
                <circle cx="6" cy="6" r="4.2" className="ms-key-removed" />
              </svg>
              Removed
            </li>
          </ul>
        </div>

        <div className="ms-readout">
          <div className="ms-stat is-main">
            <div className="label">Maximum flow</div>
            <div className="ms-value">
              <span className={`display ${belowHalf ? "is-low" : ""}`}>{state.flow}</span>
              <span className="ms-of">of {INTACT.flow} intact</span>
            </div>
            <div className="ms-meter" aria-hidden="true">
              <span className={belowHalf ? "is-low" : ""} style={{ transform: `scaleX(${state.flow / INTACT.flow})` }} />
              <i />
            </div>
            <div className="ms-stat-note">
              routes that share no connection{belowHalf ? ", now below half" : ""}
            </div>
          </div>
          <div className="ms-stat">
            <div className="label">Reachable pairs</div>
            <div className="ms-value">
              <span className="number">{state.pairs}</span>
              <span className="ms-of">of {INTACT.pairs} intact</span>
            </div>
            <div className="ms-stat-note">sensory and motor types joined by a path</div>
          </div>
          <div className="ms-removed">
            <span className="label">
              {removed.size} of {NODES.length} types removed
            </span>
            <button type="button" className="btn ms-reset" onClick={reset} disabled={removed.size === 0 && draws === 0}>
              Reset
            </button>
          </div>
          <p className="ms-note">{note}</p>
          <p className="visually-hidden" aria-live="polite">
            {announcement}
          </p>
        </div>
      </div>
    </Figure>
  );
}

/** A short bar across each cut edge, slid along the edge when two bars would sit on top of each other. */
function cutMarks(cut, points) {
  const placed = [];
  cut.forEach((i) => {
    const p = points[INDEX.get(EDGES[i][0])];
    const q = points[INDEX.get(EDGES[i][1])];
    const len = Math.hypot(q.x - p.x, q.y - p.y) || 1;
    const nx = (-(q.y - p.y) / len) * 7;
    const ny = ((q.x - p.x) / len) * 7;
    const spots = [0.5, 0.36, 0.64, 0.28, 0.72].map((t) => ({ x: p.x + t * (q.x - p.x), y: p.y + t * (q.y - p.y) }));
    const spot = spots.find((c) => placed.every((m) => Math.hypot(m.x - c.x, m.y - c.y) > 18)) ?? spots[0];
    placed.push({ i, x: spot.x, y: spot.y, x1: spot.x - nx, y1: spot.y - ny, x2: spot.x + nx, y2: spot.y + ny });
  });
  return placed;
}

function LayerLabels({ points, vertical, size }) {
  const first = points[0];
  const last = points[NODES.length - 1];
  if (vertical) {
    return (
      <g className="ms-layer-labels" aria-hidden="true">
        <text x={10} y={14}>
          Sensory types
        </text>
        <text x={10} y={size.h - 6}>
          Descending and motor types
        </text>
      </g>
    );
  }
  const middle = (points[INDEX.get("a")].x + points[INDEX.get("b")].x) / 2;
  return (
    <g className="ms-layer-labels" aria-hidden="true">
      <text x={first.x - 10} y={16}>
        Sensory types
      </text>
      <text x={middle} y={16} textAnchor="middle">
        Intermediate types
      </text>
      <text x={last.x + 10} y={16} textAnchor="end">
        Descending and motor types
      </text>
    </g>
  );
}

function Edge({ from, to, className }) {
  return <line className={`ms-edge ${className}`} x1={from.x} y1={from.y} x2={to.x} y2={to.y} />;
}

const WIDE_MARGIN = { top: 34, right: 190, bottom: 46, left: 54 };
const NARROW_MARGIN = { top: 34, right: 14, bottom: 46, left: 44 };

/** The real remaining-flow curves for one targeted attack and for random removal, annotated with f_c and AUC. */
function Summary({ meta, percolation }) {
  const [box, width] = useWidth(720);
  const narrow = width < 620;
  const intact = percolation.intact_flow;
  const range = meta.protocol.auc_range;
  const label = (id) => strategyLabel(id, { capital: true });

  const series = ["random", "out_strength"]
    .filter((id) => percolation.strategies[id])
    .map((id) => {
      const s = percolation.strategies[id];
      const source = id === "random" && s.band ? { x: s.band.fraction_removed, y: s.band.flow_mean } : { x: s.fraction_removed, y: s.flow };
      const pts = source.x.map((f, i) => [f, source.y[i] / intact]).filter(([f]) => f <= range[1] + 0.01);
      return { id, name: label(id), pts, fc: s.critical_fraction, auc: s.auc_flow, trials: s.trials };
    });
  const random = series.find((s) => s.id === "random");
  const target = series.find((s) => s.id !== "random");
  if (!random || !target) return null;
  const xMax = Math.max(...series.map((s) => s.pts[s.pts.length - 1][0]));

  const caption = (
    <>
      Flow capacity left, as a share of the intact {count(intact)} routes, as types are removed from the real graph. The
      shaded area under each curve, divided by the {percent(range[0], 0)} to {percent(range[1], 0)} range, is its AUC. The
      dots mark where each curve crosses the dashed half line, its halving point. Removing by {target.name.toLowerCase()}{" "}
      halves flow at {percent(target.fc)} and scores {fixed(target.auc, 3)}; random removal, the mean of{" "}
      {random.trials ?? meta.protocol.random_trials} orders, halves it at {percent(random.fc)} and scores{" "}
      {fixed(random.auc, 3)}.
    </>
  );

  return (
    <Figure id="measure-summary" title="Halving point and area under the curve" caption={caption}>
      <div className="ms-summary" ref={box}>
        <ChartFrame
          height={narrow ? 300 : 360}
          margin={narrow ? NARROW_MARGIN : WIDE_MARGIN}
          label={`Remaining flow capacity against share of types removed. ${target.name}: halving point ${percent(
            target.fc,
          )}, AUC ${fixed(target.auc, 3)}. Random: halving point ${percent(random.fc)}, AUC ${fixed(random.auc, 3)}.`}
        >
          {({ width: w, height: h }) => {
            const x = linear([0, xMax], [0, w]);
            const y = linear([0, 1], [h, 0]);
            const px = (pts) => pts.map(([f, v]) => [x(f), y(v)]);
            const area = (pts) => `${line(px(pts))}L${x(pts[pts.length - 1][0]).toFixed(1)} ${h}L${x(pts[0][0]).toFixed(1)} ${h}Z`;
            const endLabel = (s, dy) => {
              const [f, v] = s.pts[s.pts.length - 1];
              return narrow ? (
                <text className="ms-curve-label" x={x(f)} y={y(v) + dy} textAnchor="end">
                  {s.id === "random" ? "Random" : s.name}, AUC {fixed(s.auc, 3)}
                </text>
              ) : (
                <text className="ms-curve-label" x={x(f) + 10} y={y(v)} dy="0.32em">
                  <tspan>{s.id === "random" ? "Random" : s.name}</tspan>
                  <tspan className="ms-curve-sub" x={x(f) + 10} dy="1.25em">
                    AUC {fixed(s.auc, 3)}
                  </tspan>
                </text>
              );
            };
            return (
              <>
                <YAxis
                  scale={y}
                  ticks={[0, 0.25, 0.5, 0.75, 1]}
                  width={w}
                  format={(t) => `${Math.round(t * 100)}%`}
                  title="Flow capacity left"
                  inset={narrow ? 36 : 46}
                />
                <XAxis
                  scale={x}
                  ticks={[0, 0.1, 0.2, 0.3, 0.4, 0.5].filter((t) => t <= xMax + 1e-9)}
                  height={h}
                  width={w}
                  format={(t) => `${Math.round(t * 100)}%`}
                  title="Share of cell types removed"
                />
                <path d={area(random.pts)} className="ms-area" style={{ fill: "var(--s-random-ink)" }} />
                <path d={area(target.pts)} className="ms-area is-target" style={{ fill: `var(--s-${target.id}-ink)` }} />
                <line x1={0} x2={w} y1={y(0.5)} y2={y(0.5)} className="ms-half" />
                <text className="ms-half-label" x={w} y={y(0.5) + (narrow ? 15 : -7)} textAnchor="end">
                  Half of intact
                </text>
                {series.map((s) => (
                  <path
                    key={s.id}
                    d={line(px(s.pts))}
                    className="ms-curve"
                    style={{ stroke: `var(--s-${s.id}-ink)` }}
                  />
                ))}
                {series.map((s) => (
                  <g key={s.id} className="ms-fc">
                    <line x1={x(s.fc)} x2={x(s.fc)} y1={y(0.5)} y2={h} />
                    <circle cx={x(s.fc)} cy={y(0.5)} r={4.5} style={{ fill: `var(--s-${s.id}-ink)` }} />
                    <text x={x(s.fc) + 7} y={narrow ? y(0.5) - 9 : h - 8}>
                      <tspan className="ms-fc-symbol">f</tspan>
                      <tspan className="ms-fc-sub" dy="3">
                        c
                      </tspan>
                      <tspan dy="-3"> {percent(s.fc)}</tspan>
                    </text>
                  </g>
                ))}
                {endLabel(random, -10)}
                {endLabel(target, -10)}
              </>
            );
          }}
        </ChartFrame>
      </div>
    </Figure>
  );
}
