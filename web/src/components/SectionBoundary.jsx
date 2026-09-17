import { Component } from "react";

function reload(event) {
  event.preventDefault();
  window.location.reload();
}

/**
 * Renders its children, or a short notice in their place if they throw while rendering, so one failing part of the
 * page leaves the rest readable.
 * `id` is kept on the notice so links to the part still land; `as` is "section" for a top-level section or
 * "finding" for a chapter within the findings.
 */
export default class SectionBoundary extends Component {
  state = { failed: false };

  static getDerivedStateFromError() {
    return { failed: true };
  }

  render() {
    if (!this.state.failed) return this.props.children;
    const { id, as = "section" } = this.props;
    const notice = (
      <p className="pending">
        This {as === "finding" ? "result" : "section"} could not be shown.{" "}
        <a href="" onClick={reload}>
          Reload the page
        </a>{" "}
        to try again.
      </p>
    );
    if (as === "finding") {
      return (
        <article className="finding" id={id}>
          {notice}
        </article>
      );
    }
    return (
      <section className="section" id={id}>
        <div className="wrap">{notice}</div>
      </section>
    );
  }
}
