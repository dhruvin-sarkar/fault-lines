export const percent = (value, digits = 1) =>
  value == null || Number.isNaN(value) ? "n/a" : `${(100 * value).toFixed(digits)}%`;

export const count = (value) => (value == null ? "n/a" : Math.round(value).toLocaleString("en-US"));

export const fixed = (value, digits = 2) => (value == null ? "n/a" : Number(value).toFixed(digits));

const MINUS = "\u2212";

/** A count with an explicit sign, negatives with a true minus. */
export const signedCount = (value) => (value > 0 ? `+${count(value)}` : value < 0 ? `${MINUS}${count(-value)}` : count(value));

/** A number to `digits` decimals with an explicit sign, negatives with a true minus. */
export const signedFixed = (value, digits = 2) =>
  value > 0 ? `+${fixed(value, digits)}` : value < 0 ? `${MINUS}${fixed(-value, digits)}` : fixed(value, digits);

/** Text with its first letter capitalized, for the start of a sentence, a label or a key. */
export const sentence = (text) => (text ? `${text[0].toUpperCase()}${text.slice(1)}` : text);

const NUMBER_WORDS = ["no", "one", "two", "three", "four", "five", "six", "seven", "eight", "nine", "ten"];

/** A count up to ten as a word, larger counts as digits. */
export const numberWord = (n) => NUMBER_WORDS[n] ?? count(n);

/** p-value: "< 0.001" below 0.001, three decimals below 0.1, two decimals above. */
export function pValue(p) {
  if (p == null || Number.isNaN(p)) return "n/a";
  if (p < 0.001) return "< 0.001";
  if (p < 0.1) return p.toFixed(3);
  return p.toFixed(2);
}

/** p-value as a clause for running text: "p = 0.036", or "p < 0.001". */
export function pClause(p) {
  const text = pValue(p);
  return text.startsWith("<") ? `p ${text}` : `p = ${text}`;
}

/** One short name per removal strategy, used the same way in prose, legends and controls. */
const STRATEGY_SHORT = {
  sm_betweenness: "sensory-motor betweenness",
  betweenness: "betweenness",
  pagerank: "PageRank",
  out_strength: "weighted out-degree",
  in_strength: "weighted in-degree",
  random: "random",
};

/** Short strategy name; `capital` starts it with a capital letter, for the start of a sentence or a label. */
export function strategyLabel(id, { capital = false } = {}) {
  const name = STRATEGY_SHORT[id] ?? String(id).replaceAll("_", " ");
  return capital ? sentence(name) : name;
}

const SUPERCLASS_NAMES = {
  ascending_neuron: "ascending",
  cb_intrinsic: "central brain intrinsic",
  cb_motor: "central brain motor",
  cb_sensory: "central brain sensory",
  descending_neuron: "descending",
  endocrine: "endocrine",
  ol_intrinsic: "optic lobe intrinsic",
  ol_sensory: "optic lobe sensory",
  sensory: "sensory",
  sensory_ascending: "sensory ascending",
  vnc_efferent: "nerve cord efferent",
  vnc_intrinsic: "nerve cord intrinsic",
  vnc_motor: "nerve cord motor",
  vnc_sensory: "nerve cord sensory",
  visual_centrifugal: "visual centrifugal",
  visual_projection: "visual projection",
  unknown: "unassigned",
};

export const superclassName = (id) => SUPERCLASS_NAMES[id] ?? String(id).replaceAll("_", " ");

/** Index of the last point at or below a removal fraction. */
export function indexAt(fractions, fraction) {
  let lo = 0;
  let hi = fractions.length - 1;
  while (lo < hi) {
    const mid = (lo + hi + 1) >> 1;
    if (fractions[mid] <= fraction + 1e-9) lo = mid;
    else hi = mid - 1;
  }
  return lo;
}

/** Linear interpolation of a series at a removal fraction. */
export function valueAt(fractions, values, fraction) {
  const i = indexAt(fractions, fraction);
  if (i >= fractions.length - 1) return values[values.length - 1];
  const t = (fraction - fractions[i]) / (fractions[i + 1] - fractions[i] || 1);
  return values[i] + Math.max(0, Math.min(1, t)) * (values[i + 1] - values[i]);
}
