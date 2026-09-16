"""Place every cell type in the body and record when each strategy removes it or cuts it off from sensory input."""

import json

import contourpy
import numpy as np
import pandas as pd
from PIL import Image, ImageDraw

from pipeline.build_type_graph import load_type_graph
from pipeline.common import NEURON_ROI_PATH, NEURONS_PATH, RESULTS, SEED, TYPE_NODES_PATH
from pipeline.connectivity_metrics import unreachable_from
from pipeline.identify_sensory_motor_sets import load_sensory_motor_sets
from pipeline.regional_impact import AGGREGATE_ROIS, anchor_neuropils, load_regional_impact
from pipeline.removal_strategies import STRATEGIES
from pipeline.render_hero import CLUSTER_NM, UNSCORED_ROIS, load_meshes, rotation, simplify
from pipeline.run_percolation import RUNS_DIR

PITCH, YAW = 18.0, 0.0
CANVAS = 1000.0
RASTER = 1400
JITTER_REACH = 0.85
OUTLINE_TOLERANCE = 1.2


def project(points: np.ndarray, center: np.ndarray) -> np.ndarray:
    """Screen x, screen y (down) and depth under the hero camera, in nanometres."""
    rotated = (points - center) @ rotation(PITCH, YAW).T
    return rotated


def rdp(points: np.ndarray, tolerance: float) -> np.ndarray:
    """Ramer-Douglas-Peucker simplification of an open polyline."""
    if len(points) < 3:
        return points
    start, end = points[0], points[-1]
    segment = end - start
    length = np.hypot(*segment)
    if length == 0:
        distances = np.hypot(*(points - start).T)
    else:
        distances = np.abs(segment[0] * (points[:, 1] - start[1]) - segment[1] * (points[:, 0] - start[0])) / length
    split = int(np.argmax(distances))
    if distances[split] <= tolerance:
        return np.array([start, end])
    return np.vstack([rdp(points[: split + 1], tolerance)[:-1], rdp(points[split:], tolerance)])


def outline_path(triangles: np.ndarray, to_raster, min_area: float = 12.0) -> str:
    """SVG path of the filled silhouette of projected triangles, in canvas units."""
    mask = Image.new("L", (RASTER, RASTER), 0)
    draw = ImageDraw.Draw(mask)
    for triangle in to_raster(triangles.reshape(-1, 2)).reshape(-1, 3, 2):
        draw.polygon([tuple(p) for p in triangle], fill=255)
    lines = contourpy.contour_generator(z=np.asarray(mask, dtype=float) / 255).lines(0.5)
    scale = CANVAS / RASTER
    parts = []
    for line in lines:
        x, y = line[:, 0], line[:, 1]
        if 0.5 * abs(np.dot(x, np.roll(y, 1)) - np.dot(y, np.roll(x, 1))) < min_area:
            continue
        simplified = rdp(line, OUTLINE_TOLERANCE) * scale
        parts.append("M" + "L".join(f"{px:.1f} {py:.1f}" for px, py in simplified) + "Z")
    return "".join(parts)


def type_positions(meshes: dict, center: np.ndarray, rng: np.random.Generator) -> pd.DataFrame:
    """One point per type, inside a neuropil drawn with probability proportional to the type's synapses there.

    The point lies between the neuropil centroid and a random mesh vertex, so it falls inside the neuropil for
    roughly convex shapes; the drawing is seeded and reproducible.
    """
    centroids = {name: vertices.mean(axis=0) for name, (vertices, _) in meshes.items()}
    counts = pd.read_parquet(NEURON_ROI_PATH)
    neurons = pd.read_parquet(NEURONS_PATH)
    leaf = counts[~counts["roi"].isin(AGGREGATE_ROIS) & counts["roi"].isin(centroids.keys())]
    merged = leaf.merge(neurons[["bodyId", "type"]].dropna(), on="bodyId")
    merged["synapses"] = merged["pre"] + merged["post"]
    per_type = merged.groupby(["type", "roi"], as_index=False)["synapses"].sum()
    per_type = per_type[per_type["synapses"] > 0]
    names, points = [], []
    for cell_type, rows in per_type.groupby("type", sort=True):
        weights = rows["synapses"].to_numpy(dtype=float)
        roi = rows["roi"].to_numpy()[rng.choice(len(rows), p=weights / weights.sum())]
        vertices = meshes[roi][0]
        rim = vertices[rng.integers(len(vertices))]
        points.append(centroids[roi] + (rim - centroids[roi]) * rng.random() ** (1 / 3) * JITTER_REACH)
        names.append(cell_type)
    anchors = anchor_neuropils(counts, neurons).reindex(names)
    screen = project(np.asarray(points), center)
    return pd.DataFrame({"cell_type": names, "sx": screen[:, 0], "sy": screen[:, 1], "anchor": anchors.to_numpy()})


def replay(graph, sources: list[str]) -> tuple[pd.DataFrame, dict]:
    """Batch at which each type is removed, and at which it first has no path from any sensory type."""
    names = graph.vs["name"]
    index = {n: i for i, n in enumerate(names)}
    table = pd.DataFrame({"cell_type": names})
    counts = {}
    for strategy in STRATEGIES:
        run = json.loads((RUNS_DIR / f"{strategy}_00.json").read_text(encoding="utf-8"))
        removed_at = dict.fromkeys(names, -1)
        silenced_at = dict.fromkeys(names, -1)
        initially_silent = unreachable_from(graph, sources)
        for name in initially_silent:
            silenced_at[name] = 0
        gone: set[str] = set()
        removed_counts, silenced_counts = [0], [len(initially_silent)]
        for batch, members in enumerate(run["removed"], start=1):
            for name in members:
                removed_at[name] = batch
            gone.update(members)
            reduced = graph.copy()
            reduced.delete_vertices([index[n] for n in gone])
            silent = unreachable_from(reduced, sources)
            for name in silent:
                if silenced_at[name] == -1:
                    silenced_at[name] = batch
            removed_counts.append(len(gone))
            silenced_counts.append(len(silent))
        table[f"removed_{strategy}"] = table["cell_type"].map(removed_at)
        table[f"silenced_{strategy}"] = table["cell_type"].map(silenced_at)
        counts[strategy] = {"fraction_removed": run["fraction_removed"], "removed_types": removed_counts,
                            "silenced_types": silenced_counts}
        print(f"{strategy}: {silenced_counts[-1]} types silenced after {removed_counts[-1]} removed", flush=True)
    return table, counts


def main() -> None:
    graph = load_type_graph()
    sources, _ = load_sensory_motor_sets()
    scored = set(load_regional_impact()["neuropil"])
    meshes = load_meshes(scored | set(UNSCORED_ROIS))
    center = np.concatenate([v for v, _ in meshes.values()]).mean(axis=0)

    projected = {}
    for name, (vertices, faces) in meshes.items():
        v, f = simplify(vertices, faces, CLUSTER_NM)
        screen = project(v, center)
        projected[name] = (screen[f][:, :, :2], float(screen[:, 2].mean()))
    corners = np.concatenate([tri.reshape(-1, 2) for tri, _ in projected.values()])
    low, high = corners.min(axis=0), corners.max(axis=0)
    unit = (CANVAS - 20) / (high - low).max()
    offset = (CANVAS - (high - low) * unit) / 2

    def to_canvas(points: np.ndarray) -> np.ndarray:
        return (points - low) * unit + offset

    def to_raster(points: np.ndarray) -> np.ndarray:
        return to_canvas(points) * RASTER / CANVAS

    outlines = [{"neuropil": name, "scored": name in scored, "depth": round(depth / 1000, 1),
                 "path": outline_path(tri, to_raster)}
                for name, (tri, depth) in sorted(projected.items(), key=lambda item: -item[1][1])]
    whole = outline_path(np.concatenate([tri for tri, _ in projected.values()]), to_raster, min_area=400.0)

    positions = type_positions(meshes, center, np.random.default_rng(SEED + 11))
    canvas_xy = to_canvas(positions[["sx", "sy"]].to_numpy())
    positions["x"], positions["y"] = canvas_xy[:, 0].round(1), canvas_xy[:, 1].round(1)
    nodes = pd.read_parquet(TYPE_NODES_PATH)[["cell_type", "superclass"]]
    compartments = pd.read_csv(RESULTS / "type_compartments.csv")[["cell_type", "compartment"]]
    timeline, counts = replay(graph, sources)
    atlas = (nodes.merge(compartments, on="cell_type", how="left")
             .merge(positions[["cell_type", "anchor", "x", "y"]], on="cell_type", how="left")
             .merge(timeline, on="cell_type", how="left"))
    atlas.to_csv(RESULTS / "type_atlas.csv", index=False)

    summary = {
        "canvas": [CANVAS, CANVAS], "view": {"pitch": PITCH, "yaw": YAW},
        "types_placed": int(atlas["x"].notna().sum()), "types": len(atlas),
        "cns_outline": whole, "outlines": outlines, "replay": counts,
    }
    (RESULTS / "type_atlas.json").write_text(json.dumps(summary) + "\n", encoding="utf-8")
    print(f"{summary['types_placed']} of {len(atlas)} types placed; {len(outlines)} neuropil outlines")


if __name__ == "__main__":
    main()
