import Nav from "./components/Nav.jsx";
import Hero from "./components/Hero.jsx";
import Measure from "./components/Measure.jsx";
import Collapse from "./components/Collapse.jsx";
import Findings from "./components/Findings.jsx";
import Lookup from "./components/Lookup.jsx";
import Methods, { Footer } from "./components/Methods.jsx";
import SectionBoundary from "./components/SectionBoundary.jsx";
import { useData } from "./lib/data.js";
import { useHashLanding } from "./lib/landing.js";

export default function App() {
  const meta = useData("meta.json");
  const percolation = useData("percolation.json");
  const types = useData("types.json");
  const atlas = useData("atlas.json");
  const error = meta.error || percolation.error || types.error || atlas.error;
  const ready = meta.data && percolation.data && types.data && atlas.data;
  const shared = ready && { meta: meta.data, percolation: percolation.data, types: types.data, atlas: atlas.data };
  useHashLanding(Boolean(shared));

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
            <SectionBoundary>
              <Hero {...shared} />
            </SectionBoundary>
            <SectionBoundary id="measure">
              <Measure {...shared} />
            </SectionBoundary>
            <SectionBoundary id="collapse">
              <Collapse {...shared} />
            </SectionBoundary>
            <SectionBoundary id="findings">
              <Findings {...shared} />
            </SectionBoundary>
            <SectionBoundary id="lookup">
              <Lookup {...shared} />
            </SectionBoundary>
            <SectionBoundary id="methods">
              <Methods {...shared} />
            </SectionBoundary>
          </>
        )}
      </main>
      {shared && (
        <SectionBoundary>
          <Footer {...shared} />
        </SectionBoundary>
      )}
    </>
  );
}

function HeroSkeleton() {
  return (
    <section className="hero" aria-busy="true">
      <div className="wrap hero-frame">
        <div className="hero-plate-copy">
          <h1 className="hero-title">Fault Lines</h1>
          <p className="hero-deck">
            How much of a fly&apos;s nervous system can be lost before its senses no longer reach the neurons that move it?
          </p>
          <p className="hero-answer">Loading cell types and the removal experiments run on them.</p>
        </div>
        <div className="hero-stage">
          <div className="hero-atlas" />
          <div className="hero-scrub" aria-hidden="true">
            <div className="hero-scrub-read">&nbsp;</div>
            <div className="hero-scrub-track" />
          </div>
          <p className="hero-caption">
            Each point is a cell type, placed where it makes synapses. Red: removed at this step. Dim: cut off from sensory
            input. The slider steps through removal batches; the tick marks where flow crosses half.
          </p>
        </div>
      </div>
    </section>
  );
}
