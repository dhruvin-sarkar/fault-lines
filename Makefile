PYTHON ?= python
WORKERS ?= 4
NULLS ?= 200
export PYTHONUTF8 = 1

.PHONY: reproduce data analyze validate context hero export web paper test clean

reproduce: data analyze validate context hero export paper

data:
	$(PYTHON) -m pipeline.schema_discovery
	$(PYTHON) -m pipeline.identify_sensory_motor_sets
	$(PYTHON) -m pipeline.build_type_graph

analyze:
	$(PYTHON) -m pipeline.run_percolation --workers $(WORKERS)
	$(PYTHON) -m pipeline.critical_thresholds
	$(PYTHON) -m pipeline.single_removal --workers $(WORKERS)
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
	cd web && npm install && npm run build

paper:
	cd paper && pandoc report.md -o report.pdf --pdf-engine=typst

test:
	$(PYTHON) -m pytest -q

clean:
	rm -rf web/dist paper/report.pdf
