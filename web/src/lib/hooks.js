import { useEffect, useLayoutEffect, useRef, useState } from "react";

function readTokens(key) {
  if (typeof document === "undefined") return {};
  const style = getComputedStyle(document.documentElement);
  return Object.fromEntries(key.split(",").map((n) => [n, style.getPropertyValue(`--${n}`).trim()]));
}

/** Resolved values of CSS custom properties, for canvas code, re-read whenever the theme changes. */
export function useTokens(names) {
  const key = names.join(",");
  const [tokens, setTokens] = useState(() => readTokens(key));
  useEffect(() => {
    const reread = () =>
      setTokens((prev) => {
        const next = readTokens(key);
        return Object.keys(next).every((n) => prev[n] === next[n]) ? prev : next;
      });
    // Once on mount in case a stylesheet arrived after the first render, then on every theme change.
    reread();
    const watcher = new MutationObserver(reread);
    watcher.observe(document.documentElement, { attributeFilter: ["data-theme"] });
    return () => watcher.disconnect();
  }, [key]);
  return tokens;
}

export function useReducedMotion() {
  const [reduced, setReduced] = useState(
    () => typeof window !== "undefined" && window.matchMedia("(prefers-reduced-motion: reduce)").matches,
  );
  useEffect(() => {
    const query = window.matchMedia("(prefers-reduced-motion: reduce)");
    const update = () => setReduced(query.matches);
    query.addEventListener("change", update);
    return () => query.removeEventListener("change", update);
  }, []);
  return reduced;
}

/** True once the element has come within view; used to start data animations when the reader arrives. */
export function useInView(rootMargin = "0px 0px -20% 0px") {
  const ref = useRef(null);
  const [seen, setSeen] = useState(false);
  useEffect(() => {
    const node = ref.current;
    if (!node || seen) return undefined;
    const observer = new IntersectionObserver(
      ([entry]) => {
        if (entry.isIntersecting) {
          setSeen(true);
          observer.disconnect();
        }
      },
      { rootMargin },
    );
    observer.observe(node);
    return () => observer.disconnect();
  }, [seen, rootMargin]);
  return [ref, seen];
}

// One observer for every measured element, so a resize reaches all charts in a single callback and one render.
const widthListeners = new Map();
let widthObserver = null;

function observeWidth(node, listener) {
  widthObserver ??= new ResizeObserver((entries) => {
    for (const entry of entries) {
      let width = Math.round(entry.contentRect.width);
      // Layout is clean inside the callback, so reading the parent here does not force a reflow.
      if (width <= 0) width = Math.round(entry.target.parentElement?.clientWidth ?? 0);
      widthListeners.get(entry.target)?.(width);
    }
  });
  widthListeners.set(node, listener);
  widthObserver.observe(node);
  return () => {
    widthListeners.delete(node);
    widthObserver.unobserve(node);
  };
}

/**
 * Content width of an element, tracked with a shared ResizeObserver. The first width arrives with the observer's
 * first callback, after layout and before paint; until then the hook returns `fallback` (0 by default).
 */
export function useWidth(fallback = 0) {
  const ref = useRef(null);
  const [width, setWidth] = useState(fallback);
  useLayoutEffect(() => {
    const node = ref.current;
    if (!node) return undefined;
    return observeWidth(node, (next) => {
      if (next > 0) setWidth(next);
    });
  }, []);
  return [ref, width];
}

const nearListeners = new Map();
let nearObserver = null;

function observeNear(node, listener) {
  nearObserver ??= new IntersectionObserver(
    (entries) => {
      for (const entry of entries) {
        if (!entry.isIntersecting) continue;
        const done = nearListeners.get(entry.target);
        nearListeners.delete(entry.target);
        nearObserver.unobserve(entry.target);
        done?.();
      }
    },
    { rootMargin: "150% 0px" },
  );
  nearListeners.set(node, listener);
  nearObserver.observe(node);
  return () => {
    nearListeners.delete(node);
    nearObserver.unobserve(node);
  };
}

/**
 * True once the element referenced by `ref` has come within about one and a half screens of the viewport, and from
 * then on. Drawing waits for it; layout must not, so callers keep the element's size fixed either way.
 */
export function useNear(ref) {
  const [near, setNear] = useState(() => typeof IntersectionObserver === "undefined");
  useLayoutEffect(() => {
    const node = ref.current;
    if (near || !node) return undefined;
    return observeNear(node, () => setNear(true));
  }, [ref, near]);
  return near;
}

/** A playhead advancing through integer steps at a fixed interval; stops at the last step. */
export function usePlayhead(steps, interval = 160) {
  const [step, setStep] = useState(0);
  const [playing, setPlaying] = useState(false);
  useEffect(() => {
    if (!playing) return undefined;
    const timer = setInterval(() => {
      setStep((s) => {
        if (s >= steps - 1) {
          setPlaying(false);
          return s;
        }
        return s + 1;
      });
    }, interval);
    return () => clearInterval(timer);
  }, [playing, steps, interval]);
  return { step, setStep, playing, setPlaying };
}
