import Nav from "./components/Nav.jsx";
import Hero from "./components/Hero.jsx";
import Measure from "./components/Measure.jsx";
import Collapse from "./components/Collapse.jsx";
import Findings from "./components/Findings.jsx";
import Lookup from "./components/Lookup.jsx";
import Methods, { Footer } from "./components/Methods.jsx";
import { useData } from "./lib/data.js";

export default function App() {
  const meta = useData("meta.json");
  const percolation = useData("percolation.json");
  const types = useData("types.json");
  const atlas = useData("atlas.json");
  const error = meta.error || percolation.error || types.error || atlas.error;
  const ready = meta.data && percolation.data && types.data && atlas.data;
  const shared = ready && { meta: meta.data, percolation: percolation.data, types: types.data, atlas: atlas.data };

  return (
    <>
      <a className="skip-link" href="#main">
        Skip to content
      </a>
      <Nav ready={Boolean(shared)} />
      <main id="main">
        {error && (
          <div className="wrap section">
            <p className="pending plate">
              The results could not be loaded ({error.message}). Reload the page; if the problem stays, the data files
              are missing from this build.
            </p>
          </div>
        )}
        {!error && !ready && <HeroSkeleton />}
        {shared && (
          <>
            <Hero {...shared} />
            <Measure {...shared} />
            <Collapse {...shared} />
            <Findings {...shared} />
            <Lookup {...shared} />
            <Methods {...shared} />
          </>
        )}
      </main>
      {shared && <Footer {...shared} />}
    </>
  );
}

function HeroSkeleton() {
  return (
    <section className="hero" aria-busy="true">
      <div className="wrap hero-grid">
        <div className="hero-copy">
          <h1 className="hero-title">Fault Lines</h1>
          <p className="hero-answer">Loading cell types and the removal experiments run on them.</p>
        </div>
        <div className="hero-figure" />
      </div>
    </section>
  );
}
