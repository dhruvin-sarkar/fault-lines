import { useCallback, useEffect, useState } from "react";
import { flushSync } from "react-dom";

const KEY = "fault-lines:theme";
const SYSTEM_DARK = "(prefers-color-scheme: dark)";
const WIPE_MS = 620;

function stored() {
  try {
    const value = localStorage.getItem(KEY);
    return value === "light" || value === "dark" ? value : null;
  } catch (error) {
    return null;
  }
}

/** Distance from a point to the farthest corner of the viewport: how far the wipe has to travel. */
function reach(x, y) {
  return Math.hypot(Math.max(x, innerWidth - x), Math.max(y, innerHeight - y));
}

/**
 * The theme in force and a toggle for it. The inline script in index.html puts the resolved theme on the root
 * element before first paint; this keeps it following the system setting until the reader chooses one.
 * The toggle takes the event that caused it so the new theme can be wiped in from the control that was pressed.
 */
export function useTheme() {
  const [theme, setTheme] = useState(() => document.documentElement.dataset.theme ?? "light");
  const [chosen, setChosen] = useState(stored);

  useEffect(() => {
    document.documentElement.dataset.theme = theme;
  }, [theme]);

  useEffect(() => {
    if (chosen) return undefined;
    const query = window.matchMedia(SYSTEM_DARK);
    const follow = () => setTheme(query.matches ? "dark" : "light");
    follow();
    query.addEventListener("change", follow);
    return () => query.removeEventListener("change", follow);
  }, [chosen]);

  const toggle = useCallback((event) => {
    const next = (document.documentElement.dataset.theme ?? "light") === "dark" ? "light" : "dark";
    try {
      localStorage.setItem(KEY, next);
    } catch (error) {
      /* storage blocked: the choice lasts for this page only */
    }
    const apply = () => {
      document.documentElement.dataset.theme = next;
      flushSync(() => {
        setChosen(next);
        setTheme(next);
      });
    };

    if (matchMedia("(prefers-reduced-motion: reduce)").matches || !document.startViewTransition) {
      apply();
      return;
    }

    // The new theme is wiped in as a circle opening from the control, so the change has a direction.
    const box = event?.currentTarget?.getBoundingClientRect?.();
    const x = box ? box.left + box.width / 2 : innerWidth - 48;
    const y = box ? box.top + box.height / 2 : 48;
    const transition = document.startViewTransition(apply);
    transition.ready
      .then(
        () =>
          document.documentElement.animate(
            { clipPath: [`circle(0px at ${x}px ${y}px)`, `circle(${reach(x, y)}px at ${x}px ${y}px)`] },
            {
              duration: WIPE_MS,
              easing: "cubic-bezier(0.22, 1, 0.36, 1)",
              pseudoElement: "::view-transition-new(root)",
            },
          ).finished,
      )
      .catch(() => {});
  }, []);

  return [theme, toggle];
}
