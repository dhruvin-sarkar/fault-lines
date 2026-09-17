import { useEffect } from "react";

// Keep a deep link anchored until the page above it has been still this long, and never longer than the limit.
const QUIET_MS = 3000;
const LIMIT_MS = 10000;
const TAKEOVER = ["wheel", "touchstart", "keydown", "pointerdown"];

function decodedHash(hash) {
  try {
    return decodeURIComponent(hash.slice(1));
  } catch {
    return hash.slice(1);
  }
}

/** Element a location hash points at: the element with that id, or for a "#section/key" hash the section. */
export function hashTarget(hash) {
  if (!hash || hash.length < 2) return null;
  const id = decodedHash(hash);
  const exact = document.getElementById(id);
  if (exact || !id.includes("/")) return exact;
  return document.getElementById(id.slice(0, id.indexOf("/")));
}

/**
 * Scrolls to the location hash once the sections exist, and keeps the target in place while content above it
 * finishes loading and changes height. It lets go when the reader scrolls, touches, clicks or types, or once the
 * main element has not changed size for a few seconds. Scrolling is instant; scroll-padding-top keeps the target
 * clear of the sticky bar.
 */
export function useHashLanding(ready) {
  useEffect(() => {
    const main = document.getElementById("main");
    const { hash } = window.location;
    if (!ready || !main || hash.length < 2) return undefined;

    let quiet = null;
    let observer = null;
    const limit = setTimeout(() => stop(), LIMIT_MS);

    function stop() {
      observer?.disconnect();
      observer = null;
      clearTimeout(quiet);
      clearTimeout(limit);
      TAKEOVER.forEach((type) => window.removeEventListener(type, stop));
    }

    // Runs in the ResizeObserver callback, after layout, so measuring the target does not force a reflow.
    function land() {
      if (window.location.hash !== hash) {
        stop();
        return;
      }
      const target = hashTarget(hash);
      if (!target) return;
      target.scrollIntoView({ block: "start", inline: "nearest", behavior: "instant" });
      clearTimeout(quiet);
      quiet = setTimeout(stop, QUIET_MS);
    }

    observer = new ResizeObserver(land);
    observer.observe(main);
    TAKEOVER.forEach((type) => window.addEventListener(type, stop, { passive: true }));
    return stop;
  }, [ready]);

  // In-page links to "#section/key" have no element of that id, so the browser does not scroll for them.
  useEffect(() => {
    const onHash = () => {
      const { hash } = window.location;
      if (hash.length < 2 || document.getElementById(decodedHash(hash))) return;
      hashTarget(hash)?.scrollIntoView({ block: "start" });
    };
    window.addEventListener("hashchange", onHash);
    return () => window.removeEventListener("hashchange", onHash);
  }, []);
}
