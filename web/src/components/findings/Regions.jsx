import { useCallback, useMemo, useRef, useState } from "react";
import { Finding } from "./Finding.jsx";
import { useRovingRows } from "./useRovingRows.js";
import Atlas, { atlasAspect } from "../Atlas.jsx";
import { ChartFrame, Row, Tooltip } from "../Chart.jsx";
import { Figure, Segmented, Sidenote, TextBlock } from "../ui.jsx";
import { useData } from "../../lib/data.js";
import { useReducedMotion, useTokens } from "../../lib/hooks.js";
import { linear, niceTicks } from "../../lib/scales.js";
import { count, percent, pValue } from "../../lib/format.js";
import "../../styles/findings-a.css";

const ID = "regions";
const TITLE = "Where it hurts";
const TOP = 20;
const ROW = 26;
const SIGNIFICANCE = 0.05;
const SORTS = [
  { value: "flow_drop", label: "Flow lost" },
  { value: "excess", label: "Above random" },
];

const NEUROPILS = {
  AB: "asymmetrical body",
  AL: "antennal lobe",
  AME: "accessory medulla",
  ANm: "abdominal neuromeres",
  AOTU: "anterior optic tubercle",
  ATL: "antler",
  AVLP: "anterior ventrolateral protocerebrum",
  CA: "calyx",
  CRE: "crepine",
  EB: "ellipsoid body",
  EPA: "epaulette",
  FB: "fan-shaped body",
  FLA: "flange",
  GNG: "gnathal ganglia",
  GOR: "gorget",
  HTct: "haltere tectulum",
  IB: "inferior bridge",
  ICL: "inferior clamp",
  IPS: "inferior posterior slope",
  IntTct: "intermediate tectulum",
  LA: "lamina",
  LAL: "lateral accessory lobe",
  LH: "lateral horn",
  LO: "lobula",
  LOP: "lobula plate",
  LTct: "lower tectulum",
  LegNp: "leg neuropil",
  ME: "medulla",
  NO: "noduli",
  NTct: "neck tectulum",
  Ov: "ovoid",
  PB: "protocerebral bridge",
  PLP: "posterior lateral protocerebrum",
  PRW: "prow",
  PVLP: "posterior ventrolateral protocerebrum",
  SAD: "saddle",
  SCL: "superior clamp",
  SIP: "superior intermediate protocerebrum",
  SLP: "superior lateral protocerebrum",
  SMP: "superior medial protocerebrum",
  SPS: "superior posterior slope",
  VES: "vest",
  WED: "wedge",
  WTct: "wing tectulum",
  aL: "mushroom body alpha lobe",
  "a'L": "mushroom body alpha prime lobe",
  bL: "mushroom body beta lobe",
  "b'L": "mushroom body beta prime lobe",
  gL: "mushroom body gamma lobe",
  mVAC: "medial ventral association center",
};
const SEGMENTS = { T1: "prothoracic", T2: "mesothoracic", T3: "metathoracic" };

function describe(name) {
  const base = NEUROPILS[name.split("(")[0]];
  if (!base) return null;
  const segment = name.match(/T[123]/)?.[0];
  const side = name.endsWith("(L)") ? "left" : name.endsWith("(R)") ? "right" : null;
  return [base, segment && SEGMENTS[segment], side].filter(Boolean).join(", ");
}

function hexToRgb(hex) {
  const h = hex.replace("#", "").slice(0, 6);
  return [0, 2, 4].map((i) => Number.parseInt(h.slice(i, i + 2), 16));
}

const mix = (a, b, t) => a.map((c, i) => c + (b[i] - c) * t);

/*
 * Ramp stops for the black field, all derived from --signal-glow: position on the scale, then how far the glow is
 * mixed up from black (up to 1) or on towards white (above 1). Lightness rises with loss, so the largest losses are
 * the brightest marks.
 */
const RAMP_STOPS = [
  [0, 0.12],
  [0.3, 0.36],
  [0.62, 0.72],
  [0.86, 1],
  [1, 1.7],
];

function fieldRamp(glow) {
  if (!glow) return () => undefined;
  const base = hexToRgb(glow);
  const black = [0, 0, 0];
  const white = [255, 255, 255];
  const stops = RAMP_STOPS.map(([t, k]) => [t, k <= 1 ? mix(black, base, k) : mix(base, white, k - 1)]);
  return (t) => {
    const v = Math.max(0, Math.min(1, t));
    let k = 1;
    while (k < stops.length - 1 && stops[k][0] < v) k += 1;
    const [t0, from] = stops[k - 1];
    const [t1, to] = stops[k];
    return `rgb(${mix(from, to, (v - t0) / (t1 - t0 || 1)).map(Math.round).join(",")})`;
  };
}

function RegionTip({ region, rank, total }) {
  const description = describe(region.neuropil);
  return (
    <div className="fa-tip">
      <strong>
        <span className="id">{region.neuropil}</span>
      </strong>
      {description && <span className="fa-tip-sub">{description}</span>}
      <Row label="Flow capacity lost" value={percent(region.flow_drop)} />
      <Row label="Random sets, mean ± SD" value={`${percent(region.random_mean)} ± ${percent(region.random_sd)}`} />
      <Row label="p, upper tail" value={pValue(region.p_value)} />
      <Row label="Anchored types" value={count(region.types)} />
      <Row label="Sensory, motor" value={`${count(region.sensory)}, ${count(region.motor)}`} />
      <span className="fa-tip-sub">
        Rank {rank} of {total} by flow lost
      </span>
    </div>
  );
}

export default function Regions({ types, atlas }) {
  const { data: regions } = useData("regions.json");
  return regions?.length ? <RegionsView types={types} atlas={atlas} regions={regions} /> : null;
}

function RegionsView({ types, atlas, regions }) {
  const [active, setActive] = useState(null);
  const [sort, setSort] = useState("flow_drop");
  const mapRef = useRef(null);
  const reduced = useReducedMotion();
  const tokens = useTokens(["signal-glow"]);

  const byName = useMemo(() => (regions ? Object.fromEntries(regions.map((r) => [r.neuropil, r])) : {}), [regions]);
  const ranked = useMemo(() => (regions ? [...regions].sort((a, b) => b.flow_drop - a.flow_drop) : []), [regions]);
  const max = ranked[0]?.flow_drop || 1;
  const ramp = useMemo(() => fieldRamp(tokens["signal-glow"]), [tokens]);
  const shade = useCallback((value) => ramp(Math.sqrt(Math.max(0, value) / max)), [ramp, max]);
  const regionFill = useCallback(
    (outline) => (byName[outline.neuropil] ? shade(byName[outline.neuropil].flow_drop) : undefined),
    [byName, shade],
  );
  const aspect = useMemo(() => atlasAspect(types, atlas), [types, atlas]);

  const top = ranked[0];
  const topName = describe(top.neuropil);
  const rankOf = (name) => ranked.findIndex((r) => r.neuropil === name) + 1;
  const excess = (r) => r.flow_drop - r.random_mean;
  const listed = [...ranked].sort((a, b) => (sort === "flow_drop" ? b.flow_drop - a.flow_drop : excess(b) - excess(a))).slice(0, TOP);
  const above = regions.filter((r) => r.p_value < SIGNIFICANCE && r.flow_drop > r.random_mean);
  const below = [...regions].sort((a, b) => excess(a) - excess(b))[0];
  const topExcess = [...regions].sort((a, b) => excess(b) - excess(a))[0];
  const unscored = atlas.outlines.filter((o) => !byName[o.neuropil]).length;
  const xMax = Math.max(...listed.map((r) => Math.max(r.flow_drop, r.random_mean + r.random_sd)));
  const activeRegion = active ? byName[active.name] : null;
  const activeRow = active ? listed.findIndex((r) => r.neuropil === active.name) : -1;
  const gradient = tokens["signal-glow"]
    ? [0, 0.25, 0.5, 0.75, 1].map((t) => `${ramp(t)} ${t * 100}%`).join(", ")
    : null;
  const regionLabel = (r) => (describe(r.neuropil) ? `the ${describe(r.neuropil)} (${r.neuropil})` : r.neuropil);

  function onMap(outline, event) {
    if (!outline || !byName[outline.neuropil] || !event) {
      setActive(null);
      return;
    }
    const rect = mapRef.current.getBoundingClientRect();
    setActive({ name: outline.neuropil, source: "map", x: event.clientX - rect.left, y: event.clientY - rect.top, w: rect.width });
  }

  const rowProps = useRovingRows(
    listed.map((r) => r.neuropil),
    (name) => setActive(name ? { name, source: "bars" } : null),
  );
  const margin = { top: 26, right: 12, bottom: 40, left: 118 };
  const barHeight = TOP * ROW + margin.top + margin.bottom;

  return (
    <Finding
      id={ID}
      title={TITLE}
      stat={percent(top.flow_drop)}
      statLabel={`of flow capacity lost when the ${count(top.types)} cell types anchored in ${top.neuropil} are removed`}
    >
      <TextBlock
        notes={
          <>
            <Sidenote title="Anchoring">
              Each cell type belongs to the one neuropil holding most of its synapses, so a type that spans several
              regions is counted once.
            </Sidenote>
            <Sidenote title="Size matters">
              A neuropil with many types loses more simply by holding more. Each region is compared with random sets of
              the same number of types, and p is the share of those sets that lose at least as much.
            </Sidenote>
          </>
        }
      >
        <p>
          Removing every cell type anchored in one neuropil at once shows where sensory-to-motor routing is
          concentrated. Losing the {count(top.types)} types of {topName ? `the ${topName}` : top.neuropil} costs{" "}
          {percent(top.flow_drop)} of flow capacity, against {percent(top.random_mean)} for random sets of that size.
        </p>
        <p>
          {above.length} of {regions.length} neuropils lose more than their random sets at p &lt; {SIGNIFICANCE},
          uncorrected. The largest excess over random belongs to {regionLabel(topExcess)}, at{" "}
          {percent(topExcess.flow_drop)} against {percent(topExcess.random_mean)}.
          {excess(below) < 0 &&
            ` At the other end, removing ${regionLabel(below)} costs ${percent(below.flow_drop)}, less than the ${percent(below.random_mean)} lost by random sets of its size.`}
        </p>
      </TextBlock>

      <Figure
        variant="field"
        className={reduced ? "fa-still" : ""}
        title="Flow capacity lost when each neuropil's cell types are removed"
        controls={<Segmented label="Rank neuropils by" options={SORTS} value={sort} onChange={setSort} />}
        caption={
          <>
            Left, the male central nervous system with brain above and nerve cord below; each neuropil glows by the
            share of flow capacity lost when its anchored types are removed, on a square-root scale so small regions stay
            distinct. Points are cell types.{unscored > 0 && " Neuropils without a score stay dark."} Right, the{" "}
            {TOP} neuropils with the largest {sort === "flow_drop" ? "loss" : "loss above random"}; the white tick is
            the mean loss of same-size random sets and its whisker one standard deviation. Hover either side to find
            the same neuropil in the other, or focus the list and use the arrow keys.
          </>
        }
      >
        <div className="fa-regions">
          <div>
            <div ref={mapRef} className="fa-map" style={{ aspectRatio: `${aspect}`, maxWidth: `calc(46rem * ${aspect})` }}>
              <Atlas
                types={types}
                atlas={atlas}
                tone="field"
                regionFill={regionFill}
                activeRegion={active?.name}
                pointAlpha={0.16}
                onRegion={onMap}
                label={`Map of the male central nervous system, each neuropil shaded by the flow capacity lost when its anchored cell types are removed. Highest: ${top.neuropil}, ${percent(top.flow_drop)}.`}
              />
              {active?.source === "map" && activeRegion && (
                <Tooltip x={active.x} y={active.y - 6} width={active.w}>
                  <RegionTip region={activeRegion} rank={rankOf(active.name)} total={ranked.length} />
                </Tooltip>
              )}
            </div>
            <div className="fa-map-key">
              {gradient && (
                <div
                  className="fa-ramp"
                  role="img"
                  aria-label={`Colour scale from 0% to ${percent(max)} of flow capacity lost, square-root scaled`}
                >
                  <span>0%</span>
                  <span className="fa-ramp-bar" style={{ background: `linear-gradient(to right, ${gradient})` }} />
                  <span>{percent(max)} lost</span>
                </div>
              )}
              {unscored > 0 && (
                <span className="fa-unscored">
                  <span className="swatch" aria-hidden="true" />
                  Not scored
                </span>
              )}
            </div>
          </div>

          <div>
            <ChartFrame
              height={barHeight}
              margin={margin}
              role="group"
              label={`Use the arrow keys to move between neuropils. Top ${TOP} neuropils by ${sort === "flow_drop" ? "flow capacity lost" : "loss above same-size random sets"}, each with the random-set mean and standard deviation.`}
              onPointer={(_x, y) => {
                const i = Math.floor(y / ROW);
                if (i >= 0 && i < listed.length) setActive({ name: listed[i].neuropil, source: "bars" });
                else setActive(null);
              }}
              onLeave={() => setActive(null)}
              overlay={({ margin: m, width: w }) => {
                if (active?.source !== "bars" || activeRow < 0) return null;
                const scale = linear([0, xMax], [0, w - m.left - m.right]);
                const r = listed[activeRow];
                return (
                  <Tooltip x={m.left + scale(Math.max(r.flow_drop, r.random_mean))} y={m.top + activeRow * ROW + 4} width={w}>
                    <RegionTip region={r} rank={rankOf(r.neuropil)} total={ranked.length} />
                  </Tooltip>
                );
              }}
            >
              {(inner) => {
                const x = linear([0, xMax], [0, inner.width]);
                const ticks = niceTicks([0, xMax], inner.width < 260 ? 3 : 4).filter((t) => t <= xMax);
                return (
                  <g>
                    {ticks.map((t) => (
                      <g key={t} className="tick" transform={`translate(${x(t)},0)`}>
                        <line y1={-4} y2={inner.height} />
                        <text y={-12} textAnchor="middle">
                          {percent(t, 0)}
                        </text>
                      </g>
                    ))}
                    <line className="axis-line" x2={inner.width} y1={inner.height} y2={inner.height} />
                    <text className="axis-title" x={inner.width} y={inner.height + 26} textAnchor="end">
                      Flow capacity lost
                    </text>
                    {listed.map((r, i) => {
                      const on = active?.name === r.neuropil;
                      return (
                        <g
                          key={r.neuropil}
                          {...rowProps(r.neuropil)}
                          className="fa-move fa-focusable"
                          style={{ transform: `translateY(${i * ROW}px)` }}
                          role="img"
                          aria-label={`${r.neuropil}: ${percent(r.flow_drop)} lost; random sets ${percent(r.random_mean)}; p ${pValue(r.p_value)}`}
                        >
                          <rect
                            className={`fa-band${on ? " is-on" : ""}`}
                            x={-margin.left + 2}
                            width={inner.width + margin.left + margin.right - 4}
                            y={1}
                            height={ROW - 2}
                            rx={3}
                          />
                          <text className="fa-row-label" x={-10} y={ROW / 2} dy="0.32em" textAnchor="end">
                            {r.neuropil}
                          </text>
                          <rect x={0} y={ROW / 2 - 6} width={Math.max(1, x(r.flow_drop))} height={12} rx={1} style={{ fill: shade(r.flow_drop) }} />
                          <path
                            d={`M${x(Math.max(0, r.random_mean - r.random_sd))} ${ROW / 2}H${x(r.random_mean + r.random_sd)}M${x(r.random_mean)} ${ROW / 2 - 8}V${ROW / 2 + 8}`}
                            style={{ stroke: "var(--field)", strokeWidth: 4, opacity: 0.7 }}
                          />
                          <path
                            d={`M${x(Math.max(0, r.random_mean - r.random_sd))} ${ROW / 2}H${x(r.random_mean + r.random_sd)}`}
                            style={{ stroke: "var(--field-ink-2)", strokeWidth: 1.25 }}
                          />
                          <path d={`M${x(r.random_mean)} ${ROW / 2 - 8}V${ROW / 2 + 8}`} style={{ stroke: "var(--field-ink)", strokeWidth: 2 }} />
                        </g>
                      );
                    })}
                  </g>
                );
              }}
            </ChartFrame>
          </div>
        </div>
      </Figure>

      <details className="more">
        <summary>All {regions.length} neuropils as a table</summary>
        <div className="table-wrap">
          <table className="data">
            <thead>
              <tr>
                <th>Neuropil</th>
                <th>Region</th>
                <th className="num">Types</th>
                <th className="num">Sensory</th>
                <th className="num">Motor</th>
                <th className="num">Flow lost</th>
                <th className="num">Random mean</th>
                <th className="num">Random SD</th>
                <th className="num">p</th>
              </tr>
            </thead>
            <tbody>
              {ranked.map((r) => (
                <tr key={r.neuropil}>
                  <td>
                    <span className="id">{r.neuropil}</span>
                  </td>
                  <td>{describe(r.neuropil) ?? ""}</td>
                  <td className="num">{count(r.types)}</td>
                  <td className="num">{count(r.sensory)}</td>
                  <td className="num">{count(r.motor)}</td>
                  <td className="num">{percent(r.flow_drop)}</td>
                  <td className="num">{percent(r.random_mean)}</td>
                  <td className="num">{percent(r.random_sd)}</td>
                  <td className="num">{pValue(r.p_value)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </details>
    </Finding>
  );
}
