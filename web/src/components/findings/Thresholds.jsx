import { useEffect, useMemo, useState } from "react";
import { Finding } from "./Finding.jsx";
import { inkColor as ink } from "./marks.jsx";
import { useRovingRows } from "./useRovingRows.js";
import { ChartFrame, Row, Tooltip } from "../Chart.jsx";
import { Figure, Sidenote, TextBlock } from "../ui.jsx";
import { useData } from "../../lib/data.js";
import { useWidth } from "../../lib/hooks.js";
import { log } from "../../lib/scales.js";
import { percent, sentence } from "../../lib/format.js";
import "../../styles/findings-a.css";

const TICKS = [0.02, 0.05, 0.1, 0.2, 0.5, 1];
const DOMAIN = [0.02, 1];
const LABEL_FONT = '500 12px "Archivo Variable", "Segoe UI", system-ui, sans-serif';
const SUB_FONT = '400 11px "Archivo Variable", "Segoe UI", system-ui, sans-serif';

const GROUPS = [
  ["this study", "This connectome: flow capacity halved"],
  ["published, targeted", "Published networks, targeted removal"],
  ["published, random", "Published networks, random removal"],
];

const tickLabel = (t) => `${Math.round(t * 100)}%`;

/** A study value as printed: our thresholds to one decimal, published ones without invented precision. */
const shown = (row) =>
  `${row.qualifier === "=" ? "" : `${row.qualifier} `}${row.strategy ? percent(row.value) : `${+(row.value * 100).toFixed(1)}%`}`;

const spoken = (row) => shown(row).replace("≈ ", "roughly ").replace("> ", "more than ");

/** A published network's name without its size or qualifier, for running text. */
const shortName = (row) => row.network.split(/[,(]/)[0].trim();

let measurer;
function textWidth(text, font) {
  measurer ??= document.createElement("canvas").getContext("2d");
  measurer.font = font;
  return measurer.measureText(text).width;
}

function buildRows(meta, percolation, comparison) {
  const ownRows = meta.strategies
    .map((s) => {
      const result = percolation.strategies[s.id];
      const listed = comparison.find((c) => c.group === "this study" && c.network.endsWith(s.label));
      return {
        key: s.id,
        group: "this study",
        name: sentence(s.label),
        label: s.label,
        strategy: s.id,
        value: result.critical_fraction,
        ci: result.critical_fraction_ci95 ?? null,
        qualifier: "=",
        removal: s.id === "random" ? `random, mean of ${result.trials} trials` : listed?.removal ?? "targeted",
        criterion: listed?.criterion ?? "sensory-to-motor flow capacity halved",
        citation: "this study",
      };
    })
    .sort((a, b) => a.value - b.value);
  const others = comparison
    .filter((c) => c.group !== "this study")
    .map((c, i) => ({ ...c, name: c.network, key: `p${i}` }))
    .sort((a, b) => a.value - b.value);
  return [...ownRows, ...others];
}

function Marker({ row, x }) {
  if (row.strategy === "random") {
    return <path d={`M${x} -6.5L${x + 6.5} 0L${x} 6.5L${x - 6.5} 0Z`} className="fa-diamond" style={{ stroke: ink("random") }} />;
  }
  if (row.strategy) return <circle cx={x} r={5} style={{ fill: ink(row.strategy) }} />;
  if (row.qualifier === ">") return <path d={`M${x - 5} -5.5L${x + 6} 0L${x - 5} 5.5Z`} className="fa-glyph-fill" />;
  if (row.qualifier === "≈") return <circle cx={x} r={4.5} className="fa-ring" style={{ stroke: "var(--ink-2)" }} />;
  return <circle cx={x} r={5} className="fa-glyph-fill" />;
}

export default function Thresholds({ meta, percolation }) {
  const { data: comparison } = useData("comparison.json");
  const [wrapRef, width] = useWidth();
  const [active, setActive] = useState(null);
  const [fontsReady, setFontsReady] = useState(0);

  useEffect(() => {
    let live = true;
    document.fonts?.ready.then(() => live && setFontsReady((n) => n + 1));
    return () => {
      live = false;
    };
  }, []);

  const rows = useMemo(() => buildRows(meta, percolation, comparison ?? []), [meta, percolation, comparison]);
  const targeted = rows.filter((r) => r.strategy && r.strategy !== "random");
  const random = rows.find((r) => r.strategy === "random");
  const worst = targeted[0];
  const allBelow = targeted.every((r) => r.value < random.ci[0]);
  const published = rows.filter((r) => !r.strategy);
  const hubs = published.filter((r) => r.group === "published, targeted");
  const brain = published.filter((r) => /brain/i.test(r.network)).at(-1);
  const closeToWorst = hubs.filter((r) => Math.abs(r.value - worst.value) <= 0.03);

  // Row labels sit in a left column wide enough for the longest label; if that column would crowd the plot,
  // labels move above their rows instead.
  const labelColumn = useMemo(() => {
    let widest = 0;
    for (const r of rows) {
      widest = Math.max(widest, textWidth(r.name, LABEL_FONT));
      if (!r.strategy) widest = Math.max(widest, textWidth(`${r.criterion}; ${r.citation}`, SUB_FONT));
    }
    return Math.ceil(widest * 1.04) + 28;
  }, [rows, fontsReady]);
  const wide = width >= 700 && labelColumn <= width * 0.5;
  const margin = { top: 30, right: 56, bottom: 46, left: wide ? labelColumn : 4 };

  const layout = useMemo(() => {
    const out = [];
    let y = 0;
    for (const [group, title] of GROUPS) {
      const members = rows.filter((r) => r.group === group);
      if (!members.length) continue;
      y += out.length ? 20 : 2;
      out.push({ kind: "title", key: group, title, y: y + 12 });
      y += 24;
      for (const row of members) {
        const own = Boolean(row.strategy);
        const h = wide ? (own ? 30 : 40) : own ? 42 : 56;
        out.push({ kind: "row", key: row.key, row, top: y, h, y: wide ? y + h / 2 : y + h - 12 });
        y += h;
      }
    }
    return { items: out, height: y + 6 };
  }, [rows, wide]);

  const rowItems = layout.items.filter((item) => item.kind === "row");
  const rowProps = useRovingRows(
    rowItems.map((item) => item.key),
    setActive,
  );
  const height = layout.height + margin.top + margin.bottom;
  const activeItem = rowItems.find((item) => item.key === active);

  return (
    <Finding
      id="thresholds"
      title="How little it takes"
      stat={percent(worst.value)}
      statLabel={`of cell types removed by ${worst.label} halves sensory-to-motor flow capacity`}
    >
      <TextBlock
        notes={
          <Sidenote title="Not the same yardstick">
            Most published thresholds track the largest connected cluster on undirected graphs, often with a ranking
            fixed on the intact network. A source-to-sink capacity can halve long before such a cluster breaks up.
          </Sidenote>
        }
      >
        <p>
          Removing cell types in order of {worst.label} halves flow capacity once {percent(worst.value)} of types are
          gone. Removing them at random takes {percent(random.value)} (95% CI {percent(random.ci[0])} to {percent(random.ci[1])}).{" "}
          {allBelow
            ? "Every targeted strategy crosses the halfway point before the lower end of that interval."
            : "Not every targeted strategy crosses the halfway point before the lower end of that interval."}
        </p>
        {hubs.length > 0 && (
          <p>
            {closeToWorst.length > 0
              ? `That is the range published for engineered networks under hub attack: ${closeToWorst
                  .map((r) => `${shortName(r)}, ${spoken(r)} (${r.citation})`)
                  .join("; ")}.`
              : `Published thresholds under hub attack range from ${spoken(hubs[0])} to ${spoken(hubs[hubs.length - 1])}.`}
            {brain && ` ${shortName(brain)}s hold out far longer, to ${spoken(brain)} (${brain.citation}).`}{" "}
            The criteria differ, so the comparison supports a qualitative reading only.
          </p>
        )}
      </TextBlock>

      <Figure
        title="Fraction of nodes removed at breakdown, on a logarithmic axis"
        caption={
          <>
            Each row is one network and one removal order; its mark sits at the fraction of nodes removed when that
            study judged the network broken. Colored marks are this connectome, where breakdown means flow capacity
            falls below half its intact value; random removal is the open diamond, with capped whiskers for the 95%
            confidence interval over {random.removal.match(/\d+/)?.[0] ?? "the"} trials. Gray marks are published
            values: filled where the source prints a value, open where it gives an approximate one, and a triangle for
            a lower bound. The breakdown criterion is printed under each published network. Hover a row, or focus the
            chart and use the arrow keys, for its source.
          </>
        }
      >
        <div className="legend fa-legend" aria-hidden="true">
          <span>
            <svg width="12" height="12" viewBox="-6 -6 12 12">
              <circle r="5" className="fa-glyph-fill" />
            </svg>
            Value as printed
          </span>
          <span>
            <svg width="12" height="12" viewBox="-6 -6 12 12">
              <circle r="4.5" className="fa-glyph-ring" />
            </svg>
            Approximate value
          </span>
          <span>
            <svg width="12" height="12" viewBox="-6 -6 12 12">
              <path d="M-5 -5.5L6 0L-5 5.5Z" className="fa-glyph-fill" />
            </svg>
            Lower bound
          </span>
          <span>
            <svg width="22" height="16" viewBox="-11 -8 22 16">
              <path d="M-9 0H9M-9 -6V6M9 -6V6" style={{ stroke: ink("random"), strokeWidth: 1.5, fill: "none" }} />
              <path d="M0 -6L6 0L0 6L-6 0Z" className="fa-diamond" style={{ stroke: ink("random") }} />
            </svg>
            Random removal, 95% CI
          </span>
        </div>
        <div ref={wrapRef}>
          <ChartFrame
            height={height}
            margin={margin}
            role="group"
            label={`Fraction of nodes removed at breakdown for ${targeted.length + 1} removal orders on this connectome and ${published.length} published networks, on a logarithmic axis. Use the arrow keys to move between rows.`}
            onPointer={(x, y) => {
              const hit = rowItems.find((item) => y >= item.top && y < item.top + item.h);
              setActive(hit ? hit.key : null);
            }}
            onLeave={() => setActive(null)}
            overlay={({ margin: m, width: w }) => {
              if (!activeItem) return null;
              const { row } = activeItem;
              const scale = log(DOMAIN, [0, w - m.left - m.right]);
              return (
                <Tooltip x={m.left + scale(row.value)} y={m.top + activeItem.y - 10} width={w}>
                  <div className="fa-tip">
                    <strong>{row.network ?? `Male CNS cell types, ${row.label}`}</strong>
                    <span className="fa-tip-sub">{sentence(row.removal)}</span>
                    <Row label="Removed at breakdown" value={shown(row)} />
                    {row.ci && <Row label="95% CI" value={`${percent(row.ci[0])} to ${percent(row.ci[1])}`} />}
                    <span className="fa-tip-sub">Criterion: {row.criterion}</span>
                    <span className="fa-tip-sub">
                      {row.citation === "this study" ? "This study" : `${row.citation}, ${row.location}`}
                    </span>
                  </div>
                </Tooltip>
              );
            }}
          >
            {(inner) => {
              const x = log(DOMAIN, [0, inner.width]);
              const labelX = -margin.left;
              return (
                <g>
                  {TICKS.map((t) => (
                    <g key={t} className="tick" transform={`translate(${x(t)},0)`}>
                      <line y1={-4} y2={inner.height} />
                      <text y={-12} textAnchor="middle">
                        {tickLabel(t)}
                      </text>
                    </g>
                  ))}
                  <g transform={`translate(0,${inner.height})`}>
                    <line className="axis-line" x2={inner.width} />
                    {TICKS.map((t) => (
                      <g key={t} transform={`translate(${x(t)},0)`}>
                        <line className="fa-axis-tick" y2={5} />
                        <text y={18} textAnchor="middle">
                          {tickLabel(t)}
                        </text>
                      </g>
                    ))}
                    <text className="axis-title" x={inner.width} y={38} textAnchor="end">
                      Nodes removed at breakdown
                    </text>
                  </g>

                  {activeItem && (
                    <line className="fa-guide" x1={x(activeItem.row.value)} x2={x(activeItem.row.value)} y1={-4} y2={inner.height} />
                  )}

                  {layout.items.map((item) => {
                    if (item.kind === "title") {
                      return (
                        <text key={item.key} className="fa-group-title" x={labelX} y={item.y}>
                          {item.title}
                        </text>
                      );
                    }
                    const { row } = item;
                    const own = Boolean(row.strategy);
                    const cx = x(row.value);
                    const valueX = row.ci ? Math.max(x(row.ci[1]), cx + 6) : cx;
                    const nearEdge = valueX > inner.width - 20;
                    const nameY = wide ? item.top + item.h / 2 + (own ? 4 : -3) : item.y + (own ? -15 : -30);
                    const subY = wide ? item.top + item.h / 2 + 11 : item.y - 16;
                    return (
                      <g
                        key={item.key}
                        {...rowProps(item.key)}
                        role="img"
                        aria-label={`${row.name}: ${shown(row)}; ${row.criterion}; ${row.citation}`}
                      >
                        <rect
                          className={`fa-band${active === item.key ? " is-on" : ""}`}
                          x={labelX - 6}
                          width={inner.width + margin.left + margin.right + 6}
                          y={item.top + 1}
                          height={item.h - 2}
                          rx={3}
                        />
                        <g transform={`translate(0,${item.y})`}>
                          <line className="fa-track" x1={0} x2={inner.width} />
                          {row.ci && (
                            <path
                              d={`M${x(row.ci[0])} 0H${x(row.ci[1])}M${x(row.ci[0])} -8V8M${x(row.ci[1])} -8V8`}
                              style={{ stroke: ink(row.strategy), strokeWidth: 1.5, fill: "none" }}
                            />
                          )}
                          <Marker row={row} x={cx} />
                          <text className="fa-value" x={nearEdge ? cx - 11 : valueX + 11} y={4} textAnchor={nearEdge ? "end" : "start"}>
                            {shown(row)}
                          </text>
                        </g>
                        <text className="fa-row-label" x={labelX} y={nameY}>
                          {row.name}
                        </text>
                        {!own && (
                          <text className="fa-row-sub" x={labelX} y={subY}>
                            {sentence(row.criterion)}; {row.citation}
                          </text>
                        )}
                      </g>
                    );
                  })}
                </g>
              );
            }}
          </ChartFrame>
        </div>
      </Figure>

      <details className="more">
        <summary>Thresholds as a table</summary>
        <div className="table-wrap">
          <table className="data">
            <thead>
              <tr>
                <th>Network</th>
                <th>Removal</th>
                <th>Breakdown criterion</th>
                <th className="num">Nodes removed</th>
                <th>Source</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((row) => (
                <tr key={row.key}>
                  <td>{row.network ?? `Male CNS cell types, ${row.label}`}</td>
                  <td>{sentence(row.removal)}</td>
                  <td>{sentence(row.criterion)}</td>
                  <td className="num">
                    {shown(row)}
                    {row.ci && ` (95% CI ${percent(row.ci[0])} to ${percent(row.ci[1])})`}
                  </td>
                  <td>{row.citation === "this study" ? "This study" : `${row.citation}, ${row.location}`}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </details>
    </Finding>
  );
}
