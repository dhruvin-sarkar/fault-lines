import { useEffect, useMemo, useRef, useState } from "react";
import { useTokens } from "../lib/hooks.js";

const TOKENS = ["ink", "muted", "signal", "signal-glow", "tissue", "tissue-edge",
  "field-ink", "field-ink-3", "field-rule", "field-tissue", "field-ghost", "field-live"];

/** Color of intact cell types on the field, for legends drawn outside the canvas; equal to --field-live. */
export const FIELD_LIVE = "#b9dcff";

/*
 * Paper tone draws ink on tissue. Field tone draws the atlas as a fluorescence image: dark tissue, and points
 * blended additively so dense regions brighten the way a stained sample does.
 */
function palette(colors, tone) {
  if (tone === "field") {
    return { tissue: colors["field-tissue"], edge: colors["field-rule"], active: colors["field-ink"],
      live: colors["field-live"] || FIELD_LIVE, ghost: colors["field-ghost"], silent: colors["field-ink-3"],
      signal: colors["signal-glow"], blend: "lighter" };
  }
  return { tissue: colors.tissue, edge: colors["tissue-edge"], active: colors.ink, live: colors.ink,
    ghost: colors["tissue-edge"], silent: colors.muted, signal: colors.signal, blend: "source-over" };
}

function parsePaths(outlines) {
  return outlines.map((o) => ({ ...o, path2d: new Path2D(o.path) }));
}

function bounds(types, outlinePath) {
  const numbers = outlinePath.match(/-?\d+(\.\d+)?/g).map(Number);
  let x0 = Infinity;
  let x1 = -Infinity;
  let y0 = Infinity;
  let y1 = -Infinity;
  for (let i = 0; i < numbers.length; i += 2) {
    x0 = Math.min(x0, numbers[i]);
    x1 = Math.max(x1, numbers[i]);
    y0 = Math.min(y0, numbers[i + 1]);
    y1 = Math.max(y1, numbers[i + 1]);
  }
  for (let i = 0; i < types.x.length; i += 1) {
    if (types.x[i] == null) continue;
    x0 = Math.min(x0, types.x[i]);
    x1 = Math.max(x1, types.x[i]);
    y0 = Math.min(y0, types.y[i]);
    y1 = Math.max(y1, types.y[i]);
  }
  return { x0: x0 - 8, y0: y0 - 8, w: x1 - x0 + 16, h: y1 - y0 + 16 };
}

/** Aspect ratio (width / height) of the drawn atlas, for sizing its container. */
export function atlasAspect(types, atlas) {
  const b = bounds(types, atlas.cns_outline);
  return b.w / b.h;
}

/**
 * The male CNS drawn as neuropil outlines with one point per cell type, on canvas.
 *
 * Point state comes from `removedAt` / `silencedAt` batch arrays and the current `batch`; `regionFill`
 * turns the outlines into a choropleth; `highlight` (a set of type indices) and `focus` (one index)
 * pick out types; `tone` is "paper" or "field"; `ghostAlpha`, `silentColor` and `silentAlpha` set how removed and
 * cut-off types are drawn; `highlightTone` "neutral" draws highlighted and focused types in ink instead of the signal red;
 * `onRegion` and `onType` report what the pointer is over.
 */
export default function Atlas({
  types,
  atlas,
  batch = 0,
  removedAt,
  silencedAt,
  regionFill,
  activeRegion,
  highlight,
  focus,
  pointAlpha,
  ghostAlpha = 0.9,
  silentColor,
  silentAlpha = 0.55,
  highlightTone = "signal",
  tone = "paper",
  onRegion,
  onType,
  label,
  className = "",
  style,
}) {
  const box = useRef(null);
  const canvas = useRef(null);
  const [size, setSize] = useState({ w: 0, h: 0 });
  const colors = useTokens(TOKENS);
  const outlines = useMemo(() => parsePaths(atlas.outlines), [atlas]);
  const extent = useMemo(() => bounds(types, atlas.cns_outline), [types, atlas]);
  const hitContext = useMemo(() => document.createElement("canvas").getContext("2d"), []);
  const frame = useRef({ scale: 1, ox: 0, oy: 0 });

  useEffect(() => {
    const node = box.current;
    const observer = new ResizeObserver(([entry]) => {
      setSize({ w: entry.contentRect.width, h: entry.contentRect.height });
    });
    observer.observe(node);
    return () => observer.disconnect();
  }, []);

  useEffect(() => {
    const el = canvas.current;
    if (!el || !size.w || !size.h || !colors.ink) return;
    const dpr = Math.min(window.devicePixelRatio || 1, 2);
    el.width = Math.round(size.w * dpr);
    el.height = Math.round(size.h * dpr);
    el.style.width = `${size.w}px`;
    el.style.height = `${size.h}px`;
    const ctx = el.getContext("2d");
    const scale = Math.min(size.w / extent.w, size.h / extent.h);
    const ox = (size.w - extent.w * scale) / 2 - extent.x0 * scale;
    const oy = (size.h - extent.h * scale) / 2 - extent.y0 * scale;
    frame.current = { scale, ox, oy };
    const ink = palette(colors, tone);
    const liveAlpha = pointAlpha ?? (tone === "field" ? 0.42 : 0.7);

    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    ctx.clearRect(0, 0, size.w, size.h);
    ctx.save();
    ctx.translate(ox, oy);
    ctx.scale(scale, scale);
    ctx.lineJoin = "round";
    for (const region of outlines) {
      const fill = regionFill?.(region);
      ctx.fillStyle = fill ?? ink.tissue;
      ctx.globalAlpha = fill ? 1 : 0.9;
      ctx.fill(region.path2d, "evenodd");
      ctx.globalAlpha = 1;
      ctx.lineWidth = (region.neuropil === activeRegion ? 2.2 : 0.7) / scale;
      ctx.strokeStyle = region.neuropil === activeRegion ? ink.active : ink.edge;
      ctx.stroke(region.path2d);
    }
    ctx.restore();

    const r = Math.max(1.1, Math.min(2.6, scale * 2.1));
    const px = (i) => ox + types.x[i] * scale;
    const py = (i) => oy + types.y[i] * scale;
    const n = types.x.length;
    const dimmed = highlight && highlight.size > 0;

    const groups = { live: [], silent: [], ghost: [], fresh: [], hot: [] };
    for (let i = 0; i < n; i += 1) {
      if (types.x[i] == null) continue;
      const removed = removedAt ? removedAt[i] : -1;
      if (removed > 0 && removed < batch) groups.ghost.push(i);
      else if (removed > 0 && removed === batch) groups.fresh.push(i);
      else if (silencedAt && silencedAt[i] >= 0 && silencedAt[i] <= batch && batch > 0) groups.silent.push(i);
      else if (dimmed && highlight.has(i)) groups.hot.push(i);
      else groups.live.push(i);
    }

    const paint = (list, color, alpha, size) => {
      ctx.globalAlpha = alpha;
      ctx.fillStyle = color;
      const half = size / 2;
      for (const i of list) ctx.fillRect(px(i) - half, py(i) - half, size, size);
    };
    if (ghostAlpha > 0) paint(groups.ghost, ink.ghost, ghostAlpha, r * 0.8);
    ctx.globalCompositeOperation = ink.blend;
    paint(groups.live, ink.live, dimmed ? liveAlpha * 0.25 : liveAlpha, r);
    ctx.globalCompositeOperation = "source-over";
    paint(groups.silent, silentColor ?? ink.silent, silentAlpha, r * 0.85);
    ctx.globalCompositeOperation = ink.blend;
    const mark = highlightTone === "neutral" ? ink.active : ink.signal;
    paint(groups.hot, mark, 0.95, r * 1.35);
    paint(groups.fresh, ink.signal, 1, r * 1.9);
    ctx.globalCompositeOperation = "source-over";
    ctx.globalAlpha = 1;

    if (focus != null && types.x[focus] != null) {
      ctx.strokeStyle = mark;
      ctx.lineWidth = 2;
      ctx.beginPath();
      ctx.arc(px(focus), py(focus), 9, 0, Math.PI * 2);
      ctx.stroke();
      ctx.fillStyle = mark;
      ctx.fillRect(px(focus) - r, py(focus) - r, r * 2, r * 2);
    }
  }, [size, colors, outlines, extent, types, batch, removedAt, silencedAt, regionFill, activeRegion, highlight, focus, pointAlpha, ghostAlpha, silentColor, silentAlpha, highlightTone, tone]);

  function pointer(event) {
    if (!onRegion && !onType) return;
    const rect = canvas.current.getBoundingClientRect();
    const { scale, ox, oy } = frame.current;
    const ax = (event.clientX - rect.left - ox) / scale;
    const ay = (event.clientY - rect.top - oy) / scale;
    if (onType) {
      let best = null;
      let bestDistance = (8 / scale) ** 2;
      for (let i = 0; i < types.x.length; i += 1) {
        if (types.x[i] == null) continue;
        const d = (types.x[i] - ax) ** 2 + (types.y[i] - ay) ** 2;
        if (d < bestDistance) {
          bestDistance = d;
          best = i;
        }
      }
      onType(best, event);
    }
    if (onRegion) {
      let hit = null;
      for (let k = outlines.length - 1; k >= 0; k -= 1) {
        if (hitContext.isPointInPath(outlines[k].path2d, ax, ay, "evenodd")) {
          hit = outlines[k];
          break;
        }
      }
      onRegion(hit, event);
    }
  }

  return (
    <div ref={box} className={className} style={{ position: "relative", width: "100%", height: style?.aspectRatio ? "auto" : "100%", ...style }}>
      <canvas
        ref={canvas}
        role="img"
        aria-label={label}
        onPointerMove={pointer}
        onPointerDown={pointer}
        onPointerLeave={() => {
          onRegion?.(null);
          onType?.(null);
        }}
      />
    </div>
  );
}
