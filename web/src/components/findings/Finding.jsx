import { useAvailable, useData } from "../../lib/data.js";
import { HeadingLevel, useHeading } from "../ui.jsx";

/**
 * One finding as a chapter: serif title beside its measured number, then prose, sidenotes and figures.
 * `stat` is the headline value; `statLabel` says what it counts. The title takes the heading level from context,
 * or `level`; figures in the body sit one level below it.
 */
export function Finding({ id, title, stat, statLabel, children, level }) {
  const { level: resolved, Tag } = useHeading(level);
  return (
    <article className="finding" id={id} aria-labelledby={`${id}-title`}>
      <header className="finding-head">
        <Tag id={`${id}-title`} className="finding-title">
          {title}
        </Tag>
        {stat != null && (
          <div className="finding-key">
            <div className="display">{stat}</div>
            {statLabel && <div className="label">{statLabel}</div>}
          </div>
        )}
      </header>
      <div className="finding-body">
        <HeadingLevel level={resolved + 1}>{children}</HeadingLevel>
      </div>
    </article>
  );
}

/**
 * Load a result file that may not have been exported yet.
 * Returns { data, missing }: `missing` is true when the exporter skipped that section.
 */
export function useResult(name) {
  const available = useAvailable();
  const missing = available != null && !available.has(name);
  const { data, error } = useData(missing || available == null ? null : name);
  return { data, missing: missing || Boolean(error) };
}

/** Placeholder shown only in local builds where an analysis has not finished. */
export function Pending({ id, title, level }) {
  const { Tag } = useHeading(level);
  return (
    <article className="finding" id={id} aria-labelledby={`${id}-title`}>
      <header className="finding-head">
        <Tag id={`${id}-title`} className="finding-title">
          {title}
        </Tag>
      </header>
      <p className="pending plate">This analysis has not been exported in this build.</p>
    </article>
  );
}
