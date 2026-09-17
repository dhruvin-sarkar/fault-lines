import { XAxis, YAxis } from "../Chart.jsx";
import { sentence } from "../../lib/format.js";
import { logTicks } from "../../lib/scales.js";

const CHAR = 6.7;
const LINE = 13;

/** Distributions a power-law fit is tested against, named with their article for running text. */
export const ALTERNATIVES = {
  exponential: "an exponential",
  lognormal: "a lognormal",
  truncated_power_law: "a truncated power law",
};

/** Plain reading of a normalized log-likelihood ratio test of a power law against one alternative. */
export function verdict(comparison, name, significance) {
  if (comparison.p_value >= significance) return `A power law and ${name} cannot be told apart`;
  return comparison.loglikelihood_ratio > 0
    ? `A power law fits better than ${name}`
    : `${sentence(name)} fits better than a power law`;
}

/** Strategy color for marks on paper. */
export const inkColor = (id) => `var(--s-${id}-ink)`;

/** A power of ten set as 10 with a raised exponent. */
export function Pow({ value }) {
  const e = Math.round(Math.log10(value));
  return (
    <>
      10
      <tspan className="fb-exp" dy="-0.55em">
        {e < 0 ? `−${-e}` : e}
      </tspan>
    </>
  );
}

const powLabel = (v) => <Pow value={v} />;

/** Intermediate ticks (2 to 9 times each power of ten) inside a positive domain. */
export function minorTicks([d0, d1]) {
  const out = [];
  for (let e = Math.floor(Math.log10(d0)); e <= Math.ceil(Math.log10(d1)); e += 1) {
    for (let m = 2; m <= 9; m += 1) {
      const v = m * 10 ** e;
      if (v > d0 * 1.0001 && v < d1 * 0.9999) out.push(v);
    }
  }
  return out;
}

/**
 * Log-log axes: gridlines and 10^k labels at each power of ten, short minor ticks between them.
 * `xs` and `ys` are log scales with a `domain`; labels thin out when the plot is too narrow for every decade.
 */
export function LogAxes({ xs, ys, width, height, xTitle, yTitle }) {
  const xMajor = logTicks(xs.domain);
  const yMajor = logTicks(ys.domain);
  const room = width / Math.max(1, xMajor.length - 1);
  const every = room < 30 ? 2 : 1;
  const xLabels = xMajor.filter((_, i) => i % every === 0 || i === xMajor.length - 1);
  return (
    <g>
      {xMajor.map((t) => (
        <line key={t} className="fb-grid" x1={xs(t)} x2={xs(t)} y1={0} y2={height} />
      ))}
      <YAxis scale={ys} ticks={yMajor} width={width} format={powLabel} title={yTitle} />
      <XAxis scale={xs} ticks={xLabels} height={height} width={width} format={powLabel} title={xTitle} />
      {xMajor.map((t) => (
        <line key={t} className="fb-tick" x1={xs(t)} x2={xs(t)} y1={height} y2={height + 6} />
      ))}
      {minorTicks(xs.domain).map((t) => (
        <line key={t} className="fb-tick" x1={xs(t)} x2={xs(t)} y1={height} y2={height + 3} />
      ))}
      <line className="fb-tick" x1={0} x2={0} y1={0} y2={height} />
      {yMajor.map((t) => (
        <line key={t} className="fb-tick" x1={-6} x2={0} y1={ys(t)} y2={ys(t)} />
      ))}
      {minorTicks(ys.domain).map((t) => (
        <line key={t} className="fb-tick" x1={-3} x2={0} y1={ys(t)} y2={ys(t)} />
      ))}
    </g>
  );
}

/** A label split over two lines at the space nearest its middle, for narrow plots. */
function lines(label, narrow) {
  if (!narrow || label.length <= 13 || !label.includes(" ")) return [label];
  const mid = label.length / 2;
  let cut = -1;
  for (let i = 0; i < label.length; i += 1) {
    if (label[i] === " " && (cut < 0 || Math.abs(i - mid) < Math.abs(cut - mid))) cut = i;
  }
  return [label.slice(0, cut), label.slice(cut + 1)];
}

/**
 * Label positions at least `gap` apart inside [lo, hi], moving each as little as the others allow. `gap` is a number
 * or a function of two neighbouring items, for labels of different heights.
 */
export function spread(items, gap, lo, hi) {
  const between = typeof gap === "function" ? gap : () => gap;
  const sorted = [...items].sort((a, b) => a.y - b.y);
  sorted.forEach((item) => (item.y = Math.max(lo, Math.min(hi, item.y))));
  for (let i = 1; i < sorted.length; i += 1) {
    sorted[i].y = Math.max(sorted[i].y, sorted[i - 1].y + between(sorted[i - 1], sorted[i]));
  }
  const n = sorted.length;
  if (n && sorted[n - 1].y > hi) {
    sorted[n - 1].y = hi;
    for (let i = n - 2; i >= 0; i -= 1) sorted[i].y = Math.min(sorted[i].y, sorted[i + 1].y - between(sorted[i], sorted[i + 1]));
  }
  return sorted;
}

/** Right margin that fits the direct labels of `labels`. */
export function labelRoom(labels, narrow) {
  const longest = Math.max(0, ...labels.flatMap((l) => lines(l, narrow).map((s) => s.length)));
  return Math.ceil(longest * CHAR) + 30;
}

/**
 * Labels at the right end of lines, nudged apart and joined to their line by a short leader.
 * Each item is { id, label, y, stroke, dash }, with `y` the line's last value in pixels.
 */
export function LineLabels({ items, width, height, narrow = false, dim }) {
  // Centers sit half of each label's height apart plus clear space; two-line labels need more room than one-line ones.
  const extent = (item) => (item.parts.length - 1) * LINE + 12;
  const placed = spread(
    items.map((item) => ({ ...item, end: item.y, parts: lines(item.label, narrow) })),
    (a, b) => (extent(a) + extent(b)) / 2 + (narrow ? 7 : 4),
    0,
    height,
  );
  return (
    <g>
      {placed.map((item) => {
        const { parts } = item;
        return (
          <g key={item.id} style={{ opacity: dim?.(item.id) ?? 1 }}>
            <path className="fb-leader" d={`M${width + 2} ${item.end}L${width + 8} ${item.y}`} />
            <line
              x1={width + 8}
              x2={width + 18}
              y1={item.y}
              y2={item.y}
              style={{ stroke: item.stroke, strokeWidth: 2, strokeDasharray: item.dash }}
            />
            <text className="direct-label" x={width + 22} y={item.y - ((parts.length - 1) * LINE) / 2}>
              {parts.map((part, i) => (
                <tspan key={part} x={width + 22} dy={i ? LINE : "0.32em"}>
                  {part}
                </tspan>
              ))}
            </text>
          </g>
        );
      })}
    </g>
  );
}

/**
 * Approximate rendered width of a chart label in Archivo at `size` pixels: figures are tabular and wide, spaces and
 * punctuation narrow. `bold` is for the semibold label weight.
 */
export function labelWidth(text, size = 12, bold = true) {
  let em = 0;
  for (const ch of text) {
    if (/[0-9%]/.test(ch)) em += 0.6;
    else if (/[\s.,:;]/.test(ch)) em += 0.27;
    else em += bold ? 0.52 : 0.47;
  }
  return em * size;
}

/** True when the segment from a to b passes through the box { x0, y0, x1, y1 }. */
function crosses([ax, ay], [bx, by], box) {
  let t0 = 0;
  let t1 = 1;
  const dx = bx - ax;
  const dy = by - ay;
  const edges = [
    [-dx, ax - box.x0],
    [dx, box.x1 - ax],
    [-dy, ay - box.y0],
    [dy, box.y1 - ay],
  ];
  for (const [p, q] of edges) {
    if (p === 0) {
      if (q < 0) return false;
    } else {
      const t = q / p;
      if (p < 0) t0 = Math.max(t0, t);
      else t1 = Math.min(t1, t);
      if (t0 > t1) return false;
    }
  }
  return true;
}

/**
 * Chooses where a point label goes. `text` is a string or an array of lines set `leading` apart. Each candidate is
 * { x, y, anchor } with `y` the first baseline; the first one that no polyline in `lines`, no box in `taken` and no
 * chart edge (`bounds`) touches wins, otherwise the one touched least. Returns the candidate with its `box`, `score`
 * and `clear`, which is false when something still touches it and the label needs a halo.
 */
export function placeLabel(text, candidates, { lines = [], taken = [], bounds, size = 12, bold = true, pad = 3, leading = 14 }) {
  const rows = Array.isArray(text) ? text : [text];
  const w = Math.max(...rows.map((row) => labelWidth(row, size, bold)));
  let best = null;
  for (const candidate of candidates) {
    const left = candidate.anchor === "end" ? candidate.x - w : candidate.anchor === "middle" ? candidate.x - w / 2 : candidate.x;
    const box = {
      x0: left - pad,
      x1: left + w + pad,
      y0: candidate.y - size * 0.8 - pad,
      y1: candidate.y + (rows.length - 1) * leading + size * 0.2 + pad,
    };
    let hits = 0;
    for (const points of lines) {
      for (let i = 1; i < points.length; i += 1) {
        if (crosses(points[i - 1], points[i], box)) {
          hits += 1;
          break;
        }
      }
    }
    const overlaps = taken.filter((t) => t.x0 < box.x1 && box.x0 < t.x1 && t.y0 < box.y1 && box.y0 < t.y1).length;
    const outside = bounds && (box.x0 < bounds.x0 || box.x1 > bounds.x1 || box.y0 < bounds.y0 || box.y1 > bounds.y1) ? 1 : 0;
    const score = overlaps * 100 + outside * 10 + hits;
    if (!best || score < best.score) best = { ...candidate, box, score, clear: score === 0 };
    if (score === 0) break;
  }
  return best;
}

/** Candidate spots around a point, nearest corners first in the given order of sides. */
export function around(x, y, { dx = 8, above = 9, below = 17, order = ["below-left", "above-left", "below-right", "above-right"] } = {}) {
  const spots = {
    "below-left": { x: x - dx, y: y + below, anchor: "end" },
    "above-left": { x: x - dx, y: y - above, anchor: "end" },
    "below-right": { x: x + dx, y: y + below, anchor: "start" },
    "above-right": { x: x + dx, y: y - above, anchor: "start" },
  };
  return order.map((side) => spots[side]);
}

/** Ticks for a removal-fraction axis that runs to about one half. */
export function xTicks(max, narrow) {
  const step = narrow ? 0.25 : 0.1;
  return Array.from({ length: Math.floor(max / step + 1e-9) + 1 }, (_, i) => Number((i * step).toFixed(2)));
}

/** "p = value" with very small values as a power of ten; a p that underflowed to zero reads as below 10^-323. */
export function PValue({ p }) {
  if (p == null) return "p not available";
  if (p === 0) {
    return (
      <>
        p &lt; 10<sup className="fb-sup">−323</sup>
      </>
    );
  }
  if (p >= 0.001) return `p = ${p < 0.01 ? p.toFixed(3) : p.toFixed(2)}`;
  const [mantissa, exponent] = p.toExponential(1).split("e");
  return (
    <>
      p = {mantissa} × 10<sup className="fb-sup">{`−${Math.abs(Number(exponent))}`}</sup>
    </>
  );
}
