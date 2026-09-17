"""Render the one-page poster of the study at print size, and a smaller preview for the README."""

import argparse
import json
import re
from dataclasses import dataclass
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
from matplotlib.font_manager import FontProperties  # noqa: E402
from matplotlib.patches import Circle, PathPatch, Rectangle  # noqa: E402
from matplotlib.path import Path as MplPath  # noqa: E402
from PIL import Image  # noqa: E402
from scipy import ndimage, stats  # noqa: E402

from pipeline.common import ASSETS, DATA, RESULTS, ROOT  # noqa: E402
from pipeline.figures import STRATEGY_COLORS  # noqa: E402
from pipeline.qr_code import encode  # noqa: E402

WIDTH, HEIGHT = 3508, 4960
PRINT_DPI = 300
PREVIEW_WIDTH = 880
MARGIN = 128
GUTTER = 88
COLUMNS = 3
BAND_HEIGHT = 1270
METHODS_HEIGHT = 230
COLUMN_TOP = BAND_HEIGHT + METHODS_HEIGHT + 175
CHECKS_TOP = 3930
FOOTER_TOP = 4580
OUT_DIR = ASSETS / "readme"
POSTER_PATH = OUT_DIR / "fault-lines-poster.png"
PREVIEW_PATH = OUT_DIR / "poster-preview.png"

SITE_URL = "https://dhruvin-sarkar.github.io/fault-lines/"
REPO_URL = "https://github.com/dhruvin-sarkar/fault-lines"
AUTHOR = "Dhruvin Sarkar"
TYPED_NEURONS = 164506

FIELD = "#000000"
FIELD_TISSUE = "#0b0f12"
FIELD_RULE = "#242a2e"
FIELD_INK = "#e8edef"
FIELD_INK_2 = "#9ba5aa"
FIELD_INK_3 = "#7a858a"
FIELD_LIVE = "#b9dcff"
SIGNAL_GLOW = "#ff4b63"
PAPER = "#f3f5f5"
PAPER_RAISED = "#fbfcfc"
WASH = "#e5e9ea"
RULE = "#d3d9db"
RULE_STRONG = "#a9b2b6"
INK = "#0e1214"
INK_2 = "#444e53"
INK_3 = "#5b666b"
SIGNAL = "#c21f3a"
SIGNAL_SOFT = "#f6d5db"
# Darker strategy colours for text on paper, each at least 4.5:1 against PAPER, as on the site.
STRATEGY_INK = {
    "sm_betweenness": "#1e6ecb",
    "betweenness": "#c34500",
    "pagerank": "#007e56",
    "out_strength": "#966505",
    "in_strength": "#b24b74",
    "random": "#687075",
}
STRATEGY_ORDER = ("out_strength", "betweenness", "sm_betweenness", "in_strength", "pagerank", "random")
STRATEGY_NAMES = {
    "random": "random",
    "out_strength": "weighted out-degree",
    "in_strength": "weighted in-degree",
    "betweenness": "betweenness",
    "pagerank": "PageRank",
    "sm_betweenness": "sensory-motor betweenness",
}
SUPERCLASS_NAMES = {
    "descending_neuron": "descending neurons",
    "vnc_sensory": "nerve cord sensory",
    "cb_intrinsic": "central brain intrinsic",
    "vnc_intrinsic": "nerve cord intrinsic",
    "ascending_neuron": "ascending neurons",
    "cb_sensory": "central brain sensory",
    "vnc_motor": "nerve cord motor",
    "sensory_ascending": "ascending sensory",
    "ol_intrinsic": "optic lobe intrinsic",
    "cb_motor": "central brain motor",
    "visual_projection": "visual projection",
    "visual_centrifugal": "visual centrifugal",
    "vnc_efferent": "nerve cord efferent",
}

FONTSOURCE = ROOT / "web" / "node_modules" / "@fontsource-variable"
FONT_DIR = DATA / "fonts" / "poster"
SERIF_ROMAN = "source-serif-4/files/source-serif-4-latin-opsz-normal.woff2"
SERIF_ITALIC = "source-serif-4/files/source-serif-4-latin-opsz-italic.woff2"
SANS_ROMAN = "archivo/files/archivo-latin-wdth-normal.woff2"
SANS_ITALIC = "archivo/files/archivo-latin-wdth-italic.woff2"
FACES = {
    "display": (SERIF_ROMAN, {"wght": 400, "opsz": 60}),
    "serif": (SERIF_ROMAN, {"wght": 400, "opsz": 12}),
    "serif_bold": (SERIF_ROMAN, {"wght": 600, "opsz": 12}),
    "serif_italic": (SERIF_ITALIC, {"wght": 400, "opsz": 12}),
    "deck": (SERIF_ITALIC, {"wght": 400, "opsz": 36}),
    "sans": (SANS_ROMAN, {"wght": 400, "wdth": 100}),
    "sans_medium": (SANS_ROMAN, {"wght": 500, "wdth": 100}),
    "sans_bold": (SANS_ROMAN, {"wght": 600, "wdth": 100}),
    "sans_italic": (SANS_ITALIC, {"wght": 400, "wdth": 100}),
}
TABULAR_FACES = ("sans", "sans_medium", "sans_bold", "sans_italic")
# Static Archivo files that pipeline.fonts caches, by family name, for when the variable fonts cannot be read.
CACHED_SANS = {"sans": "Archivo", "sans_medium": "Archivo Medium", "sans_bold": "Archivo SemiBold"}
_font_paths: dict[str, Path | None] = dict.fromkeys(FACES)


# Layout and formatting

def column_edges(width: float, margin: float, gutter: float, n: int) -> list[tuple[float, float]]:
    """Left and right edge of each of ``n`` equal columns between the margins."""
    column = (width - 2 * margin - (n - 1) * gutter) / n
    return [(margin + i * (column + gutter), margin + i * (column + gutter) + column) for i in range(n)]


def split_cells(x0: float, x1: float, n: int, gap: float) -> list[tuple[float, float]]:
    """Divide [x0, x1] into ``n`` equal cells separated by ``gap``."""
    cell = (x1 - x0 - (n - 1) * gap) / n
    return [(x0 + i * (cell + gap), x0 + i * (cell + gap) + cell) for i in range(n)]


def linear(d0: float, d1: float, r0: float, r1: float):
    """Map the data interval [d0, d1] onto the drawing interval [r0, r1]."""
    return lambda v: r0 + (np.asarray(v, dtype=float) - d0) / (d1 - d0) * (r1 - r0)


def log1p_scale(top: float, r0: float, r1: float):
    """Map counts in [0, top] onto [r0, r1] by log10(1 + v), so zero stays on the axis."""
    return lambda v: r0 + np.log10(1 + np.asarray(v, dtype=float)) / np.log10(1 + top) * (r1 - r0)


def spread_labels(positions: list[float], gap: float) -> list[float]:
    """Push sorted label positions apart so neighbours are at least ``gap`` apart, keeping their order."""
    out: list[float] = []
    for p in positions:
        out.append(p if not out else max(p, out[-1] + gap))
    return out


def pct(fraction: float, digits: int = 1) -> str:
    """A fraction as a percentage, e.g. 0.0411 as '4.1%', with halves rounded up as printed tables do."""
    return f"{round(100 * fraction + 1e-9, digits):.{digits}f}%"


def count(n: float) -> str:
    """An integer with thousands separators."""
    return f"{int(round(n)):,}"


def p_value(p: float, digits: int = 2) -> str:
    """A p value to ``digits`` significant figures, or a bound below 0.001."""
    if p < 0.001:
        return "< 0.001"
    return f"{p:#.{digits}g}"


def ordinal(n: int) -> str:
    """1st, 2nd, 3rd, 4th, 11th, 21st."""
    suffix = "th" if 10 <= n % 100 <= 20 else {1: "st", 2: "nd", 3: "rd"}.get(n % 10, "th")
    return f"{n}{suffix}"


def wrap_widths(widths: list[float], space: float, limit: float) -> list[list[int]]:
    """Greedy line breaks: indices of the words on each line, given word widths and the space width."""
    lines: list[list[int]] = []
    current: list[int] = []
    used = 0.0
    for i, w in enumerate(widths):
        needed = w if not current else used + space + w
        if current and needed > limit:
            lines.append(current)
            current, used = [i], w
        else:
            current.append(i)
            used = needed
    if current:
        lines.append(current)
    return lines


MARKUP = re.compile(r"\*\*|\*|\^[^^]*\^|~[^~]*~|\s+|[^*^~\s]+")


def parse_markup(text: str) -> list[list[tuple[str, str]]]:
    """Words of ``text`` as runs of (text, style).

    ``**bold**`` and ``*italic*`` toggle styles; ``^1^`` is a superscript and ``~c~`` a subscript, both
    attached to the preceding characters without a space.
    """
    words: list[list[tuple[str, str]]] = []
    current: list[tuple[str, str]] = []
    bold = italic = False
    for token in MARKUP.findall(text):
        if token == "**":
            bold = not bold
        elif token == "*":
            italic = not italic
        elif token.isspace():
            if current:
                words.append(current)
                current = []
        elif token.startswith("^"):
            current.append((token[1:-1], "sup"))
        elif token.startswith("~"):
            current.append((token[1:-1], "sub"))
        else:
            current.append((token, "bold" if bold else "italic" if italic else "regular"))
    if current:
        words.append(current)
    return words


def half_flow_batch(flow: list[float], intact: float) -> int | None:
    """First batch at which flow falls below half its intact value, or None if it never does."""
    for i, value in enumerate(flow):
        if value < intact / 2:
            return i
    return None


def svg_path(d: str) -> MplPath:
    """Matplotlib path from the absolute M/L/Z subset of SVG path data."""
    vertices, codes = [], []
    start = (0.0, 0.0)
    for command, body in re.findall(r"([MLZ])([^MLZ]*)", d):
        if command == "Z":
            vertices.append(start)
            codes.append(MplPath.CLOSEPOLY)
            continue
        numbers = [float(v) for v in re.findall(r"-?\d+(?:\.\d+)?", body)]
        for i in range(0, len(numbers), 2):
            point = (numbers[i], numbers[i + 1])
            if command == "M" and i == 0:
                start = point
                codes.append(MplPath.MOVETO)
            else:
                codes.append(MplPath.LINETO)
            vertices.append(point)
    return MplPath(vertices, codes)


def fit_box(bounds, width: float, height: float) -> tuple[float, float, float]:
    """Scale and offsets that fit ``bounds`` (x0, y0, x1, y1) centred in a width by height box."""
    x0, y0, x1, y1 = bounds
    scale = min(width / (x1 - x0), height / (y1 - y0))
    return scale, (width - (x1 - x0) * scale) / 2 - x0 * scale, (height - (y1 - y0) * scale) / 2 - y0 * scale


def ccdf(values) -> tuple[np.ndarray, np.ndarray]:
    """Distinct positive values and the share of positive values at least that large."""
    v = np.sort(np.asarray(values, dtype=float))
    v = v[v > 0]
    distinct = np.unique(v)
    share = 1 - np.searchsorted(v, distinct, side="left") / len(v)
    return distinct, share


# Fonts

def _tabular(ttfont) -> None:
    """Point the digits at their tabular glyphs so columns of numbers align."""
    if "GSUB" not in ttfont:
        return
    mapping: dict[str, str] = {}
    gsub = ttfont["GSUB"].table
    for record in gsub.FeatureList.FeatureRecord:
        if record.FeatureTag != "tnum":
            continue
        for index in record.Feature.LookupListIndex:
            for subtable in gsub.LookupList.Lookup[index].SubTable:
                subtable = getattr(subtable, "ExtSubTable", subtable)
                mapping.update(getattr(subtable, "mapping", None) or {})
    for table in ttfont["cmap"].tables:
        table.cmap = {code: mapping.get(name, name) for code, name in table.cmap.items()}


def build_fonts(font_dir: Path = FONT_DIR) -> dict[str, Path | None]:
    """Static TTF instances of Source Serif 4 and Archivo cut from the site's variable fonts.

    Reading WOFF2 needs the ``brotli`` module. Instances already in ``font_dir`` are reused. A face that
    cannot be built falls back to the static Archivo files cached by ``pipeline.fonts``, then to matplotlib's
    default serif or sans-serif.
    """
    from fontTools.ttLib import TTFont
    from fontTools.varLib import instancer

    font_dir.mkdir(parents=True, exist_ok=True)
    for role, (source, axes) in FACES.items():
        target = font_dir / f"{role}.ttf"
        if not target.exists():
            try:
                ttfont = instancer.instantiateVariableFont(TTFont(FONTSOURCE / source), axes)
                ttfont.flavor = None
                if role in TABULAR_FACES:
                    _tabular(ttfont)
                ttfont.save(target)
            except Exception as error:  # a missing font file or a missing brotli module
                print(f"Could not build the {role} face: {error}")
                continue
        _font_paths[role] = target
    if any(path is None for path in _font_paths.values()):
        cached = {TTFont(path)["name"].getDebugName(1): path for path in sorted((DATA / "fonts").glob("*.ttf"))}
        for role, family in CACHED_SANS.items():
            if _font_paths[role] is None:
                _font_paths[role] = cached.get(family)
    for role, path in _font_paths.items():
        fallback = "serif" if role in ("display", "serif", "serif_bold", "serif_italic", "deck") else "sans-serif"
        print(f"{role:>13}: {path.name if path else 'matplotlib default ' + fallback}")
    return dict(_font_paths)


def font(role: str, size: float) -> FontProperties:
    """FontProperties for a poster face at ``size`` pixels."""
    path = _font_paths.get(role)
    if path is not None:
        return FontProperties(fname=path, size=size)
    serif = role in ("display", "serif", "serif_bold", "serif_italic", "deck")
    return FontProperties(family="serif" if serif else "sans-serif", size=size,
                          weight="bold" if role.endswith("bold") else "normal",
                          style="italic" if role.endswith("italic") or role == "deck" else "normal")


# Drawing

STYLE_ROLES = {
    "serif": {"regular": "serif", "bold": "serif_bold", "italic": "serif_italic"},
    "sans": {"regular": "sans", "bold": "sans_bold", "italic": "sans_italic"},
    "deck": {"regular": "deck", "bold": "deck", "italic": "deck"},
}


@dataclass
class Frame:
    """A chart area with its data scales."""

    x0: float
    y0: float
    x1: float
    y1: float
    sx: object
    sy: object


class Sheet:
    """The poster canvas: one unit per pixel, origin at the top left, text placed on its baseline."""

    def __init__(self, width: int, height: int, ground: str = PAPER) -> None:
        self.fig = plt.figure(figsize=(width / 72, height / 72), dpi=72, facecolor=ground)
        self.ax = self.fig.add_axes((0, 0, 1, 1))
        self.ax.set_xlim(0, width)
        self.ax.set_ylim(height, 0)
        self.ax.axis("off")
        self._renderer = self.fig.canvas.get_renderer()
        self._widths: dict[tuple, float] = {}

    def width_of(self, s: str, size: float, role: str) -> float:
        key = (s, size, role)
        if key not in self._widths:
            self._widths[key] = self._renderer.get_text_width_height_descent(s, font(role, size), ismath=False)[0]
        return self._widths[key]

    def text(self, x, y, s, size, role="sans", color=INK, ha="left", zorder=6):
        return self.ax.text(x, y, s, fontproperties=font(role, size), color=color, ha=ha, va="baseline",
                            zorder=zorder)

    def rect(self, x0, y0, x1, y1, color, alpha=1.0, zorder=1) -> None:
        self.ax.add_patch(Rectangle((min(x0, x1), min(y0, y1)), abs(x1 - x0), abs(y1 - y0), facecolor=color,
                                    edgecolor="none", alpha=alpha, zorder=zorder))

    def line(self, xs, ys, color, width=2.0, dashes=None, alpha=1.0, zorder=3, cap="butt") -> None:
        (artist,) = self.ax.plot(xs, ys, color=color, linewidth=width, alpha=alpha, zorder=zorder,
                                 solid_capstyle=cap, solid_joinstyle="round")
        if dashes:
            artist.set_linestyle((0, dashes))

    def fill(self, xs, ys, color, alpha=1.0, zorder=2) -> None:
        self.ax.fill(xs, ys, color=color, alpha=alpha, linewidth=0, zorder=zorder)

    def dot(self, x, y, r, color, hollow=False, ground=PAPER, stroke=3.0, zorder=7) -> None:
        if hollow:
            self.ax.add_patch(Circle((x, y), r - stroke / 2, facecolor=ground, edgecolor=color, linewidth=stroke,
                                     zorder=zorder))
        else:
            self.ax.add_patch(Circle((x, y), r, facecolor=color, edgecolor="none", zorder=zorder))

    @staticmethod
    def _role(base: str, style: str) -> str:
        roles = STYLE_ROLES[base]
        return roles.get(style, roles["regular"])

    def paragraph(self, x, y, width, markup, size, base="serif", color=INK, leading=1.42, colors=None) -> float:
        """Wrap and draw ``markup`` with its first baseline at ``y``; returns the baseline after the last line."""
        words = parse_markup(markup)
        regular = self._role(base, "regular")
        space = self.width_of("a a", size, regular) - self.width_of("aa", size, regular)

        def run_size(style):
            return size * (0.62 if style in ("sup", "sub") else 1)

        widths = [sum(self.width_of(t, run_size(s), self._role(base, s)) for t, s in w) for w in words]
        for line in wrap_widths(widths, space, width):
            cursor = x
            for n, i in enumerate(line):
                for text, style in words[i]:
                    shift = -size * 0.36 if style == "sup" else size * 0.16 if style == "sub" else 0
                    role = self._role(base, style)
                    self.text(cursor, y + shift, text, run_size(style), role, (colors or {}).get(style, color))
                    cursor += self.width_of(text, run_size(style), role)
                if n < len(line) - 1:
                    cursor += space
            y += size * leading
        return y

    def image(self, array, x0, y0, x1, y1, zorder=2) -> None:
        self.ax.imshow(array, extent=(x0, x1, y1, y0), interpolation="antialiased", zorder=zorder, aspect="auto")

    def save(self, path: Path) -> None:
        self.fig.savefig(path, dpi=72, facecolor=self.fig.get_facecolor())
        plt.close(self.fig)


# Data

def load_json(name: str) -> dict | None:
    path = RESULTS / name
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else None


def load_results() -> dict:
    """Every result the poster draws on; an analysis whose output does not exist yet is None."""
    validation = (RESULTS / "null_model_validation.md").read_text(encoding="utf-8")
    planned = re.search(r"N = (\d+) randomized graphs", validation)
    return {
        "fragility": load_json("fragility_scores.json"),
        "thresholds": load_json("critical_thresholds.json"),
        "curves": pd.read_csv(RESULTS / "percolation_curves.csv"),
        "edges": load_json("edge_attack.json"),
        "structure": load_json("structure_profile.json"),
        "compartments": load_json("brain_vnc_comparison.json"),
        "avalanches": load_json("avalanche_analysis.json"),
        "bottleneck": load_json("hidden_bottleneck.json"),
        "pairs": load_json("synthetic_lethal_pairs.json"),
        "synergy": pd.read_csv(RESULTS / "synthetic_lethal_pairs.csv", usecols=["synergy"])["synergy"],
        "literature": load_json("literature_validation.json"),
        "atlas": load_json("type_atlas.json"),
        "atlas_types": pd.read_csv(RESULTS / "type_atlas.csv",
                                   usecols=["cell_type", "x", "y", "removed_out_strength", "silenced_out_strength"]),
        "regions": pd.read_csv(RESULTS / "regional_impact.csv"),
        "bilateral": load_json("bilateral_symmetry.json"),
        "null_model": load_json("null_model_summary.json"),
        "planned_nulls": int(planned.group(1)) if planned else None,
    }


def run_rows(curves: pd.DataFrame, strategy: str, trial: int = 0) -> pd.DataFrame:
    return curves[(curves["strategy"] == strategy) & (curves["trial"] == trial)].sort_values("batch")


def strategy_curves(curves: pd.DataFrame, intact: float, limit: float = 0.51) -> dict:
    """Normalized flow per strategy within the removal window; random as mean and 95% band over its trials."""
    out = {}
    window = curves[curves["fraction_removed"] <= limit]
    for strategy, rows in window.groupby("strategy"):
        if strategy == "random":
            grouped = rows.groupby("batch")
            values = grouped["flow"]
            n = values.count().to_numpy()
            mean = values.mean().to_numpy() / intact
            half = stats.t.ppf(0.975, n - 1) * values.std(ddof=1).to_numpy() / np.sqrt(n) / intact
            out[strategy] = {"x": grouped["fraction_removed"].mean().to_numpy(), "y": mean, "lo": mean - half,
                             "hi": mean + half}
        else:
            trial = rows[rows["trial"] == 0].sort_values("batch")
            out[strategy] = {"x": trial["fraction_removed"].to_numpy(), "y": trial["flow"].to_numpy() / intact}
    return out


def cut_off_at_half_flow(data: dict) -> dict[str, int | None]:
    """Surviving types with no sensory path at each strategy's first batch below half flow (run or trial 0)."""
    intact = data["thresholds"]["intact_flow"]
    out = {}
    for strategy, replay in data["atlas"]["replay"].items():
        batch = half_flow_batch(run_rows(data["curves"], strategy)["flow"].tolist(), intact)
        silenced = replay["silenced_types"]
        out[strategy] = silenced[batch] if batch is not None and batch < len(silenced) else None
    return out


def primary_avalanches(curves: pd.DataFrame, window: float = 0.5) -> np.ndarray:
    """Avalanche sizes of the pre-registered primary set: one run per strategy, batches up to the first past half."""
    sizes = []
    for strategy in STRATEGY_ORDER:
        rows = run_rows(curves, strategy)
        rows = rows[rows["batch"] >= 1]
        past = np.flatnonzero(rows["fraction_removed"].to_numpy() >= window)
        last = past[0] + 1 if len(past) else len(rows)
        sizes.append(rows["avalanche"].to_numpy()[:last])
    return np.concatenate(sizes)


# Anatomy

def _rgb(color: str) -> np.ndarray:
    return np.array([int(color[i:i + 2], 16) / 255 for i in (1, 3, 5)], dtype=np.float32)


def atlas_bounds(types: pd.DataFrame, outline: str, pad: float = 8.0) -> tuple[float, float, float, float]:
    """Bounding box (x0, y0, x1, y1) of the outline and every placed type, in atlas units."""
    numbers = np.array([float(v) for v in re.findall(r"-?\d+(?:\.\d+)?", outline)]).reshape(-1, 2)
    placed = types.dropna(subset=["x", "y"])
    return (min(numbers[:, 0].min(), placed["x"].min()) - pad, min(numbers[:, 1].min(), placed["y"].min()) - pad,
            max(numbers[:, 0].max(), placed["x"].max()) + pad, max(numbers[:, 1].max(), placed["y"].max()) + pad)


def disk(diameter: float) -> np.ndarray:
    """Square kernel of odd size holding a filled disc of ``diameter`` pixels, as ones and zeros."""
    radius = diameter / 2
    half = int(np.ceil(radius - 0.5))
    y, x = np.mgrid[-half:half + 1, -half:half + 1]
    return (x * x + y * y <= radius * radius).astype(np.float32)


def _splat(xs: np.ndarray, ys: np.ndarray, shape: tuple[int, int], diameter: float) -> np.ndarray:
    grid = np.zeros(shape, dtype=np.float32)
    ix = np.clip(np.round(xs).astype(int), 0, shape[1] - 1)
    iy = np.clip(np.round(ys).astype(int), 0, shape[0] - 1)
    np.add.at(grid, (iy, ix), 1.0)
    grid = ndimage.convolve(grid, disk(diameter), mode="constant")
    return ndimage.gaussian_filter(grid, 0.7)


def render_anatomy(data: dict, width: int, height: int) -> tuple[np.ndarray, dict]:
    """The CNS on the black field: neuropil outlines, every cell type as a glowing point, and in red the types
    weighted out-degree has removed by the batch where flow capacity first falls below half."""
    atlas, types = data["atlas"], data["atlas_types"]
    scale, ox, oy = fit_box(atlas_bounds(types, atlas["cns_outline"]), width, height)

    fig = plt.figure(figsize=(width / 72, height / 72), dpi=72, facecolor=FIELD)
    ax = fig.add_axes((0, 0, 1, 1))
    ax.set_xlim(0, width)
    ax.set_ylim(height, 0)
    ax.axis("off")
    for region in atlas["outlines"]:
        path = svg_path(region["path"])
        ax.add_patch(PathPatch(MplPath(path.vertices * scale + (ox, oy), path.codes), facecolor=FIELD_TISSUE,
                               edgecolor="#262e33", linewidth=1.5))
    whole = svg_path(atlas["cns_outline"])
    ax.add_patch(PathPatch(MplPath(whole.vertices * scale + (ox, oy), whole.codes), facecolor="none",
                           edgecolor="#3d474d", linewidth=2.4))
    fig.canvas.draw()
    base = np.asarray(fig.canvas.buffer_rgba())[:, :, :3].astype(np.float32) / 255
    plt.close(fig)

    run = run_rows(data["curves"], "out_strength")
    batch = half_flow_batch(run["flow"].tolist(), data["thresholds"]["intact_flow"])
    placed = types.dropna(subset=["x", "y"])
    removed = ((placed["removed_out_strength"] > 0) & (placed["removed_out_strength"] <= batch)).to_numpy()
    silenced = (~removed & (placed["silenced_out_strength"] >= 0)
                & (placed["silenced_out_strength"] <= batch)).to_numpy()
    live = ~removed & ~silenced
    px = placed["x"].to_numpy() * scale + ox
    py = placed["y"].to_numpy() * scale + oy
    shape = (height, width)
    dot = max(2.0, scale * 2.1)

    light = np.zeros((height, width, 3), dtype=np.float32)
    core = _splat(px[live], py[live], shape, dot)
    light += _rgb(FIELD_LIVE) * (0.5 * core + 1.2 * ndimage.gaussian_filter(core, 6))[:, :, None]
    core = _splat(px[silenced], py[silenced], shape, dot * 1.4)
    light += _rgb("#d8dee1") * (0.9 * core)[:, :, None]
    core = _splat(px[removed], py[removed], shape, dot * 2.4)
    light += _rgb(SIGNAL_GLOW) * (2.6 * core + 3.2 * ndimage.gaussian_filter(core, 6))[:, :, None]
    del core
    light = 1 - np.exp(-light)
    image = np.clip(base * (1 - light) + light, 0, 1)
    counts = {"placed": int(len(placed)), "removed": int(removed.sum()), "silenced": int(silenced.sum()),
              "batch": batch, "fraction": float(run["fraction_removed"].iloc[batch])}
    return image, counts


# Charts

TICK = 27
LABEL = 28
CAPTION = 29


def axis_frame(sheet: Sheet, x0, y0, x1, y1, xdom, ydom, xticks, yticks, xfmt, yfmt, xlabel=None,
               yscale=None) -> Frame:
    sx = linear(xdom[0], xdom[1], x0, x1)
    sy = yscale if yscale is not None else linear(ydom[0], ydom[1], y1, y0)
    for t in yticks:
        y = float(sy(t))
        sheet.line([x0, x1], [y, y], RULE, 1.5, zorder=1)
        sheet.text(x0 - 16, y + 9, yfmt(t), TICK, "sans", INK_3, ha="right")
    sheet.line([x0, x1], [y1, y1], RULE_STRONG, 2, zorder=2)
    for t in xticks:
        x = float(sx(t))
        sheet.line([x, x], [y1, y1 + 10], RULE_STRONG, 2)
        sheet.text(x, y1 + 44, xfmt(t), TICK, "sans", INK_3, ha="center")
    if xlabel:
        sheet.text((x0 + x1) / 2, y1 + 86, xlabel, LABEL, "sans", INK_2, ha="center")
    return Frame(x0, y0, x1, y1, sx, sy)


def chart_title(sheet: Sheet, x0, x1, y, title, note=None) -> None:
    sheet.text(x0, y, title, LABEL, "sans_bold", INK)
    if note:
        sheet.text(x1, y, note, LABEL, "sans", INK_3, ha="right")


def caption(sheet: Sheet, x0, x1, y, title, body) -> float:
    return sheet.paragraph(x0, y, x1 - x0, f"**{title}** {body}", CAPTION, "sans", INK_2, leading=1.4,
                           colors={"bold": INK})


def heading(sheet: Sheet, x0, y, text) -> float:
    sheet.text(x0, y, text, 88, "display", INK)
    return y + 84


def figure_percolation(sheet: Sheet, data: dict, x0, x1, y) -> float:
    intact = data["thresholds"]["intact_flow"]
    curves = strategy_curves(data["curves"], intact)
    fc = data["thresholds"]["strategies"]
    chart_title(sheet, x0, x1, y, "Flow capacity, share of intact", f"{count(intact)} routes intact")
    top, bottom = y + 50, y + 380
    frame = axis_frame(sheet, x0 + 80, top, x1, bottom, (0, 0.5), (0, 1), [0, 0.1, 0.2, 0.3, 0.4, 0.5],
                       [0, 0.5, 1], lambda t: pct(t, 0), lambda t: pct(t, 0), xlabel="Cell types removed")
    half = float(frame.sy(0.5))
    sheet.line([frame.x0, frame.x1], [half, half], SIGNAL, 2.5, dashes=(10, 8), zorder=4)
    sheet.text(frame.x1, half - 16, "flow halves", LABEL, "sans_medium", SIGNAL, ha="right")
    random = curves["random"]
    sheet.fill(np.r_[frame.sx(random["x"]), frame.sx(random["x"][::-1])],
               np.r_[frame.sy(random["hi"]), frame.sy(random["lo"][::-1])], WASH, zorder=2)
    for strategy in reversed(STRATEGY_ORDER):
        c = curves[strategy]
        sheet.line(frame.sx(c["x"]), frame.sy(np.clip(c["y"], 0, 1)), STRATEGY_COLORS[strategy],
                   5 if strategy == "out_strength" else 3.2, zorder=5, cap="round")
    for strategy in STRATEGY_ORDER:
        sheet.dot(float(frame.sx(fc[strategy]["f_c"])), half, 11, STRATEGY_COLORS[strategy], zorder=8)
    y = bottom + 136
    cells = split_cells(x0, x1, 2, 30)
    for i, strategy in enumerate(STRATEGY_ORDER):
        cx0, cx1 = cells[i % 2]
        row_y = y + (i // 2) * 46
        sheet.line([cx0, cx0 + 32], [row_y - 9, row_y - 9], STRATEGY_COLORS[strategy], 6)
        sheet.text(cx0 + 46, row_y, STRATEGY_NAMES[strategy], LABEL, "sans", INK)
        sheet.text(cx1, row_y, pct(fc[strategy]["f_c"]), LABEL, "sans_bold", STRATEGY_INK[strategy], ha="right")
    y += 2 * 46 + 66
    lo, hi = fc["random"]["f_c_ci95"]
    return caption(sheet, x0, x1, y, "Figure 1. Targeted removal halves routing within a few percent of types.",
                   "Batches of 1% of the remaining types, scores recomputed each time; dots mark where flow halves. "
                   f"Random: mean of {len(fc['random']['f_c_trials'])} runs, 95% band, threshold CI {pct(lo)} to "
                   f"{pct(hi)}.")


def figure_compartments(sheet: Sheet, data: dict, x0, x1, y) -> float:
    comp = data["compartments"]["compartments"]
    brain, vnc = comp["brain"]["f_c"], comp["vnc"]["f_c"]
    chart_title(sheet, x0, x1, y, "Types removed when flow halves")
    lx = x1 - sheet.width_of("nerve cord", TICK, "sans")
    sheet.text(lx, y, "nerve cord", TICK, "sans", INK_2)
    sheet.dot(lx - 24, y - 9, 11, INK_2)
    lx -= 70 + sheet.width_of("brain", TICK, "sans")
    sheet.text(lx, y, "brain", TICK, "sans", INK_2)
    sheet.dot(lx - 24, y - 9, 11, INK_2, hollow=True, stroke=4)
    top, row = y + 30, 44
    bottom = top + row * len(STRATEGY_ORDER)
    sx = linear(0, 0.35, x0 + 330, x1 - 12)
    for t in (0, 0.1, 0.2, 0.3):
        sheet.line([sx(t), sx(t)], [top, bottom], RULE, 1.5, zorder=1)
        sheet.text(float(sx(t)), bottom + 40, pct(t, 0), TICK, "sans", INK_3, ha="center")
    for i, strategy in enumerate(STRATEGY_ORDER):
        cy = top + row * i + row / 2
        sheet.text(x0, cy + 9, STRATEGY_NAMES[strategy], LABEL, "sans", INK)
        a, b = float(sx(brain[strategy])), float(sx(vnc[strategy]))
        sheet.line([a, b], [cy, cy], STRATEGY_COLORS[strategy], 5, alpha=0.5, zorder=4)
        sheet.dot(a, cy, 12, STRATEGY_COLORS[strategy], hollow=True, stroke=4.5)
        sheet.dot(b, cy, 12, STRATEGY_COLORS[strategy])
    return caption(sheet, x0, x1, bottom + 96, "Figure 2. The most damaging order depends on the circuit.",
                   f"The same protocol on the {count(comp['brain']['types'])} brain and "
                   f"{count(comp['vnc']['types'])} nerve cord types. Sensory-motor betweenness halves brain flow after "
                   f"{pct(brain['sm_betweenness'])} of types and nerve cord flow after {pct(vnc['sm_betweenness'])}; "
                   f"weighted in-degree does the reverse ({pct(brain['in_strength'])} and {pct(vnc['in_strength'])}).")


def figure_edges(sheet: Sheet, data: dict, x0, x1, y) -> float:
    edges = data["edges"]
    orders = edges["orders"]
    colors = {"strongest": "out_strength", "weakest": "pagerank", "random": "random"}
    names = {"strongest": "strongest first", "weakest": "weakest first", "random": "random order"}
    chart_title(sheet, x0, x1, y, "Flow capacity as connections are removed")
    top, bottom = y + 50, y + 270
    frame = axis_frame(sheet, x0 + 80, top, x1 - 230, bottom, (0, 0.5), (0, 1), [0, 0.1, 0.2, 0.3, 0.4, 0.5],
                       [0, 0.5, 1], lambda t: pct(t, 0), lambda t: pct(t, 0), xlabel="Connections removed")
    half = float(frame.sy(0.5))
    sheet.line([frame.x0, frame.x1], [half, half], SIGNAL, 2.5, dashes=(10, 8), zorder=4)
    ends = []
    for order in ("weakest", "random", "strongest"):
        o = orders[order]
        ys = np.asarray(o["flow"]) / edges["intact_flow"]
        sheet.line(frame.sx(o["fraction_removed"]), frame.sy(ys), STRATEGY_COLORS[colors[order]],
                   5 if order == "strongest" else 3.2, zorder=5, cap="round")
        ends.append((float(frame.sy(ys[-1])), order))
        if o["critical_fraction"] is not None:
            sheet.dot(float(frame.sx(o["critical_fraction"])), half, 11, STRATEGY_COLORS[colors[order]])
    ends.sort()
    for ypos, (_, order) in zip(spread_labels([e[0] for e in ends], 36), ends):
        sheet.text(frame.x1 + 22, ypos + 9, names[order], LABEL, "sans_medium", STRATEGY_INK[colors[order]])
    strongest, random = orders["strongest"], orders["random"]
    lo, hi = random["critical_fraction_range"]
    return caption(sheet, x0, x1, bottom + 136, "Figure 3. Heavy connections carry more routes, not all of them.",
                   f"With the strongest of {count(edges['edges'])} connections removed first, flow halves after "
                   f"{pct(strongest['critical_fraction'])}; in random order, after {pct(random['critical_fraction'])} "
                   f"({len(random['critical_fraction_trials'])} runs, {pct(lo)} to {pct(hi)}). Weakest first never "
                   "halves it within half of all connections.")


def figure_superclasses(sheet: Sheet, data: dict, x0, x1, y) -> float:
    rows = data["structure"]["superclass_impact"]
    chart_title(sheet, x0, x1, y, "Flow lost when a whole superclass is removed")
    lx = x1 - sheet.width_of("same-size random", TICK, "sans")
    sheet.text(lx, y, "same-size random", TICK, "sans", INK_2)
    sheet.rect(lx - 26, y - 24, lx - 18, y + 4, INK_3, zorder=6)
    top, row = y + 30, 40
    bottom = top + row * len(rows)
    sx = linear(0, 1, x0 + 320, x1 - 120)
    for t in (0, 0.25, 0.5, 0.75, 1):
        sheet.line([sx(t), sx(t)], [top, bottom], RULE, 1.5, zorder=1)
        sheet.text(float(sx(t)), bottom + 40, pct(t, 0), TICK, "sans", INK_3, ha="center")
    for i, r in enumerate(rows):
        cy = top + row * i + row / 2
        strong = r["p_value"] < 0.05 and r["flow_drop"] > r["random_mean"]
        sheet.text(x0, cy + 9, SUPERCLASS_NAMES.get(r["superclass"], r["superclass"]), LABEL, "sans",
                   INK if strong else INK_3)
        a, b = float(sx(r["random_mean"])), float(sx(r["flow_drop"]))
        sheet.line([a, b], [cy, cy], SIGNAL if strong else RULE_STRONG, 3, alpha=0.45 if strong else 1)
        sheet.rect(a - 4, cy - 15, a + 4, cy + 15, INK_3, zorder=5)
        sheet.dot(b, cy, 11, SIGNAL if strong else INK_3, hollow=not strong, stroke=4)
        sheet.text(x1, cy + 9, pct(r["flow_drop"]), LABEL, "sans_bold" if strong else "sans",
                   SIGNAL if strong else INK_3, ha="right")
    dn = next(r for r in rows if r["superclass"] == "descending_neuron")
    an = next(r for r in rows if r["superclass"] == "ascending_neuron")
    return caption(sheet, x0, x1, bottom + 96,
                   "Figure 4. Without the descending neurons, two thirds of the routes go.",
                   f"All {count(dn['types'])} descending neuron types cost {pct(dn['flow_drop'])} of flow; random "
                   f"sets of the same size cost {pct(dn['random_mean'])}. Ascending neurons, neither source nor sink, "
                   f"cost {pct(an['flow_drop'])} against {pct(an['random_mean'])}. Red: one-sided p < 0.05 over "
                   f"{data['structure']['random_draws']} draws.")


def figure_disconnection(sheet: Sheet, data: dict, x0, x1, y) -> float:
    replay = data["atlas"]["replay"]
    at_half = cut_off_at_half_flow(data)
    chart_title(sheet, x0, x1, y, "Surviving types with no path from sensory input")
    top, bottom = y + 50, y + 280
    frame = axis_frame(sheet, x0 + 100, top, x1, bottom, (0, 0.5), (0, 10000), [0, 0.1, 0.2, 0.3, 0.4, 0.5],
                       [0, 10, 100, 1000, 10000], lambda t: pct(t, 0), count, xlabel="Cell types removed",
                       yscale=log1p_scale(10000, bottom, top))
    for strategy in reversed(STRATEGY_ORDER):
        r = replay[strategy]
        sheet.line(frame.sx(r["fraction_removed"]), frame.sy(r["silenced_types"]), STRATEGY_COLORS[strategy],
                   5 if strategy == "sm_betweenness" else 3.2, zorder=5, cap="round")
    sm = replay["sm_betweenness"]
    jumps = np.diff(sm["silenced_types"])
    j = int(np.argmax(jumps))
    sheet.text(float(frame.sx(sm["fraction_removed"][j])) - 20, float(frame.sy(sm["silenced_types"][j + 1])) + 34,
               f"one batch cuts off {count(jumps[j])}", LABEL, "sans_medium", STRATEGY_INK["sm_betweenness"],
               ha="right")
    worst = max(v for v in at_half.values() if v is not None)
    return caption(sheet, x0, x1, bottom + 136, "Figure 5. Routing thins before anything is cut off.",
                   f"When flow halves, at most {count(worst)} of {count(data['atlas']['types'])} types have lost every "
                   f"sensory path, whatever the order. Under sensory-motor betweenness one batch, from "
                   f"{pct(sm['fraction_removed'][j])} to {pct(sm['fraction_removed'][j + 1])} removed, cuts off "
                   f"{count(jumps[j])} types at once. Colours as in Figure 1.")


def figure_regions(sheet: Sheet, data: dict, x0, x1, y, n: int = 6) -> float:
    regions = data["regions"].sort_values("flow_drop", ascending=False).head(n)
    chart_title(sheet, x0, x1, y, "Flow lost when a neuropil's types are removed")
    lx = x1 - sheet.width_of("same-size random", TICK, "sans")
    sheet.text(lx, y, "same-size random", TICK, "sans", INK_2)
    sheet.rect(lx - 26, y - 26, lx - 20, y + 6, INK, zorder=6)
    top, row = y + 30, 40
    bottom = top + row * n
    sx = linear(0, 0.4, x0 + 230, x1 - 120)
    for t in (0, 0.1, 0.2, 0.3, 0.4):
        sheet.line([sx(t), sx(t)], [top, bottom], RULE, 1.5, zorder=1)
        sheet.text(float(sx(t)), bottom + 40, pct(t, 0), TICK, "sans", INK_3, ha="center")
    for i, r in enumerate(regions.itertuples()):
        cy = top + row * i + row / 2
        strong = r.p_value < 0.05
        sheet.text(x0, cy + 9, r.neuropil, LABEL, "sans", INK if strong else INK_3)
        sheet.rect(float(sx(0)), cy - 13, float(sx(r.flow_drop)), cy + 13, SIGNAL if strong else RULE_STRONG,
                   zorder=3)
        m = float(sx(r.random_mean))
        sheet.rect(m - 3, cy - 20, m + 3, cy + 20, INK, zorder=5)
        sheet.text(x1, cy + 9, pct(r.flow_drop), LABEL, "sans_bold" if strong else "sans",
                   SIGNAL if strong else INK_3, ha="right")
    first = regions.iloc[0]
    significant = int((data["regions"]["p_value"] < 0.05).sum())
    return caption(sheet, x0, x1, bottom + 96, "Figure 6. The gnathal ganglia hold the most routes.",
                   f"Each type is anchored to the neuropil with most of its synapses. Removing the "
                   f"{count(first.n_types)} types of the {first.neuropil} costs {pct(first.flow_drop)} of flow, against "
                   f"{pct(first.random_mean)} for random sets of that size. {significant} of {len(data['regions'])} "
                   "neuropils reach p < 0.05, uncorrected; exploratory.")


def figure_core(sheet: Sheet, data: dict, x0, x1, y) -> float:
    s = data["structure"]
    counts = {int(k): v for k, v in s["coreness_counts"].items()}
    kmax = s["max_coreness"]
    chart_title(sheet, x0, x1, y, "Cell types by core number")
    top, bottom = y + 50, y + 290
    frame = axis_frame(sheet, x0 + 100, top, x1, bottom, (-0.5, kmax + 0.5), (0, 10000), [0, 5, 10, 15, 20],
                       [0, 10, 100, 1000, 10000], lambda t: str(int(t)), count,
                       yscale=log1p_scale(10000, bottom, top))
    bar = (frame.x1 - frame.x0) / (kmax + 1) * 0.7
    for k, v in counts.items():
        cx = float(frame.sx(k))
        sheet.rect(cx - bar / 2, float(frame.sy(v)), cx + bar / 2, bottom, INK if k == kmax else RULE_STRONG,
                   zorder=3)
    cx = float(frame.sx(kmax))
    sheet.text(cx - bar, float(frame.sy(counts[kmax])) + 26, f"{count(counts[kmax])} types, k = {kmax}", LABEL,
               "sans_bold", INK, ha="right")
    return bottom + 44


# Mini charts for the checks strip

def mini_strip(sheet: Sheet, x0, x1, y, values, median, color) -> None:
    sx = linear(0, 100, x0 + 8, x1 - 8)
    sheet.line([x0, x1], [y + 40, y + 40], RULE_STRONG, 2)
    for t in (0, 50, 100):
        sheet.line([sx(t), sx(t)], [y + 40, y + 50], RULE_STRONG, 2)
        sheet.text(float(sx(t)), y + 82, str(t), TICK, "sans", INK_3, ha="center")
    sheet.line([sx(median)] * 2, [y, y + 40], color, 3)
    for v in values:
        sheet.dot(float(sx(v)), y + 24, 10, color, hollow=True, stroke=3.5, zorder=8)


def mini_bottleneck(sheet: Sheet, x0, x1, y, candidates) -> None:
    sx = linear(0, 100, x0 + 160, x1 - 8)
    for t in (0, 50, 100):
        sheet.line([sx(t), sx(t)], [y - 4, y + 4 * 27 - 4], RULE, 1.5, zorder=1)
    for i, c in enumerate(candidates):
        cy = y + 10 + i * 27
        sheet.text(x0, cy + 8, c["cell_type"], 22, "sans", INK_2)
        a, b = float(sx(c["degree_pct"])), float(sx(c["sm_betweenness_pct"]))
        sheet.line([a, b], [cy, cy], SIGNAL, 3, alpha=0.4)
        sheet.dot(a, cy, 8, INK_3, hollow=True, stroke=3)
        sheet.dot(b, cy, 8, SIGNAL)


def mini_histogram(sheet: Sheet, x0, x1, y, series: pd.Series) -> None:
    values = series.value_counts().sort_index()
    lo, hi = int(values.index.min()), int(values.index.max())
    sx = linear(lo - 0.5, hi + 0.5, x0, x1)
    sy = log1p_scale(100000, y + 90, y)
    w = (x1 - x0) / (hi - lo + 1) * 0.72
    for v, n in values.items():
        cx = float(sx(v))
        color = SIGNAL if v > 0 else INK_3 if v < 0 else RULE_STRONG
        sheet.rect(cx - w / 2, float(sy(n)), cx + w / 2, y + 90, color, zorder=3)
    sheet.line([x0, x1], [y + 90, y + 90], RULE_STRONG, 2)
    for t in (lo, 0, hi):
        sheet.text(float(sx(t)), y + 124, f"{t:+d}" if t else "0", TICK, "sans", INK_3, ha="center")


def mini_ccdf(sheet: Sheet, x0, x1, y, sizes) -> None:
    xs, share = ccdf(sizes)
    sx = linear(0, np.log10(10000), x0 + 10, x1 - 10)
    sy = linear(-3, 0, y + 90, y)
    sheet.line([x0, x1], [y + 90, y + 90], RULE_STRONG, 2)
    sheet.line(sx(np.log10(xs)), sy(np.log10(share)), INK, 3.2, zorder=5)
    sheet.dot(float(sx(np.log10(xs[-1]))), float(sy(np.log10(share[-1]))), 9, STRATEGY_COLORS["sm_betweenness"])
    for t, label in ((0, "1"), (2, "100"), (4, "10,000")):
        sheet.text(float(sx(t)), y + 124, label, TICK, "sans", INK_3, ha="center")


def mini_stack(sheet: Sheet, x0, x1, y, parts) -> None:
    total = sum(n for _, n, _ in parts)
    cursor = x0
    for label, n, color in parts:
        w = (x1 - x0) * n / total
        sheet.rect(cursor, y + 20, cursor + max(w, 3), y + 62, color, zorder=3)
        cursor += w
    cursor = x0
    for i, (label, n, color) in enumerate(parts):
        sheet.text(x0 if i == 0 else x1 if i == 2 else (x0 + x1) / 2, y + 102, f"{count(n)} {label}", TICK,
                   "sans", INK_3, ha="left" if i == 0 else "right" if i == 2 else "center")


def mini_pending(sheet: Sheet, x0, x1, y) -> None:
    sheet.line([x0, x1, x1, x0, x0], [y, y, y + 90, y + 90, y], RULE_STRONG, 2, dashes=(8, 8))
    sheet.text((x0 + x1) / 2, y + 56, "running", LABEL, "sans_medium", INK_3, ha="center")


# Layout blocks

def draw_band(sheet: Sheet, data: dict, edges) -> None:
    sheet.rect(0, 0, WIDTH, BAND_HEIGHT, FIELD, zorder=0)
    x0 = MARGIN
    text_right = edges[0][1] + 150
    sheet.text(x0 - 12, 290, "Fault", 270, "display", FIELD_INK)
    sheet.text(x0 - 12, 535, "Lines", 270, "display", FIELD_INK)
    sheet.paragraph(x0, 645, text_right - x0, "How much of a fly's nervous system can be lost before its senses "
                    "no longer reach the neurons that move it?", 60, "deck", FIELD_INK, leading=1.24)

    th = data["thresholds"]["strategies"]
    lead, rand = th["out_strength"], th["random"]
    sheet.line([x0, text_right], [850, 850], FIELD_RULE, 2)
    cells = split_cells(x0, text_right, 2, 60)
    sheet.text(cells[0][0] - 4, 985, pct(lead["f_c"]), 150, "display", SIGNAL_GLOW)
    sheet.text(cells[1][0] - 4, 985, pct(rand["f_c"]), 150, "display", FIELD_INK_2)
    sheet.paragraph(cells[0][0], 1038, cells[0][1] - cells[0][0],
                    f"of {count(data['structure']['types'])} cell types, removed most output synapses first, halve "
                    "sensory-to-motor flow capacity", 29, "sans", FIELD_INK, leading=1.36)
    sheet.paragraph(cells[1][0], 1038, cells[1][1] - cells[1][0],
                    f"in random order, mean of {len(rand['f_c_trials'])} runs (95% CI {pct(rand['f_c_ci95'][0])} to "
                    f"{pct(rand['f_c_ci95'][1])})", 29, "sans", FIELD_INK_2, leading=1.36)

    sheet.line([x0, WIDTH - MARGIN], [1140, 1140], FIELD_RULE, 2)
    sheet.text(x0, 1212, AUTHOR, 38, "sans_bold", FIELD_INK)
    sheet.paragraph(x0 + sheet.width_of(AUTHOR, 38, "sans_bold") + 44, 1212, 2400,
                    "Complete male adult *Drosophila* CNS connectome, neuPrint male-cns:v1.0. Independent, "
                    "pre-registered analysis, not peer reviewed.", 29, "sans", FIELD_INK_2)
    sheet.text(WIDTH - MARGIN, 1212, SITE_URL.removeprefix("https://").rstrip("/"), 29, "sans_medium", FIELD_INK,
               ha="right")

    ax0, ax1, ay0, ay1 = edges[1][0] + 130, edges[2][0] + 270, 36, 1110
    image, counts = render_anatomy(data, int(ax1 - ax0), int(ay1 - ay0))
    sheet.image(image, ax0, ay0, ax1, ay1)
    del image

    lx0, lx1 = edges[2][0] + 380, WIDTH - MARGIN
    legend = [
        (FIELD_LIVE, f"**{count(counts['placed'] - counts['removed'] - counts['silenced'])} intact cell types,** one "
                     "point each, in a neuropil that holds its synapses"),
        (SIGNAL_GLOW, f"**{count(counts['removed'])} removed** by weighted out-degree by the batch where flow first "
                      f"falls below half ({pct(counts['fraction'])} of types)"),
        ("#d8dee1", f"**{count(counts['silenced'])} surviving types** already cut off from every sensory type"),
    ]
    y = 660
    y = sheet.paragraph(lx0, y, lx1 - lx0, "The male CNS seen from the front, brain above, nerve cord below.",
                        29, "sans", FIELD_INK_2, leading=1.36) + 30
    for color, text in legend:
        sheet.dot(lx0 + 11, y - 10, 11, color, ground=FIELD)
        y = sheet.paragraph(lx0 + 40, y, lx1 - lx0 - 40, text, 29, "sans", FIELD_INK_2, leading=1.36,
                            colors={"bold": FIELD_INK}) + 22


def draw_methods(sheet: Sheet, data: dict) -> None:
    y = BAND_HEIGHT
    fr = data["fragility"]
    g = fr["graph"]
    lit = data["literature"]["tests"]["primary"]["sm_betweenness"]
    steps = [
        ("Data", f"neuPrint male-cns:v1.0, {count(TYPED_NEURONS)} typed neurons, chemical synapses"),
        ("Graph", f"{count(g['cell_types'])} cell types, {count(g['edges'])} connections of at least 1% of the "
                  "target's input"),
        ("Terminals", f"{count(g['sensory_types'])} sensory sources, {count(g['motor_types'])} descending and "
                      "motor sinks"),
        ("Measure", f"flow capacity: {count(g['intact_flow'])} edge-disjoint sensory-to-motor paths when intact"),
        ("Remove", f"six orders, {pct(fr['protocol']['batch_fraction_of_remaining'], 0)} of remaining types a "
                   f"batch, scores recomputed, {fr['protocol']['random_trials']} random runs"),
        ("Validate", f"plan committed first; {data['planned_nulls']} degree-preserving nulls; "
                     f"{lit['n_curated']} published cell types"),
    ]
    sheet.rect(0, y, WIDTH, y + METHODS_HEIGHT, WASH, zorder=0)
    for i, ((label, body), (cx0, cx1)) in enumerate(zip(steps, split_cells(MARGIN, WIDTH - MARGIN, 6, 56))):
        sheet.text(cx0, y + 98, str(i + 1), 58, "display", SIGNAL)
        sheet.text(cx0 + 52, y + 88, label, 31, "sans_bold", INK)
        sheet.paragraph(cx0 + 52, y + 134, cx1 - cx0 - 52, body, 27, "sans", INK_2, leading=1.36)


def draw_column_one(sheet: Sheet, data: dict, x0, x1, y) -> float:
    g = data["fragility"]["graph"]
    th = data["thresholds"]["strategies"]
    y = heading(sheet, x0, y, "Question")
    y = sheet.paragraph(x0, y + 8, x1 - x0,
                        "A nervous system must carry signals from the senses to the neurons that move the body. How "
                        "much of that routing survives when parts of the wiring are lost, and does the order of loss "
                        "matter? The complete connectome of a male fruit fly, brain and nerve cord together,^1^ was "
                        "attacked in six orders fixed in advance. Removing the types with the most output synapses "
                        f"halves routing after {pct(th['out_strength']['f_c'])} of types; random loss needs "
                        f"{pct(th['random']['f_c'])}, the gap first seen in the Internet and the Web.^2^",
                        37, "serif", INK, leading=1.42)

    y = heading(sheet, x0, y + 84, "The graph")
    y = sheet.paragraph(x0, y + 8, x1 - x0,
                        f"Synapses between {count(TYPED_NEURONS)} typed neurons were summed into "
                        f"{count(g['cell_types'])} cell types, keeping {count(g['edges'])} connections that supply at "
                        "least 1% of a type's input. Routing is the flow capacity *F*: the most edge-disjoint paths "
                        "from sensory to descending and motor types.^3^", 37, "serif", INK, leading=1.42)
    s = data["structure"]
    tail = next(t for t in s["degree_tails"] if t["measure"].startswith("out-strength"))
    y = figure_core(sheet, data, x0, x1, y + 30)
    y = caption(sheet, x0, x1, y + 80, "Figure 7. A dense core with a thin rim.",
                f"{pct(s['types_in_deepest_core'] / s['types'])} of types share the deepest core. Output ranges from "
                f"a median of {count(tail['median'])} to {count(tail['max'])} synapses per type, a heavy tail better "
                "fit by a truncated than a pure power law:^4^ targeting works without the graph being scale-free.")

    y = heading(sheet, x0, y + 100, "Scope of the claims")
    shows = [
        "Sensory-to-motor routing in this wiring diagram tolerates random loss and fails fast under targeted loss.",
        "Capacity thins long before types are cut off.",
        "Which types are critical depends on the circuit and the measure.",
    ]
    limits = [
        "What a fly would do without these types: no activity is simulated.",
        "Synaptic sign, electrical synapses, modulation or plasticity.",
        "Other animals, or resolution finer than the cell type.",
    ]
    ends = []
    for (cx0, cx1), title, items in zip(split_cells(x0, x1, 2, 50), ("What this shows", "What this does not show"),
                                        (shows, limits)):
        yy = y + 8
        sheet.text(cx0, yy, title, CAPTION, "sans_bold", INK)
        sheet.line([cx0, cx1], [yy + 22, yy + 22], RULE_STRONG, 2)
        yy += 72
        for item in items:
            yy = sheet.paragraph(cx0, yy, cx1 - cx0, item, CAPTION, "sans", INK_2, leading=1.38) + 14
        ends.append(yy)
    return max(ends)


def draw_column_two(sheet: Sheet, data: dict, x0, x1, y) -> float:
    y = heading(sheet, x0, y, "Results")
    y = figure_percolation(sheet, data, x0, x1, y + 36)
    y = figure_compartments(sheet, data, x0, x1, y + 56)
    return figure_edges(sheet, data, x0, x1, y + 56)


def draw_column_three(sheet: Sheet, data: dict, x0, x1, y) -> float:
    y = heading(sheet, x0, y, "Where routing breaks")
    y = figure_superclasses(sheet, data, x0, x1, y + 36)
    y = figure_disconnection(sheet, data, x0, x1, y + 56)
    return figure_regions(sheet, data, x0, x1, y + 56)


def draw_checks(sheet: Sheet, data: dict) -> float:
    y = CHECKS_TOP
    sheet.line([MARGIN, WIDTH - MARGIN], [y, y], INK, 3)
    sheet.text(MARGIN, y + 90, "Checks and further findings", 64, "display", INK)
    lit = data["literature"]
    primary = lit["tests"]["primary"]["sm_betweenness"]
    control = lit["tests"]["with_positive_control"]["sm_betweenness"]
    bottleneck = data["bottleneck"]
    example = bottleneck["example"]
    pairs = data["pairs"]
    av = data["avalanches"]
    bil = data["bilateral"]
    nm = data["null_model"]

    cells = []
    cells.append((
        "Published neurons rank high", f"p = {p_value(primary['p_value'])}",
        lambda a, b, t: mini_strip(sheet, a, b, t, [v["sm_betweenness_percentile"] for v in
                                                    lit["curated_types"].values()],
                                   primary["median_percentile"], SIGNAL),
        f"{primary['n_curated']} behaviorally validated types sit at a median "
        f"{ordinal(round(primary['median_percentile']))} percentile of sensory-motor betweenness; "
        f"p = {p_value(control['p_value'])} with the motor neuron control.",
    ))
    cells.append((
        "A hidden bottleneck", example["cell_type"],
        lambda a, b, t: mini_bottleneck(sheet, a, b, t, bottleneck["candidates"]),
        f"{bottleneck['n_candidates']} types pair below-median degree (hollow) with top 1% sensory-motor "
        f"betweenness (red). Removing {example['cell_type']} costs only "
        f"{count(example['intact_flow'] - example['flow_after_removal'])} routes: detours exist.",
    ))
    cells.append((
        "Synthetic-lethal pairs", count(pairs["pairs_with_positive_synergy"]),
        lambda a, b, t: mini_histogram(sheet, a, b, t, data["synergy"]),
        f"of {count(pairs['pairs_evaluated'])} pairs lose more flow together than apart, by at most "
        f"{pairs['max_synergy']} routes. Synergy counts per value, log scale; all top pairs are sensory types.",
    ))
    cells.append((
        "Cascades", f"p = {av['primary']['bootstrap_p']:.3f}",
        lambda a, b, t: mini_ccdf(sheet, a, b, t, primary_avalanches(data["curves"])),
        f"for a power law in the primary set, {av['sensitivity_all_random_trials']['bootstrap_p']:.3f} "
        "with all random runs pooled; a lognormal fits as well, so scale-free cascades are not established.^4^",
    ))
    if bil:
        counts = bil["additivity_counts"]
        cells.append((
            "Left and right back each other up", count(counts["superadditive"]),
            lambda a, b, t: mini_stack(sheet, a, b, t, [("more", counts["superadditive"], SIGNAL),
                                                        ("additive", counts["additive"], RULE_STRONG),
                                                        ("less", counts["subadditive"], INK)]),
            f"of {count(bil['informative_types'])} types lose more with both sides removed than the two sides "
            f"alone add up to (one-sided Wilcoxon p {p_value(bil['both_greater_than_sum_of_singles']['p_value'])}). "
            f"For {bil['fully_insured_types']}, one side fully covers the other.",
        ))
    else:
        cells.append(("Left and right sides", "In progress", lambda a, b, t: mini_pending(sheet, a, b, t),
                      "Each type's left, right and both hemisphere nodes removed in turn."))
    if nm:
        strategies = nm["strategies"]
        significant = sum(1 for s in strategies.values() if s["auc_flow"]["significant"])
        cells.append(("Against randomized graphs", f"{significant} of {len(strategies)}",
                      lambda a, b, t: None,
                      f"removal orders find the real graph more fragile than {nm['n_nulls']} degree-preserving "
                      f"randomizations at a Bonferroni-corrected alpha of {nm['alpha']:.4f}."))
    else:
        cells.append(("Against randomized graphs", "In progress", lambda a, b, t: mini_pending(sheet, a, b, t),
                      f"{data['planned_nulls']} degree-preserving randomized graphs are going through the same "
                      "pre-registered protocol."))

    ends = []
    for (cx0, cx1), (title, number, chart, body) in zip(split_cells(MARGIN, WIDTH - MARGIN, 6, 60), cells):
        top = y + 158
        sheet.text(cx0, top, title, CAPTION, "sans_bold", INK)
        sheet.text(cx0, top + 90, number, 70, "display", INK_3 if number == "In progress" else INK)
        chart(cx0, cx1, top + 126)
        ends.append(sheet.paragraph(cx0, top + 300, cx1 - cx0, body, 27, "sans", INK_2, leading=1.38))
    return max(ends)


def draw_footer(sheet: Sheet) -> None:
    y = FOOTER_TOP
    sheet.line([MARGIN, WIDTH - MARGIN], [y, y], RULE_STRONG, 2)
    modules = encode(SITE_URL, "M")
    size = 290
    cell = size / len(modules)
    qy = y + 60
    verts, codes = [], []
    for r, c in zip(*np.nonzero(modules)):
        bx, by = MARGIN + c * cell, qy + r * cell
        verts += [(bx, by), (bx + cell, by), (bx + cell, by + cell), (bx, by + cell), (bx, by)]
        codes += [MplPath.MOVETO, MplPath.LINETO, MplPath.LINETO, MplPath.LINETO, MplPath.CLOSEPOLY]
    sheet.ax.add_patch(PathPatch(MplPath(verts, codes), facecolor=INK, edgecolor="none", zorder=6,
                                 antialiased=False))

    cols = split_cells(MARGIN + size + 60, WIDTH - MARGIN, 4, 70)
    x0, x1 = cols[0]
    sheet.text(x0, qy + 30, "Explore every result on the live site", CAPTION, "sans_bold", INK)
    sheet.text(x0, qy + 72, SITE_URL.removeprefix("https://").rstrip("/"), CAPTION, "sans_bold", SIGNAL)
    yy = sheet.paragraph(x0, qy + 122, x1 - x0, "Replay each attack on the atlas, break the graph yourself and read "
                         "the technical report.", 27, "sans", INK_2, leading=1.38)
    sheet.paragraph(x0, yy + 8, x1 - x0, "Data: HHMI Janelia FlyEM and Google Research, CC-BY 4.0. Code: MIT.", 25,
                    "sans", INK_3, leading=1.38)

    refs = [
        "Berg S et al. (2026). Sexual dimorphism in the complete *Drosophila* male central nervous system connectome. "
        "*Cell* 189(18):5504-5526. doi:10.1016/j.cell.2026.08.015",
        "Albert R, Jeong H, Barabási A-L (2000). Error and attack tolerance of complex networks. *Nature* "
        "406:378-382. doi:10.1038/35019019",
        "Ford LR, Fulkerson DR (1956). Maximal flow through a network. *Canadian Journal of Mathematics* 8:399-404.",
        "Clauset A, Shalizi CR, Newman MEJ (2009). Power-law distributions in empirical data. *SIAM Review* "
        "51(4):661-703. doi:10.1137/070710111",
    ]
    x0, x1 = cols[1]
    sheet.text(x0, qy + 30, "Cite as", CAPTION, "sans_bold", INK)
    sheet.paragraph(x0, qy + 76, x1 - x0, f"Sarkar D (2026). Fault Lines: attack tolerance and structural "
                    "robustness of the complete *Drosophila* male CNS connectome. "
                    f"{REPO_URL.removeprefix('https://')}", 27, "sans", INK_2, leading=1.38)
    groups = [refs[:2], refs[2:]]
    for (x0, x1), group, start in zip(cols[2:], groups, (1, 3)):
        yy = qy + 30
        for n, ref in enumerate(group, start=start):
            sheet.text(x0, yy, str(n), 25, "sans_bold", INK_3)
            yy = sheet.paragraph(x0 + 34, yy, x1 - x0 - 34, ref, 25, "sans", INK_2, leading=1.38) + 12


def render(output: Path = POSTER_PATH, preview: Path = PREVIEW_PATH) -> None:
    build_fonts()
    data = load_results()
    sheet = Sheet(WIDTH, HEIGHT)
    edges = column_edges(WIDTH, MARGIN, GUTTER, COLUMNS)
    draw_band(sheet, data, edges)
    draw_methods(sheet, data)
    bottoms = [draw(sheet, data, *edge, COLUMN_TOP)
               for draw, edge in zip((draw_column_one, draw_column_two, draw_column_three), edges)]
    checks_bottom = draw_checks(sheet, data)
    draw_footer(sheet)
    print(f"Column bottoms {[round(b) for b in bottoms]} (checks start {CHECKS_TOP}); "
          f"checks bottom {round(checks_bottom)} (footer starts {FOOTER_TOP})")
    output.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(output)
    with Image.open(output) as im:
        im = im.convert("RGB")
        im.save(output, dpi=(PRINT_DPI, PRINT_DPI), optimize=True)
        height = round(PREVIEW_WIDTH * im.height / im.width)
        im.resize((PREVIEW_WIDTH, height), Image.Resampling.LANCZOS).save(preview, optimize=True)
    print(f"Wrote {output} ({WIDTH} x {HEIGHT}) and {preview} ({PREVIEW_WIDTH} x {height})")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=POSTER_PATH)
    parser.add_argument("--preview", type=Path, default=PREVIEW_PATH)
    args = parser.parse_args()
    render(args.output, args.preview)


if __name__ == "__main__":
    main()
