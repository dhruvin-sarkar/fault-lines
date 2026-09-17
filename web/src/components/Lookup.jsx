import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import Atlas, { FIELD_LIVE, atlasAspect } from "./Atlas.jsx";
import { ChartFrame, Row, Tooltip } from "./Chart.jsx";
import { Figure } from "./ui.jsx";
import { useWidth } from "../lib/hooks.js";
import { useAvailable, useData } from "../lib/data.js";
import { count, percent, sentence, signedCount, strategyLabel, superclassName } from "../lib/format.js";
import { useRovingRows } from "./findings/useRovingRows.js";
import { linear } from "../lib/scales.js";
import "../styles/findings-c.css";
import "../styles/lookup-pairs.css";

const LIMIT = 8;
const PICKS = 8;
const HASH = "#lookup/";
const COMPARTMENTS = { 0: "Brain", 1: "Nerve cord" };
const ROLES = { 1: "sensory", 2: "descending or motor" };

function hashName() {
  if (typeof window === "undefined" || !window.location.hash.startsWith(HASH)) return null;
  try {
    return decodeURIComponent(window.location.hash.slice(HASH.length));
  } catch {
    return null;
  }
}

/** Prefix matches first, shorter names first, then substring matches by match position; case-insensitive. */
function search(lower, names, query) {
  const q = query.trim().toLowerCase();
  if (!q) return [];
  const prefix = [];
  const inside = [];
  for (let i = 0; i < lower.length; i += 1) {
    const at = lower[i].indexOf(q);
    if (at === 0) prefix.push(i);
    else if (at > 0) inside.push([i, at]);
  }
  const byName = (a, b) => names[a].length - names[b].length || names[a].localeCompare(names[b]);
  prefix.sort(byName);
  if (prefix.length >= LIMIT) return prefix.slice(0, LIMIT);
  inside.sort((a, b) => a[1] - b[1] || byName(a[0], b[0]));
  return [...prefix, ...inside.map(([i]) => i)].slice(0, LIMIT);
}

function Highlighted({ text, query }) {
  const q = query.trim().toLowerCase();
  const at = q ? text.toLowerCase().indexOf(q) : -1;
  if (at < 0) return text;
  return (
    <>
      {text.slice(0, at)}
      <mark>{text.slice(at, at + q.length)}</mark>
      {text.slice(at + q.length)}
    </>
  );
}

export default function Lookup({ meta, percolation, types, atlas }) {
  const names = types.name;
  const total = names.length;
  const lower = useMemo(() => names.map((n) => n.toLowerCase()), [names]);
  const index = useMemo(() => new Map(names.map((n, i) => [n, i])), [names]);
  const aspect = useMemo(() => atlasAspect(types, atlas), [types, atlas]);

  const ranking = useMemo(() => {
    const order = names
      .map((_, i) => i)
      .sort((a, b) => types.flow_drop[b] - types.flow_drop[a] || names[a].localeCompare(names[b]));
    const above = new Map();
    const tied = new Map();
    order.forEach((i, position) => {
      const v = types.flow_drop[i];
      if (!above.has(v)) above.set(v, position);
      tied.set(v, (tied.get(v) ?? 0) + 1);
    });
    return { order, above, tied };
  }, [names, types.flow_drop]);

  const [selected, setSelected] = useState(() => {
    const fromHash = hashName();
    const i = fromHash == null ? -1 : names.indexOf(fromHash);
    return i >= 0 ? i : ranking.order[0];
  });
  // A linked name that matches no cell type; the hash is left as it is.
  const [unknown, setUnknown] = useState(() => {
    const fromHash = hashName();
    return fromHash && !names.includes(fromHash) ? fromHash : null;
  });
  const [query, setQuery] = useState("");
  const [open, setOpen] = useState(false);
  const [active, setActive] = useState(-1);
  const [pointer, setPointer] = useState(null);
  const mapBox = useRef(null);

  const suggestions = useMemo(() => search(lower, names, query), [lower, names, query]);
  const listOpen = open && query.trim().length > 0;

  const choose = useCallback(
    (i, { link = true } = {}) => {
      if (i == null || i < 0) return;
      setSelected(i);
      setUnknown(null);
      setQuery("");
      setOpen(false);
      setActive(-1);
      if (link) {
        const { pathname, search: params } = window.location;
        window.history.replaceState(null, "", `${pathname}${params}${HASH}${encodeURIComponent(names[i])}`);
      }
    },
    [names],
  );

  useEffect(() => {
    const onHash = () => {
      const name = hashName();
      if (name == null) return;
      if (index.has(name)) choose(index.get(name), { link: false });
      else setUnknown(name || null);
    };
    window.addEventListener("hashchange", onHash);
    return () => window.removeEventListener("hashchange", onHash);
  }, [index, choose]);

  useEffect(() => {
    if (active >= 0) document.getElementById(`lookup-option-${active}`)?.scrollIntoView({ block: "nearest" });
  }, [active]);

  function onKeyDown(event) {
    if (event.nativeEvent.isComposing) return;
    const n = suggestions.length;
    if (event.key === "ArrowDown") {
      event.preventDefault();
      setOpen(true);
      if (n) setActive((a) => (a + 1) % n);
    } else if (event.key === "ArrowUp") {
      event.preventDefault();
      setOpen(true);
      if (n) setActive((a) => (a <= 0 ? n - 1 : a - 1));
    } else if (event.key === "Enter") {
      if (listOpen && n) {
        event.preventDefault();
        choose(suggestions[active >= 0 ? active : 0]);
      }
    } else if (event.key === "Escape") {
      if (listOpen) {
        event.preventDefault();
        setOpen(false);
        setActive(-1);
      } else if (query) {
        event.preventDefault();
        setQuery("");
      }
    }
  }

  const anchor = types.anchor[selected];
  const neighbors = useMemo(() => {
    const set = new Set();
    if (anchor < 0) return set;
    for (let i = 0; i < total; i += 1) if (i !== selected && types.anchor[i] === anchor) set.add(i);
    return set;
  }, [anchor, selected, total, types.anchor]);

  const picks = ranking.order.slice(0, PICKS);
  const name = names[selected];

  return (
    <section className="section" id="lookup" aria-labelledby="lookup-title">
      <div className="wrap">
        <div className="section-head">
          <h2 id="lookup-title">Look up any cell type</h2>
          <p className="lede">
            All {count(total)} cell types, with what removing each one alone costs and when each removal strategy takes
            it out. Search by name, start from the types whose loss costs most, or pick a point on the map.
          </p>
        </div>

        {unknown && (
          <p className="fc-unknown" role="status">
            No cell type is named &ldquo;{unknown}&rdquo;. Search for another name below, or pick one of the types
            listed.
          </p>
        )}

        <div className="fc-lookup">
          <div className="fc-lookup-main">
            <div>
              <div className="fc-search">
                <label className="field-label" htmlFor="lookup-input" id="lookup-label">
                  Cell type name
                </label>
                <input
                  id="lookup-input"
                  className="input"
                  type="text"
                  role="combobox"
                  aria-autocomplete="list"
                  aria-expanded={listOpen}
                  aria-controls="lookup-listbox"
                  aria-activedescendant={listOpen && active >= 0 ? `lookup-option-${active}` : undefined}
                  autoComplete="off"
                  autoCapitalize="off"
                  spellCheck={false}
                  placeholder="Search, for example DNp01"
                  value={query}
                  onChange={(event) => {
                    setQuery(event.target.value);
                    setOpen(true);
                    setActive(-1);
                  }}
                  onFocus={() => query && setOpen(true)}
                  onBlur={() => setOpen(false)}
                  onKeyDown={onKeyDown}
                />
                <ul
                  className="fc-listbox"
                  id="lookup-listbox"
                  role="listbox"
                  aria-labelledby="lookup-label"
                  hidden={!listOpen}
                >
                  {suggestions.map((i, k) => (
                    <li
                      key={i}
                      id={`lookup-option-${k}`}
                      role="option"
                      aria-selected={k === active}
                      onMouseDown={(event) => event.preventDefault()}
                      onMouseEnter={() => setActive(k)}
                      onClick={() => choose(i)}
                    >
                      <span className="id">
                        <Highlighted text={names[i]} query={query} />
                      </span>
                      <span className="fc-option-meta">{sentence(superclassName(types.superclasses[types.superclass[i]]))}</span>
                    </li>
                  ))}
                  {listOpen && suggestions.length === 0 && (
                    <li className="fc-empty" role="presentation">
                      No cell type name contains &ldquo;{query.trim()}&rdquo;.
                    </li>
                  )}
                </ul>
              </div>

              <div className="fc-picks">
                <div className="label" id="lookup-picks">
                  The {PICKS} types whose removal alone costs the most flow
                </div>
                <div className="choices" role="group" aria-labelledby="lookup-picks">
                  {picks.map((i) => (
                    <button key={i} type="button" className="choice" aria-pressed={i === selected} onClick={() => choose(i)}>
                      {names[i]}
                    </button>
                  ))}
                </div>
              </div>
            </div>

            <Profile index={selected} meta={meta} percolation={percolation} types={types} ranking={ranking} />
          </div>

          <div className="fc-lookup-map">
            <Figure
              variant="field"
              title={
                <>
                  Where <span className="id">{name}</span> sits
                </>
              }
              caption={
                <>
                  One point per cell type, placed where its synapses lie; brain above, nerve cord below. Hover a point
                  for its name and select it to look it up.
                </>
              }
            >
              <div
                ref={mapBox}
                className="fc-map"
                style={{ aspectRatio: `${aspect}`, maxWidth: `calc(40rem * ${aspect})`, cursor: pointer ? "pointer" : undefined }}
              >
                <Atlas
                  types={types}
                  atlas={atlas}
                  tone="field"
                  focus={selected}
                  highlight={neighbors}
                  highlightTone="neutral"
                  label={`Map of the central nervous system with ${name} ringed and the other types in its main neuropil highlighted`}
                  onType={(i, event) => {
                    if (i == null || !event) {
                      setPointer(null);
                      return;
                    }
                    if (event.type === "pointerdown") {
                      choose(i);
                      return;
                    }
                    const rect = mapBox.current.getBoundingClientRect();
                    setPointer({ index: i, x: event.clientX - rect.left, y: event.clientY - rect.top, width: rect.width });
                  }}
                />
                {pointer && (
                  <Tooltip x={pointer.x} y={pointer.y - 6} width={pointer.width}>
                    <div className="fc-tip">
                      <strong>
                        <span className="id">{names[pointer.index]}</span>
                      </strong>
                      <span className="fc-tip-sub">
                        {sentence(superclassName(types.superclasses[types.superclass[pointer.index]]))}
                      </span>
                      <Row label="Routes lost when removed alone" value={count(types.flow_drop[pointer.index])} />
                    </div>
                  </Tooltip>
                )}
              </div>
              <div className="fc-map-key" aria-hidden="true">
                <span>
                  <svg width="14" height="14" viewBox="-7 -7 14 14">
                    <circle r="5.5" style={{ fill: "none", stroke: "var(--field-ink)", strokeWidth: 1.5 }} />
                  </svg>
                  <span className="id">{name}</span>
                </span>
                {neighbors.size > 0 && (
                  <span>
                    <svg width="10" height="10" viewBox="-5 -5 10 10">
                      <rect x="-3" y="-3" width="6" height="6" style={{ fill: "var(--field-ink)" }} />
                    </svg>
                    {count(neighbors.size)} other types mostly in {types.anchors[anchor]}
                  </span>
                )}
                <span>
                  <svg width="10" height="10" viewBox="-5 -5 10 10">
                    <rect x="-2" y="-2" width="4" height="4" style={{ fill: `var(--field-live, ${FIELD_LIVE})`, opacity: 0.6 }} />
                  </svg>
                  All other types
                </span>
              </div>
            </Figure>
          </div>
        </div>
      </div>
    </section>
  );
}

function Profile({ index, meta, percolation, types, ranking }) {
  const name = types.name[index];
  const anchor = types.anchor[index];
  const role = ROLES[types.role[index]];
  const neurons = types.neurons[index];
  const heading = useRef(null);
  const followed = useRef(false);

  useEffect(() => {
    if (!followed.current) return;
    followed.current = false;
    heading.current?.focus();
  }, [index]);

  return (
    <article className="fc-profile" aria-labelledby="lookup-profile-name">
      <header>
        <h3 id="lookup-profile-name" className="fc-profile-name" ref={heading} tabIndex={-1}>
          {name}
        </h3>
        <p className="fc-profile-meta">
          {anchor >= 0 && <span>Most synapses in {types.anchors[anchor]}</span>}
          {role && <span>In the {role} set</span>}
        </p>
      </header>

      <dl className="facts">
        <div>
          <dt>Neurons in the type</dt>
          <dd>{count(neurons)}</dd>
        </div>
        <div>
          <dt>Superclass</dt>
          <dd className="fc-fact-text">{sentence(superclassName(types.superclasses[types.superclass[index]]))}</dd>
        </div>
        <div>
          <dt>Compartment</dt>
          <dd className="fc-fact-text">{COMPARTMENTS[types.compartment[index]] ?? "Not assigned"}</dd>
        </div>
        <div>
          <dt>Input partner types</dt>
          <dd>{count(types.in_degree[index])}</dd>
        </div>
        <div>
          <dt>Output partner types</dt>
          <dd>{count(types.out_degree[index])}</dd>
        </div>
        <div>
          <dt>Input synapses, within the graph</dt>
          <dd>{count(types.in_strength[index])}</dd>
        </div>
        <div>
          <dt>Output synapses, within the graph</dt>
          <dd>{count(types.out_strength[index])}</dd>
        </div>
      </dl>

      <Removal
        index={index}
        meta={meta}
        types={types}
        ranking={ranking}
        onFollow={() => {
          followed.current = true;
        }}
      />

      <div>
        <div className="fc-timing-head">
          <h4 className="fc-timing-title">When each strategy reaches it</h4>
        </div>
        <div className="legend fc-legend" aria-hidden="true">
          <span>
            <svg width="12" height="12" viewBox="-6 -6 12 12">
              <circle r="5" className="fc-glyph-ink" />
            </svg>
            Removed, in the strategy&apos;s color
          </span>
          <span>
            <svg width="12" height="12" viewBox="-6 -6 12 12">
              <circle r="4.25" className="fc-glyph-ring" />
            </svg>
            Cut off from all sensory input
          </span>
          <span>
            <svg width="8" height="14" viewBox="-4 -7 8 14">
              <path d="M0 -6V6" style={{ stroke: "var(--signal)", strokeWidth: 2 }} />
            </svg>
            Flow capacity halved
          </span>
        </div>
        <Timing index={index} meta={meta} percolation={percolation} types={types} />
        <p className="caption" style={{ marginTop: "1rem" }}>
          The share of cell types already removed when a strategy takes this type out, or first leaves it with no route
          from any sensory type. Random removal shows the first of {count(meta.protocol.random_trials)} trials.
          {meta.strategies.some((s) => types.silenced[s.id][index] === 0)
            ? " This type has no route from any sensory type even in the intact graph."
            : ""}
        </p>
      </div>
    </article>
  );
}

const OWN_PAIRS = { 1: "as a sensory source", 2: "as a motor target" };

function TypeLink({ name, onFollow }) {
  return (
    <a className="lk-type" href={`${HASH}${encodeURIComponent(name)}`} onClick={onFollow}>
      <span className="id">{name}</span>
    </a>
  );
}

function Change({ value }) {
  return value > 0 ? (
    <span className="lk-change">{signedCount(-value)}</span>
  ) : (
    <span className="lk-change is-none">no change</span>
  );
}

/** Flow capacity and reachable pairs with and without the type, and the pairs whose last route runs through it. */
function Removal({ index, meta, types, ranking, onFollow }) {
  const name = types.name[index];
  const intact = meta.graph.intact_flow;
  const reachable = meta.graph.intact_reachable_pairs;
  const drop = types.flow_drop[index];
  const lost = types.pairs_lost[index];
  const rank = ranking.above.get(drop) + 1;
  const tied = ranking.tied.get(drop);
  const available = useAvailable();
  const listed = Boolean(available?.has("pair_loss.json"));
  const { data, error } = useData(lost > 0 && listed ? "pair_loss.json" : null);

  return (
    <div className="lk-removal">
      <div className="fc-timing-head">
        <h4 className="fc-timing-title">What removing it alone breaks</h4>
      </div>

      <table className="data lk-compare">
        <caption className="visually-hidden">Sensory-to-motor connectivity with and without {name}</caption>
        <thead>
          <tr>
            <th scope="col">Measure</th>
            <th scope="col" className="num">
              Intact
            </th>
            <th scope="col" className="num">
              Without it
            </th>
          </tr>
        </thead>
        <tbody>
          <tr>
            <th scope="row">Flow capacity, in edge-disjoint routes</th>
            <td className="num">{count(intact)}</td>
            <td className="num">
              <span className="lk-after">{count(intact - drop)}</span>
              <Change value={drop} />
            </td>
          </tr>
          <tr>
            <th scope="row">Sensory-motor pairs with a path</th>
            <td className="num">{count(reachable)}</td>
            <td className="num">
              <span className="lk-after">{count(reachable - lost)}</span>
              <Change value={lost} />
            </td>
          </tr>
        </tbody>
      </table>

      <p className="caption lk-note">
        {drop > 0 ? (
          <>
            Removing it alone costs {percent(drop / intact, 2)} of flow capacity, rank {count(rank)} of{" "}
            {count(types.name.length)}
            {tied > 1 ? `, tied with ${count(tied - 1)} other ${tied === 2 ? "type" : "types"}` : ""}.
          </>
        ) : (
          <>Like {count(tied - 1)} other types, removing it alone leaves all {count(intact)} routes in place.</>
        )}
      </p>

      <div className="lk-pairs">
        <h5 className="lk-pairs-title">Sensory-motor pairs that lose their only path</h5>
        <PairList
          name={name}
          lost={lost}
          role={types.role[index]}
          entry={data?.types[name]}
          limit={data?.limit}
          state={lost === 0 ? "none" : !listed || error ? "unlisted" : data ? "ready" : "loading"}
          onFollow={onFollow}
        />
      </div>
    </div>
  );
}

function PairList({ name, lost, role, entry, limit, state, onFollow }) {
  if (state === "none") {
    return <p className="lk-text">None. Without it, every sensory-motor pair keeps another route.</p>;
  }
  if (state === "unlisted") {
    return <p className="lk-text">{count(lost)} pairs lose their only path; the list of pairs is not in this build.</p>;
  }
  if (state === "loading") {
    return <p className="lk-text lk-quiet">Loading the {count(lost)} pairs.</p>;
  }

  const other = entry?.other ?? 0;
  const own = lost - other;
  const ownText = OWN_PAIRS[role] ?? "as an endpoint";
  if (other === 0) {
    return (
      <p className="lk-text">
        All {count(lost)} are its own pairs, {ownText}. Every pair between two other types keeps another route.
      </p>
    );
  }

  const hiddenSources = entry.sources_total - entry.sources.length;
  return (
    <>
      <p className="lk-text">
        {count(other)} {other === 1 ? "pair" : "pairs"} between two other types {other === 1 ? "has" : "have"} no route
        left without <span className="id">{name}</span>
        {own > 0 ? `, plus its own ${count(own)} ${own === 1 ? "pair" : "pairs"} ${ownText}` : ""}.
      </p>
      <ul className="lk-groups">
        {entry.sources.map((group) => {
          const more = group.lost - group.motors.length;
          return (
            <li key={group.sensory} className="lk-group">
              <p className="lk-group-head">
                <TypeLink name={group.sensory} onFollow={onFollow} />
                <span>
                  loses its only path to{" "}
                  {group.lost === group.reach
                    ? `all ${count(group.lost)} motor types it reaches`
                    : `${count(group.lost)} of the ${count(group.reach)} motor types it reaches`}
                </span>
              </p>
              <ul className="lk-motors" aria-label={`Motor types ${group.sensory} can no longer reach`}>
                {group.motors.map((motor) => (
                  <li key={motor}>
                    <TypeLink name={motor} onFollow={onFollow} />
                  </li>
                ))}
                {more > 0 && <li className="lk-more">and {count(more)} more</li>}
              </ul>
            </li>
          );
        })}
      </ul>
      {hiddenSources > 0 && (
        <p className="lk-text">
          And {count(hiddenSources)} more sensory {hiddenSources === 1 ? "type" : "types"}.
        </p>
      )}
      <p className="caption">
        Sensory types with the most lost pairs come first. Motor types are listed descending neurons first, then
        central brain and nerve cord motor types, each by name{limit ? `, up to ${count(limit)} per sensory type` : ""}.
        Select a name to look that type up.
      </p>
    </>
  );
}

function Timing({ index, meta, percolation, types }) {
  const [wrapRef, width] = useWidth();
  const [hover, setHover] = useState(null);
  const strategies = meta.strategies;
  const end = Math.max(...strategies.map((s) => percolation.strategies[s.id].fraction_removed.at(-1)));
  const wide = width >= 520;
  const rowH = wide ? 34 : 50;
  const rowProps = useRovingRows(
    strategies.map((s) => s.id),
    (id) => setHover(id == null ? null : strategies.findIndex((s) => s.id === id)),
  );
  const margin = { top: 8, right: 0, bottom: 44, left: wide ? 190 : 0 };
  const height = strategies.length * rowH + margin.top + margin.bottom;
  const trackY = wide ? rowH / 2 : 34;

  const rows = strategies.map((s) => {
    const run = percolation.strategies[s.id];
    const removedBatch = types.removed[s.id][index];
    const silencedBatch = types.silenced[s.id][index];
    const removed = removedBatch > 0 ? run.fraction_removed[removedBatch] : null;
    const silenced = silencedBatch > 0 ? run.fraction_removed[silencedBatch] : null;
    let summary;
    if (removed != null) summary = `removed at ${percent(removed)}`;
    else if (silencedBatch === 0) summary = "no sensory input";
    else if (silenced != null) summary = `cut off at ${percent(silenced)}`;
    else summary = `kept to ${percent(run.fraction_removed.at(-1), 0)}`;
    return { ...s, label: strategyLabel(s.id, { capital: true }), removed, silenced, silencedBatch, critical: run.critical_fraction, summary };
  });

  return (
    <div ref={wrapRef}>
      <ChartFrame
        height={height}
        margin={margin}
        role="group"
        label={`When each removal strategy reaches ${types.name[index]}: ${rows.map((r) => `${r.label}, ${r.summary}`).join("; ")}`}
        onPointer={(_x, y) => {
          const i = Math.floor(y / rowH);
          setHover(i >= 0 && i < rows.length ? i : null);
        }}
        onLeave={() => setHover(null)}
        overlay={({ margin: m, width: w }) => {
          if (hover == null) return null;
          const r = rows[hover];
          const x = linear([0, end], [0, Math.max(10, w - m.left - m.right - 118)]);
          const at = r.removed ?? r.silenced ?? r.critical ?? 0;
          return (
            <Tooltip x={m.left + x(Math.min(end, at))} y={m.top + hover * rowH + trackY - 10} width={w}>
              <div className="fc-tip">
                <strong>{r.label}</strong>
                <Row label="Removed" value={r.removed != null ? percent(r.removed) : `not by ${percent(end, 0)}`} />
                <Row
                  label="Cut off from sensory input"
                  value={
                    r.silencedBatch === 0
                      ? "already, intact"
                      : r.silenced != null
                        ? percent(r.silenced)
                        : r.removed != null
                          ? "not before removal"
                          : `not by ${percent(end, 0)}`
                  }
                />
                <Row label="Flow capacity halved" value={r.critical != null ? percent(r.critical) : "not reached"} />
              </div>
            </Tooltip>
          );
        }}
      >
        {(inner) => {
          const valueW = 118;
          const span = Math.max(10, inner.width - valueW);
          const x = linear([0, end], [0, span]);
          const ticks = [0, 0.1, 0.2, 0.3, 0.4, 0.5].filter((t) => t <= end + 1e-9 && (span >= 240 || t * 10 % 2 === 0));
          const body = rows.length * rowH;
          return (
            <g>
              {ticks.map((t) => (
                <g key={t} className="tick" transform={`translate(${x(t)},0)`}>
                  <line y1={-4} y2={body} />
                </g>
              ))}
              <g transform={`translate(0,${body})`}>
                <line className="axis-line" x2={span} />
                {ticks.map((t) => (
                  <text key={t} x={x(t)} y={18} textAnchor={t === 0 ? "start" : "middle"}>
                    {percent(t, 0)}
                  </text>
                ))}
                <text className="axis-title" x={inner.width} y={38} textAnchor="end">
                  Share of cell types removed
                </text>
              </g>
              {rows.map((r, i) => {
                const y = i * rowH;
                const cy = y + trackY;
                return (
                  <g
                    key={r.id}
                    {...rowProps(r.id)}
                    className="fc-row fc-row-static"
                    role="img"
                    aria-label={`${r.label}: ${r.summary}`}
                  >
                    <rect
                      className="fc-band"
                      x={-margin.left}
                      y={y}
                      width={inner.width + margin.left}
                      height={rowH}
                      rx={3}
                      style={{ opacity: i === hover ? 1 : 0 }}
                    />
                    <rect x={wide ? -margin.left : 0} y={(wide ? cy : y + 15) - 5} width={10} height={10} rx={2} style={{ fill: `var(--s-${r.id}-ink)` }} />
                    <text className="fc-row-label" x={(wide ? -margin.left : 0) + 16} y={wide ? cy : y + 15} dy="0.32em" style={{ fontStretch: "100%", fontWeight: 500 }}>
                      {r.label}
                    </text>
                    <line className="fc-track" x1={0} x2={span} y1={cy} y2={cy} />
                    {r.critical != null && r.critical <= end && (
                      <path d={`M${x(r.critical)} ${cy - 8}V${cy + 8}`} style={{ stroke: "var(--signal)", strokeWidth: 2 }} />
                    )}
                    {r.silenced != null && <circle cx={x(r.silenced)} cy={cy} r={4.5} className="fc-ring" />}
                    {r.removed != null && (
                      <circle cx={x(r.removed)} cy={cy} r={5.5} style={{ fill: `var(--s-${r.id}-ink)`, stroke: "var(--paper)", strokeWidth: 1.5 }} />
                    )}
                    <text
                      className={r.removed != null || r.silenced != null ? "fc-value" : "fc-value-quiet"}
                      x={inner.width}
                      y={cy}
                      dy="0.32em"
                      textAnchor="end"
                    >
                      {r.summary}
                    </text>
                    <rect className="fc-hit" x={-margin.left} y={y} width={inner.width + margin.left} height={rowH} rx={3} />
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
