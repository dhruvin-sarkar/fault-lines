import { useEffect, useRef, useState } from "react";
import { repoUrl } from "../lib/data.js";
import { useReducedMotion } from "../lib/hooks.js";
import { useTheme } from "../lib/theme.js";

const LINKS = [
  ["measure", "The measure"],
  ["collapse", "Six attacks"],
  ["findings", "Findings"],
  ["lookup", "Any cell type"],
  ["methods", "Methods"],
];

function ThemeMark({ dark }) {
  return dark ? (
    <svg width="16" height="16" viewBox="0 0 16 16" aria-hidden="true">
      <path
        d="M13.2 10.1A5.6 5.6 0 0 1 5.9 2.8a5.6 5.6 0 1 0 7.3 7.3Z"
        fill="none"
        stroke="currentColor"
        strokeWidth="1.6"
        strokeLinejoin="round"
      />
    </svg>
  ) : (
    <svg width="16" height="16" viewBox="0 0 16 16" aria-hidden="true">
      <circle cx="8" cy="8" r="3" fill="none" stroke="currentColor" strokeWidth="1.6" />
      <path
        d="M8 1.1v1.6M8 13.3v1.6M1.1 8h1.6M13.3 8h1.6M3.1 3.1l1.1 1.1M11.8 11.8l1.1 1.1M12.9 3.1l-1.1 1.1M4.2 11.8l-1.1 1.1"
        stroke="currentColor"
        strokeWidth="1.6"
        strokeLinecap="round"
      />
    </svg>
  );
}

/** Site bar; `ready` tells it the sections have rendered so it can mark the one being read. */
export default function Nav({ ready = true }) {
  const [current, setCurrent] = useState(null);
  const [theme, toggleTheme] = useTheme();
  const strip = useRef(null);
  const reduced = useReducedMotion();

  // On narrow screens the links scroll sideways; bring the current one into the strip without moving the page.
  useEffect(() => {
    const box = strip.current;
    const link = current && box?.querySelector(`a[href="#${current}"]`);
    if (!link || box.scrollWidth <= box.clientWidth) return;
    const edge = 32;
    const outer = box.getBoundingClientRect();
    const inner = link.getBoundingClientRect();
    let delta = 0;
    if (inner.left < outer.left) delta = inner.left - outer.left - 8;
    else if (inner.right > outer.right - edge) delta = inner.right - outer.right + edge;
    if (delta) box.scrollTo({ left: box.scrollLeft + delta, behavior: reduced ? "auto" : "smooth" });
  }, [current, reduced]);

  useEffect(() => {
    if (!ready) return undefined;
    let sections = [];
    const inBand = new Map();
    const spy = new IntersectionObserver(
      (entries) => {
        entries.forEach((e) => inBand.set(e.target, e.isIntersecting));
        const first = sections.find((s) => inBand.get(s));
        setCurrent(first ? first.id : null);
      },
      { rootMargin: "-40% 0px -55% 0px" },
    );
    // Sections can be replaced after first render; observe whichever elements currently carry the ids.
    const attach = () => {
      const next = LINKS.map(([id]) => document.getElementById(id)).filter(Boolean);
      if (next.length === sections.length && next.every((s, i) => s === sections[i])) return;
      spy.disconnect();
      inBand.clear();
      sections = next;
      sections.forEach((s) => spy.observe(s));
      if (!sections.length) setCurrent(null);
    };
    attach();
    const main = document.getElementById("main");
    const watcher = main ? new MutationObserver(attach) : null;
    watcher?.observe(main, { childList: true });
    return () => {
      watcher?.disconnect();
      spy.disconnect();
    };
  }, [ready]);

  return (
    <header className="nav">
      <div className="wrap nav-inner">
        <a className="wordmark" href="#main">
          <svg width="18" height="18" viewBox="0 0 18 18" aria-hidden="true">
            <path d="M2 3h14M2 9h6.5M11 9h5M2 15h14" stroke="currentColor" strokeWidth="2" strokeLinecap="round" />
            <path d="M9.6 5.5 8.2 12.5" stroke="var(--signal-glow)" strokeWidth="2" strokeLinecap="round" />
          </svg>
          Fault Lines
        </a>
        <nav className="nav-links" aria-label="Sections" ref={strip}>
          {LINKS.map(([id, label]) => (
            <a key={id} href={`#${id}`} className={current === id ? "is-current" : ""} aria-current={current === id ? "location" : undefined}>
              {label}
            </a>
          ))}
          <a className="nav-external" href={repoUrl}>
            Code and data
          </a>
        </nav>
        <button
          type="button"
          className="nav-theme"
          onClick={toggleTheme}
          aria-label={theme === "dark" ? "Switch to the light theme" : "Switch to the dark theme"}
        >
          <ThemeMark dark={theme === "dark"} />
        </button>
      </div>
    </header>
  );
}
