/** Linear scale from a data domain to a pixel range, with `invert`. */
export function linear([d0, d1], [r0, r1]) {
  const span = d1 - d0 || 1;
  const s = (value) => r0 + ((value - d0) / span) * (r1 - r0);
  s.invert = (pixel) => d0 + ((pixel - r0) / (r1 - r0 || 1)) * span;
  s.domain = [d0, d1];
  return s;
}

/** Base-10 logarithmic scale; the domain must be positive. */
export function log([d0, d1], [r0, r1]) {
  const l0 = Math.log10(d0);
  const l1 = Math.log10(d1);
  const s = (value) => r0 + ((Math.log10(value) - l0) / (l1 - l0 || 1)) * (r1 - r0);
  s.domain = [d0, d1];
  return s;
}

/** Round tick values covering a domain, about `target` of them. */
export function niceTicks([d0, d1], target = 5) {
  const span = d1 - d0;
  if (span <= 0) return [d0];
  const raw = span / target;
  const power = 10 ** Math.floor(Math.log10(raw));
  const step = [1, 2, 2.5, 5, 10].map((m) => m * power).find((s) => s >= raw) ?? raw;
  const out = [];
  for (let v = Math.ceil(d0 / step - 1e-9) * step; v <= d1 + step * 1e-6; v += step) out.push(Number(v.toFixed(10)));
  return out;
}

/** Powers of ten inside a positive domain. */
export function logTicks([d0, d1]) {
  const out = [];
  for (let e = Math.floor(Math.log10(d0)); e <= Math.ceil(Math.log10(d1)); e += 1) {
    const v = 10 ** e;
    if (v >= d0 * 0.999 && v <= d1 * 1.001) out.push(v);
  }
  return out;
}

/** SVG path through points already in pixel space. */
export const line = (points) =>
  points.map(([x, y], i) => `${i ? "L" : "M"}${x.toFixed(1)} ${y.toFixed(1)}`).join("");

/** Closed SVG path for a band between an upper and a lower series. */
export const band = (upper, lower) =>
  `${line(upper)}L${lower
    .slice()
    .reverse()
    .map(([x, y]) => `${x.toFixed(1)} ${y.toFixed(1)}`)
    .join("L")}Z`;
