"""Render the male CNS neuropils, each shaded by the sensory-to-motor flow lost when its cell types are removed."""

import hashlib
import json
import textwrap
import urllib.parse
from pathlib import Path

import numpy as np
import pandas as pd
import requests
from matplotlib.collections import PolyCollection
from matplotlib.colors import LinearSegmentedColormap, to_rgb
from PIL import Image

from pipeline.common import ASSETS, DATA, RESULTS, ROOT
from pipeline.figures import plt
from pipeline.fonts import register
from pipeline.removal_strategies import STRATEGY_LABELS
from pipeline.regional_impact import load_regional_impact

MESH_SOURCES = {
    "brain": "https://storage.googleapis.com/flyem-male-cns/rois/fullbrain-roi-v5",
    "vnc": "https://storage.googleapis.com/flyem-male-cns/rois/malecns-vnc-neuropil-roi-v0",
}
MESH_CACHE = DATA / "neuropil_meshes"
HERO_SIZE = (1920, 1080)
SUPERSAMPLE = 2
CLUSTER_NM = 2000.0
PAPER = "#f4f5f3"
INK = "#0b0b0b"
INK_SECONDARY = "#52514e"
MUTED = "#898781"
RAMP = LinearSegmentedColormap.from_list("impact", ["#ece9e3", "#e3b9bf", "#d1344b", "#600d1c"])
UNSCORED_ROIS = ("CV-anterior", "CV-posterior")
UNSCORED_COLOR = "#d6d5cf"
GAMMA = 0.5
SCALE_TICKS = (0.0, 0.02, 0.05, 0.10, 0.20, 0.35)
MAP_MESH_BOX = (690, 5, 1780, 1062)
MAP_SCALE_BOX = (50, 777, 640, 870)
PAPER_DIR = ROOT / "paper"


def mesh_names(source: str) -> list[str]:
    """Neuropil names published for one mesh source."""
    info = requests.get(f"{MESH_SOURCES[source]}/segment_properties/info", timeout=60).json()["inline"]
    return list(info["properties"][0]["values"])


def mesh_cache_path(source: str, name: str) -> Path:
    """Cache file for one neuropil mesh, unique even on case-insensitive filesystems (AL(R) and aL(R) both exist)."""
    digest = hashlib.sha1(name.encode("utf-8")).hexdigest()[:8]
    return MESH_CACHE / source / f"{name}.{digest}.ngmesh"


def load_mesh(source: str, name: str) -> tuple[np.ndarray, np.ndarray] | None:
    """Vertices (nm) and triangles of one neuropil, cached on disk; None when no mesh is published."""
    path = mesh_cache_path(source, name)
    path.parent.mkdir(parents=True, exist_ok=True)
    if not path.exists():
        response = requests.get(f"{MESH_SOURCES[source]}/mesh/{urllib.parse.quote(name)}.ngmesh", timeout=600)
        if response.status_code == 404:
            return None
        response.raise_for_status()
        path.write_bytes(response.content)
    raw = path.read_bytes()
    count = int(np.frombuffer(raw[:4], np.uint32)[0])
    vertices = np.frombuffer(raw[4 : 4 + 12 * count], np.float32).reshape(-1, 3).astype(np.float64)
    faces = np.frombuffer(raw[4 + 12 * count :], np.uint32).reshape(-1, 3).astype(np.int64)
    return vertices, faces


def load_meshes(names: set[str]) -> dict[str, tuple[np.ndarray, np.ndarray]]:
    """Every requested neuropil that has a published mesh, from the brain or the nerve cord source."""
    meshes = {}
    for source in MESH_SOURCES:
        for name in mesh_names(source):
            if name in names and name not in meshes:
                mesh = load_mesh(source, name)
                if mesh is not None:
                    meshes[name] = mesh
    return meshes


def simplify(vertices: np.ndarray, faces: np.ndarray, cell: float) -> tuple[np.ndarray, np.ndarray]:
    """Collapse vertices sharing a cubic cell of side ``cell`` to their centroid and drop collapsed triangles."""
    keys = np.floor(vertices / cell).astype(np.int64)
    _, cluster, counts = np.unique(keys, axis=0, return_inverse=True, return_counts=True)
    cluster = cluster.ravel()
    centroids = np.zeros((len(counts), 3))
    np.add.at(centroids, cluster, vertices)
    centroids /= counts[:, None]
    remapped = cluster[faces]
    collapsed = ((remapped[:, 0] == remapped[:, 1]) | (remapped[:, 1] == remapped[:, 2])
                 | (remapped[:, 0] == remapped[:, 2]))
    remapped = remapped[~collapsed]
    _, first = np.unique(np.sort(remapped, axis=1), axis=0, return_index=True)
    return centroids, remapped[np.sort(first)]


def rotation(pitch: float, yaw: float) -> np.ndarray:
    """Rotation for a pitch about the left-right axis followed by a yaw about the vertical axis."""
    p, y = np.radians(pitch), np.radians(yaw)
    about_x = np.array([[1, 0, 0], [0, np.cos(p), np.sin(p)], [0, -np.sin(p), np.cos(p)]])
    about_y = np.array([[np.cos(y), 0, np.sin(y)], [0, 1, 0], [-np.sin(y), 0, np.cos(y)]])
    return about_y @ about_x


def ramp_position(value: float, vmax: float) -> float:
    """Position on the color ramp for an impact value; the gamma spreads a heavy-tailed distribution."""
    return 0.08 + 0.92 * min(value / vmax, 1.0) ** GAMMA


def shaded_faces(meshes: dict, base_colors: dict, pitch: float, yaw: float) -> tuple:
    """Screen-space triangles and their shaded colors, sorted back to front."""
    light = np.array([-0.4, -0.5, -0.77])
    light /= np.linalg.norm(light)
    view = rotation(pitch, yaw)
    drawn = {name: mesh for name, mesh in meshes.items() if name in base_colors}
    center = np.concatenate([v for v, _ in drawn.values()]).mean(axis=0)
    polygons, colors, depths = [], [], []
    for name, (vertices, faces) in drawn.items():
        v, f = simplify(vertices, faces, CLUSTER_NM)
        triangles = ((v - center) @ view.T)[f]
        normals = np.cross(triangles[:, 1] - triangles[:, 0], triangles[:, 2] - triangles[:, 0])
        normals /= np.linalg.norm(normals, axis=1, keepdims=True) + 1e-12
        lambert = np.abs(normals @ light)
        base = np.asarray(to_rgb(base_colors[name]))
        polygons.append(triangles[:, :, :2] * [1, -1])
        colors.append(np.clip(base * (0.45 + 0.55 * lambert)[:, None] + 0.12 * lambert[:, None] ** 10, 0, 1))
        depths.append(triangles[:, :, 2].mean(axis=1))
    order = np.argsort(-np.concatenate(depths))
    return np.concatenate(polygons)[order], np.concatenate(colors)[order], len(drawn)


def render(meshes: dict, impact: pd.Series, headline: dict, path, pitch: float = 18.0, yaw: float = 0.0) -> None:
    """Orthographic view of the whole CNS, painted back to front, with a title block and a color scale."""
    sans, mono = register()
    vmax = float(np.ceil(impact.max() * 20) / 20)
    base_colors = {name: RAMP(ramp_position(value, vmax)) for name, value in impact.items() if name in meshes}
    base_colors.update({name: UNSCORED_COLOR for name in UNSCORED_ROIS if name in meshes})
    polygons, colors, rendered = shaded_faces(meshes, base_colors, pitch, yaw)

    scale = SUPERSAMPLE
    width, height = (side * scale for side in HERO_SIZE)
    fig = plt.figure(figsize=(width / 100, height / 100), dpi=100, facecolor=PAPER)
    ax = fig.add_axes([0.30, 0.02, 0.68, 0.96], facecolor=PAPER)
    ax.add_collection(PolyCollection(polygons, facecolors=colors, edgecolors=colors, linewidths=0.4,
                                     antialiased=False))
    corners = polygons.reshape(-1, 2)
    ax.set_xlim(corners[:, 0].min(), corners[:, 0].max())
    ax.set_ylim(corners[:, 1].min(), corners[:, 1].max())
    ax.set_aspect("equal")
    ax.axis("off")

    fig.text(0.045, 0.90, "Fault Lines", color=INK, fontsize=44 * scale, fontfamily=sans, fontweight=600, va="top")
    fig.text(0.045, 0.835, "Attack tolerance of the complete\nDrosophila male CNS connectome",
             color=INK_SECONDARY, fontsize=17 * scale, fontfamily=sans, va="top", linespacing=1.5)
    statement = textwrap.fill(
        f"Removing {100 * headline['f_c']:.1f}% of cell types by {headline['strategy']} halves sensory-to-motor "
        f"flow capacity. Random removal needs {100 * headline['random']:.1f}%.", width=40)
    fig.text(0.045, 0.70, statement, color=INK, fontsize=15 * scale, fontfamily=mono, va="top", linespacing=1.7)
    fig.text(0.045, 0.45, "Each neuropil is shaded by the share of flow capacity\nlost when every cell type anchored "
             "there is removed from\nthe graph. The cervical connective, in gray, is not scored.",
             color=INK_SECONDARY, fontsize=13 * scale, fontfamily=sans, va="top", linespacing=1.6)

    ticks = [tick for tick in SCALE_TICKS if tick <= vmax]
    bar = fig.add_axes([0.045, 0.26, 0.20, 0.018])
    bar.imshow(np.linspace(0.08, 1.0, 256)[None, :], aspect="auto", cmap=RAMP, extent=[0.08, 1.0, 0, 1])
    bar.set_yticks([])
    bar.set_xticks([ramp_position(tick, vmax) for tick in ticks])
    bar.set_xticklabels([f"{100 * tick:g}%" for tick in ticks], fontfamily=mono, fontsize=10.5 * scale)
    bar.set_xlim(0.08, 1.0)
    bar.tick_params(colors=INK_SECONDARY, length=0, pad=6)
    for spine in bar.spines.values():
        spine.set_visible(False)
    fig.text(0.045, 0.222, f"flow capacity lost   ({rendered} regions drawn)", color=MUTED, fontsize=11 * scale,
             fontfamily=sans, va="top")
    fig.text(0.045, 0.06, "Data: male CNS connectome v1.0, HHMI Janelia FlyEM and Google Research\n"
             "(Berg et al., Cell 2026), CC-BY 4.0", color=MUTED, fontsize=11 * scale, fontfamily=sans, va="top",
             linespacing=1.6)

    fig.canvas.draw()
    image = Image.frombuffer("RGBA", fig.canvas.get_width_height(), fig.canvas.buffer_rgba()).convert("RGB")
    plt.close(fig)
    image.resize(HERO_SIZE, Image.LANCZOS).save(path, optimize=True)


def crop_regional_map(hero_path, path) -> None:
    """Cut the report's regional impact figure from the hero: the meshes, with the color scale beneath and no title."""
    hero = Image.open(hero_path).convert("RGB")
    if hero.size != HERO_SIZE:
        raise ValueError(f"Expected a {HERO_SIZE[0]}x{HERO_SIZE[1]} hero, got {hero.size[0]}x{hero.size[1]}")
    mesh, scale = hero.crop(MAP_MESH_BOX), hero.crop(MAP_SCALE_BOX)
    figure = Image.new("RGB", (mesh.width, mesh.height + scale.height), PAPER)
    figure.paste(mesh, (0, 0))
    figure.paste(scale, (0, mesh.height))
    figure.save(path, optimize=True)


def main() -> None:
    table = load_regional_impact()
    impact = table.set_index("neuropil")["flow_drop"]
    thresholds = json.loads((RESULTS / "critical_thresholds.json").read_text(encoding="utf-8"))["strategies"]
    worst = min((s for s in thresholds if s != "random"), key=lambda s: thresholds[s]["f_c"])
    headline = {"strategy": STRATEGY_LABELS[worst], "f_c": thresholds[worst]["f_c"],
                "random": thresholds["random"]["f_c"]}
    meshes = load_meshes(set(impact.index) | set(UNSCORED_ROIS))
    ASSETS.mkdir(exist_ok=True)
    render(meshes, impact, headline, ASSETS / "hero.png")
    crop_regional_map(ASSETS / "hero.png", PAPER_DIR / "regional_impact_map.png")
    missing = sorted(set(impact.index) - set(meshes))
    print(f"Rendered {len(meshes)} neuropils at {HERO_SIZE[0]}x{HERO_SIZE[1]}")
    print(f"No published mesh for {len(missing)} scored regions: {', '.join(missing)}")


if __name__ == "__main__":
    main()
