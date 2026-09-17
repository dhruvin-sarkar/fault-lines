import { useEffect, useLayoutEffect, useRef, useState } from "react";

function readTokens(key) {
  if (typeof document === "undefined") return {};
  const style = getComputedStyle(document.documentElement);
  return Object.fromEntries(key.split(",").map((n) => [n, style.getPropertyValue(`--${n}`).trim()]));
}

/** Resolved values of CSS custom properties, for canvas code. The palette is fixed, so they are read once. */
export function useTokens(names) {
  const key = names.join(",");
  const [tokens, setTokens] = useState(() => readTokens(key));
  // Re-read once after mount in case a stylesheet arrived after the first render.
  useEffect(() => {
    const next = readTokens(key);
    setTokens((prev) => (Object.keys(next).every((n) => prev[n] === next[n]) ? prev : next));
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

function contentWidth(node) {
  const style = getComputedStyle(node);
  const own = node.clientWidth - Number.parseFloat(style.paddingLeft || 0) - Number.parseFloat(style.paddingRight || 0);
  if (own > 0) return Math.round(own);
  return Math.max(0, Math.round(node.parentElement?.clientWidth ?? 0));
}

/**
 * Content width of an element, measured before first paint and tracked with ResizeObserver.
 * Returns `fallback` (0 by default) only until the element has been measured.
 */
export function useWidth(fallback = 0) {
  const ref = useRef(null);
  const [width, setWidth] = useState(fallback);
  useLayoutEffect(() => {
    const node = ref.current;
    if (!node) return undefined;
    setWidth(contentWidth(node));
    const observer = new ResizeObserver(([entry]) => setWidth(Math.round(entry.contentRect.width)));
    observer.observe(node);
    return () => observer.disconnect();
  }, []);
  return [ref, width];
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
