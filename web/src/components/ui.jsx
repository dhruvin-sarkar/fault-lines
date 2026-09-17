import { createContext, useContext, useId, useRef } from "react";

/** Heading level for titles rendered by Figure, Finding and Pending; sections set it for what they contain. */
export const HeadingContext = createContext(3);

/** Sets the heading level used by figures and chapters below it. */
export function HeadingLevel({ level, children }) {
  return <HeadingContext.Provider value={level}>{children}</HeadingContext.Provider>;
}

/** Heading tag for an explicit level or the level from context, kept within h2 to h6. */
export function useHeading(level) {
  const context = useContext(HeadingContext);
  const resolved = Math.min(6, Math.max(2, level ?? context));
  return { level: resolved, Tag: `h${resolved}` };
}

/**
 * A figure: label and serif title with optional controls on the right, the graphic, and a caption on how to read it.
 * The label counts itself with a CSS counter; pass `number` to set it explicitly. The label is hidden from assistive
 * technology, so the figure is named by its title alone. `level` overrides the heading level from context.
 * `variant="field"` sets the figure on the black imaging field.
 */
export function Figure({ id, number, title, controls, caption, children, variant = "", className = "", level }) {
  const fallback = useId();
  const titleId = `${id ?? fallback}-title`;
  const { Tag } = useHeading(level);
  return (
    <figure
      id={id}
      className={`figure ${variant === "field" ? "figure-field field" : ""} ${className}`}
      aria-labelledby={titleId}
    >
      <div className="figure-head">
        <Tag id={titleId} className="figure-title">
          <span className="figure-number" aria-hidden="true">
            {number != null ? `Figure ${number}` : null}
          </span>
          {title}
        </Tag>
        {controls && <div className="figure-controls">{controls}</div>}
      </div>
      <div className="figure-body">{children}</div>
      {caption && <figcaption className="figure-caption">{caption}</figcaption>}
    </figure>
  );
}

/**
 * Exclusive choice as a washed track of buttons; arrow keys, Home and End move the choice.
 * Name the group with `label`, or with `labelledBy` pointing at a visible label's id. Options may carry a `color` swatch.
 */
export function Segmented({ label, labelledBy, options, value, onChange }) {
  const refs = useRef([]);
  const current = options.findIndex((o) => o.value === value);
  const onKeyDown = (event) => {
    const last = options.length - 1;
    let next;
    if (event.key === "Home") next = 0;
    else if (event.key === "End") next = last;
    else {
      const step = { ArrowRight: 1, ArrowDown: 1, ArrowLeft: -1, ArrowUp: -1 }[event.key];
      if (!step) return;
      next = (Math.max(current, 0) + step + options.length) % options.length;
    }
    event.preventDefault();
    onChange(options[next].value);
    refs.current[next]?.focus();
  };
  return (
    <div
      className="segmented"
      role="radiogroup"
      aria-label={labelledBy ? undefined : label}
      aria-labelledby={labelledBy}
      onKeyDown={onKeyDown}
    >
      {options.map((option, i) => (
        <button
          key={option.value}
          ref={(el) => (refs.current[i] = el)}
          type="button"
          role="radio"
          aria-checked={option.value === value}
          tabIndex={option.value === value || (current < 0 && i === 0) ? 0 : -1}
          className={option.value === value ? "on" : ""}
          onClick={() => onChange(option.value)}
        >
          {option.color && <span className="swatch" style={{ background: option.color }} aria-hidden="true" />}
          {option.label}
        </button>
      ))}
    </div>
  );
}

/** Prose beside a column of marginal notes; the notes drop below the prose on narrow screens. */
export function TextBlock({ children, notes }) {
  return (
    <div className="text-grid">
      <div className="prose">{children}</div>
      {notes && <div className="notes">{notes}</div>}
    </div>
  );
}

/** A marginal note beside the paragraph it annotates. */
export function Sidenote({ title, children }) {
  return (
    <aside className="sidenote">
      {title && <strong>{title}</strong>}
      {children}
    </aside>
  );
}

/** A number worth remembering, set large in the margin with what it counts. */
export function Keynote({ value, children, className = "" }) {
  return (
    <div className={`keynote ${className}`}>
      <div className="display">{value}</div>
      <div className="label">{children}</div>
    </div>
  );
}

/**
 * Range input with a visible label and value. The visible value is hidden from assistive technology;
 * `valueText` is what the input announces in place of the raw number.
 */
export function Slider({ label, min, max, step = 1, value, onChange, format = (v) => v, valueText }) {
  const id = useId();
  const text = typeof valueText === "function" ? valueText(value) : valueText;
  return (
    <div className="slider">
      <label htmlFor={id}>{label}</label>
      <input
        id={id}
        type="range"
        min={min}
        max={max}
        step={step}
        value={value}
        aria-valuetext={text}
        onChange={(e) => onChange(Number(e.target.value))}
      />
      <span className="slider-value" aria-hidden="true">
        {format(value)}
      </span>
    </div>
  );
}
