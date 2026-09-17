import { useLayoutEffect, useRef, useState } from "react";
import { useWidth } from "../lib/hooks.js";

export const MARGIN = { top: 32, right: 18, bottom: 46, left: 54 };

/**
 * Responsive SVG chart. `children` receives the inner plotting size; `onPointer` receives pointer
 * coordinates inside the plotting area so charts can drive a crosshair or pick the nearest mark.
 * Nothing is drawn until the container has been measured. Interactive charts pass `role="group"`.
 */
export function ChartFrame({ height = 360, margin = MARGIN, label, children, overlay, onPointer, onLeave, role = "img" }) {
  const [ref, width] = useWidth();
  const svgRef = useRef(null);
  const inner = { width: Math.max(10, width - margin.left - margin.right), height: height - margin.top - margin.bottom };

  function handle(event) {
    if (!onPointer || !svgRef.current) return;
    const rect = svgRef.current.getBoundingClientRect();
    onPointer(event.clientX - rect.left - margin.left, event.clientY - rect.top - margin.top, inner);
  }

  if (!width) return <div className="chart" ref={ref} style={{ height }} />;

  return (
    <div className="chart" ref={ref}>
      <svg
        ref={svgRef}
        width={width}
        height={height}
        role={role}
        aria-label={label}
        onPointerMove={handle}
        onPointerDown={handle}
        onPointerLeave={onLeave}
      >
        <g transform={`translate(${margin.left},${margin.top})`}>{children(inner)}</g>
      </svg>
      {overlay?.({ ...inner, margin, width })}
    </div>
  );
}

/** Value axis with light gridlines; the title sits horizontally above the top tick, read before the data. */
export function YAxis({ scale, ticks, width, format = String, title, grid = true, inset = 46 }) {
  return (
    <g>
      {ticks.map((t) => (
        <g key={t} className="tick" transform={`translate(0,${scale(t)})`}>
          {grid && <line x2={width} />}
          <text x={-10} dy="0.32em" textAnchor="end">
            {format(t)}
          </text>
        </g>
      ))}
      {title && (
        <text className="axis-title" x={-inset} y={Math.min(...ticks.map((t) => scale(t))) - 16} textAnchor="start">
          {title}
        </text>
      )}
    </g>
  );
}

export function XAxis({ scale, ticks, height, format = String, title, width }) {
  return (
    <g transform={`translate(0,${height})`}>
      <line className="axis-line" x2={width} />
      {ticks.map((t) => (
        <text key={t} x={scale(t)} y={20} textAnchor="middle">
          {format(t)}
        </text>
      ))}
      {title && (
        <text className="axis-title" x={width} y={40} textAnchor="end">
          {title}
        </text>
      )}
    </g>
  );
}

/**
 * Readout anchored above a point in the chart's pixel space; it takes the field styling inside a black figure.
 * It measures its rendered box and shifts sideways to stay 4px inside `width`, whatever transform a stylesheet
 * gives it, and drops below the point when there is no room above. `clamp={false}` turns both off.
 * It is hidden from assistive technology, so its values must also be reachable another way.
 */
export function Tooltip({ x, y, width, children, clamp = true }) {
  const ref = useRef(null);
  const [fit, setFit] = useState({ shift: 0, h: 0 });

  useLayoutEffect(() => {
    const node = ref.current;
    const parent = node?.offsetParent;
    if (!clamp || !node || !parent) return;
    const box = node.getBoundingClientRect();
    const frame = parent.getBoundingClientRect();
    const room = width ?? frame.width;
    // Position the box would have with no shift, so the correction does not feed back on itself.
    const natural = box.left - frame.left - fit.shift;
    const target = box.width + 8 > room ? (room - box.width) / 2 : Math.max(4, Math.min(room - 4 - box.width, natural));
    const shift = Math.round(target - natural);
    const h = Math.round(box.height);
    if (shift !== fit.shift || h !== fit.h) setFit({ shift, h });
  });

  const below = clamp && fit.h > 0 && y - fit.h - 12 < 0;
  return (
    <div
      ref={ref}
      className={`tooltip${below ? " is-below" : ""}`}
      style={{ left: x + (clamp ? fit.shift : 0), top: y }}
      aria-hidden="true"
    >
      {children}
    </div>
  );
}

export function Row({ label, value, color }) {
  return (
    <div className="row">
      <span>
        {color && <span className="swatch" style={{ background: color, display: "inline-block", marginRight: 6 }} />}
        {label}
      </span>
      <strong>{value}</strong>
    </div>
  );
}

/** Direct labels placed at the right end of lines, nudged apart so they never overlap. */
export function spreadLabels(items, minGap = 15, lo = 0, hi = Infinity) {
  const sorted = [...items].sort((a, b) => a.y - b.y);
  for (let i = 1; i < sorted.length; i += 1) {
    if (sorted[i].y - sorted[i - 1].y < minGap) sorted[i].y = sorted[i - 1].y + minGap;
  }
  const overflow = sorted.length ? sorted[sorted.length - 1].y - hi : 0;
  if (overflow > 0) sorted.forEach((item) => (item.y -= overflow));
  for (let i = sorted.length - 2; i >= 0; i -= 1) {
    if (sorted[i + 1].y - sorted[i].y < minGap) sorted[i].y = sorted[i + 1].y - minGap;
  }
  sorted.forEach((item) => (item.y = Math.max(lo, item.y)));
  return sorted;
}
