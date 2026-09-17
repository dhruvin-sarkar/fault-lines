PYTHON ?= python
WORKERS ?= 4
NULLS ?= 200
export PYTHONUTF8 = 1
CHECKS := schema sensory_motor_sets type_graph percolation critical_thresholds avalanches regional_impact structure_profile \
	edge_attack hidden_bottleneck synthetic_lethal_pairs pair_loss literature_validation brain_vnc bilateral null_model \
	type_atlas export references

.PHONY: reproduce data analyze validate context hero export web paper poster test verify readme captures clean

reproduce: data analyze validate context hero export paper test verify

data:
	$(PYTHON) -m pipeline.schema_discovery
	$(PYTHON) -m pipeline.identify_sensory_motor_sets
	$(PYTHON) -m pipeline.build_type_graph

analyze:
	$(PYTHON) -m pipeline.run_percolation --workers $(WORKERS)
	$(PYTHON) -m pipeline.critical_thresholds
	$(PYTHON) -m pipeline.run_percolation --from-results
	$(PYTHON) -m pipeline.single_removal --workers $(WORKERS)
	$(PYTHON) -m pipeline.pair_loss
	$(PYTHON) -m pipeline.avalanche_analysis
	$(PYTHON) -m pipeline.brain_vnc_comparison --workers $(WORKERS)
	$(PYTHON) -m pipeline.synthetic_lethal_pairs --workers $(WORKERS)
	$(PYTHON) -m pipeline.bilateral_symmetry --workers $(WORKERS)
	$(PYTHON) -m pipeline.hidden_bottleneck
	$(PYTHON) -m pipeline.structure_profile --workers $(WORKERS)
	$(PYTHON) -m pipeline.edge_attack

validate:
	$(PYTHON) -m pipeline.null_model --n-nulls $(NULLS) --workers $(WORKERS)
	$(PYTHON) -m pipeline.literature_validation

context:
	$(PYTHON) -m pipeline.network_comparison

hero:
	$(PYTHON) -m pipeline.regional_impact --workers $(WORKERS)
	$(PYTHON) -m pipeline.render_hero
	$(PYTHON) -m pipeline.type_atlas

export:
	$(PYTHON) -m export.build_static_json

web: export
	cd web && npm ci && npm run build

paper:
	cd paper && pandoc report.md -o report.pdf --pdf-engine=typst

# Poster faces are cut from the site's fonts in web/node_modules; reading WOFF2 needs the brotli module.
poster:
	$(PYTHON) -m pipeline.poster

test:
	$(PYTHON) -m pytest -q

# Checks the committed results against their invariants and each other; fails if any check fails.
# Checks whose inputs are not on disk report SKIP and do not fail.
verify:
	@status=0; for c in $(CHECKS); do printf "%-24s" "$$c"; $(PYTHON) -m verify.check_$$c || status=1; done; exit $$status

# README plates, figures and methods diagram, drawn from results/ into assets/readme/.
readme:
	$(PYTHON) -m pipeline.readme_assets

# GIFs and the phone strip of the site. Recording needs the built site served with `npx vite preview --port 4173`
# in web/ and Chrome started with --remote-debugging-port=9222; `site_captures assemble` rebuilds from saved frames.
captures:
	$(PYTHON) -m pipeline.site_captures

clean:
	rm -rf web/dist paper/report.pdf
