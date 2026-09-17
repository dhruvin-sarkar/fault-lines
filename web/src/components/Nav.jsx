import { useEffect, useState } from "react";
import { repoUrl } from "../lib/data.js";

const LINKS = [
  ["measure", "The measure"],
  ["collapse", "Six attacks"],
  ["findings", "Findings"],
  ["lookup", "Any cell type"],
  ["methods", "Methods"],
];

/** Site bar; `ready` tells it the sections have rendered so it can mark the one being read. */
export default function Nav({ ready = true }) {
  const [current, setCurrent] = useState(null);

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
        <nav className="nav-links" aria-label="Sections">
          {LINKS.map(([id, label]) => (
            <a key={id} href={`#${id}`} className={current === id ? "is-current" : ""} aria-current={current === id ? "location" : undefined}>
              {label}
            </a>
          ))}
          <a className="nav-external" href={repoUrl}>
            Code and data
          </a>
        </nav>
      </div>
    </header>
  );
}
