"""Draw the README plates, figures and methods diagram as SVG, in light and dark variants, from the results.

Text is set as glyph outlines in the site's typefaces, Source Serif 4 and Archivo, so every viewer renders the same
shapes and widths. Each glyph is defined once per file and placed with ``<use>``.
"""

import argparse
import json
import math
import re
from collections.abc import Callable, Iterable, Sequence
from decimal import ROUND_HALF_UP, Decimal
from functools import cache
from html import escape
from pathlib import Path

import matplotlib
import numpy as np
import pandas as pd
from fontTools.pens.svgPathPen import SVGPathPen
from fontTools.ttLib import TTFont
from scipy import special, stats

from pipeline.common import ASSETS, RESULTS
from pipeline.figures import STRATEGY_COLORS

OUT_DIR = ASSETS / "readme"
WIDTH = 1760
MARGIN = 64

# Serif text at or above this size uses the display optical size.
DISPLAY_SIZE = 48
# DejaVu ships with matplotlib; it stands in for a face that cannot be built and for glyphs a face lacks.
FALLBACK_FILES = {
    "display": "DejaVuSerif.ttf",
    "serif": "DejaVuSerif.ttf",
    "serif_bold": "DejaVuSerif-Bold.ttf",
    "serif_italic": "DejaVuSerif-Italic.ttf",
    "sans": "DejaVuSans.ttf",
    "sans_medium": "DejaVuSans.ttf",
    "sans_bold": "DejaVuSans-Bold.ttf",
    "sans_italic": "DejaVuSans-Oblique.ttf",
}

THEMES = {
    "light": {
        "ground": "#f3f5f5",
        "border": None,
        "plate": "#fbfcfc",
        "track": "#e5e9ea",
        "rule": "#d3d9db",
        "rule_strong": "#a9b2b6",
        "ink": "#0e1214",
        "ink2": "#444e53",
        "ink3": "#5b666b",
        "axis": "#7b868b",
        "signal": "#c21f3a",
        "signal_soft": "#f6d5db",
        "ramp": ("#e5e9ea", "#efbcc5", "#c21f3a", "#5e0b1a"),
    },
    "dark": {
        "ground": "#000000",
        "border": "#242a2e",
        "plate": "#0a0d0f",
        "track": "#15191d",
        "rule": "#242a2e",
        "rule_strong": "#4a5358",
        "ink": "#e8edef",
        "ink2": "#9ba5aa",
        "ink3": "#7a858a",
        "axis": "#7a858a",
        "signal": "#ff4b63",
        "signal_soft": "#3a1119",
        "ramp": ("#1a2126", "#56202b", "#ff4b63", "#ffd9df"),
    },
}

# Darker inks of the strategy colors keep contrast on the light ground; brighter ones on black.
STRATEGY_INK = {
    "light": {
        "sm_betweenness": "#1e6ecb",
        "betweenness": "#c34500",
        "pagerank": "#007e56",
        "out_strength": "#966505",
        "in_strength": "#b24b74",
        "random": "#687075",
    },
    "dark": {
        "sm_betweenness": "#5aa6ff",
        "betweenness": "#ff8b52",
        "pagerank": "#33d99e",
        "out_strength": "#ffc13a",
        "in_strength": "#ff94c4",
        "random": "#9aa4aa",
    },
}
STRATEGY_NAMES = {
    "out_strength": "Weighted out-degree",
    "betweenness": "Betweenness",
    "sm_betweenness": "Sensory-motor betweenness",
    "in_strength": "Weighted in-degree",
    "pagerank": "PageRank",
    "random": "Random",
}
SUPERCLASS_NAMES = {
    "ascending_neuron": "Ascending",
    "cb_intrinsic": "Central brain intrinsic",
    "cb_motor": "Central brain motor",
    "cb_sensory": "Central brain sensory",
    "descending_neuron": "Descending",
    "ol_intrinsic": "Optic lobe intrinsic",
    "sensory_ascending": "Sensory ascending",
    "vnc_efferent": "Nerve cord efferent",
    "vnc_intrinsic": "Nerve cord intrinsic",
    "vnc_motor": "Nerve cord motor",
    "vnc_sensory": "Nerve cord sensory",
    "visual_centrifugal": "Visual centrifugal",
    "visual_projection": "Visual projection",
}
TERMINAL_SUPERCLASSES = {
    "cb_sensory", "ol_sensory", "vnc_sensory", "sensory_ascending", "sensory_descending",
    "descending_neuron", "cb_motor", "vnc_motor",
}
PREREGISTRATION_COMMIT = "0e72491"


# Formatting and geometry helpers.

def linear(d0: float, d1: float, r0: float, r1: float) -> Callable[[float], float]:
    """Map the data interval [d0, d1] onto the canvas interval [r0, r1]."""
    return lambda v: r0 + (v - d0) / (d1 - d0) * (r1 - r0)


def pct(value: float, digits: int = 1) -> str:
    """Format a fraction as a percentage, e.g. 0.0411 -> '4.1%'.

    Rounds half up from the shortest decimal form of ``value``, so a stored 0.2055 gives '20.6%' as the tables do.
    """
    scaled = Decimal(str(float(value))) * 100
    return f"{scaled.quantize(Decimal(1).scaleb(-digits), rounding=ROUND_HALF_UP)}%"


def count(value: float) -> str:
    """Format an integer with thousands separators."""
    return f"{int(round(value)):,}"


def fmt_p(p: float) -> str:
    """Format an empirical p-value to three decimals."""
    return f"{p:.3f}"


def num(value: float) -> str:
    """Compact coordinate for SVG output: one decimal, trailing zeros dropped."""
    text = f"{value:.1f}".rstrip("0").rstrip(".")
    return "0" if text in ("-0", "") else text


# Typefaces.

class Face:
    """A static TrueType font read for glyph outlines, advance widths and pair kerning."""

    def __init__(self, path: Path) -> None:
        self.font = TTFont(path, lazy=True)
        self.key = path.stem
        self.upem = self.font["head"].unitsPerEm
        self.cmap = self.font.getBestCmap()
        self.glyphs = self.font.getGlyphSet()
        self.metrics = self.font["hmtx"].metrics
        self._pairs = pair_subtables(self.font)
        self._kerning: dict[tuple[str, str], int] = {}

    def glyph(self, ch: str) -> str | None:
        return self.cmap.get(ord(ch))

    def advance(self, glyph: str) -> int:
        return self.metrics[glyph][0]

    def kern(self, left: str, right: str) -> int:
        """Horizontal adjustment between two glyphs from the first matching GPOS pair subtable, in font units."""
        key = (left, right)
        if key not in self._kerning:
            self._kerning[key] = pair_adjustment(self._pairs, left, right)
        return self._kerning[key]

    def outline(self, glyph: str) -> str:
        """SVG path data for ``glyph`` in font units, y up."""
        pen = SVGPathPen(self.glyphs, ntos=lambda v: num(v))
        self.glyphs[glyph].draw(pen)
        return pen.getCommands()


def pair_subtables(font: TTFont) -> list[tuple[object, dict[str, int]]]:
    """Pair-positioning subtables of the 'kern' feature, each with its coverage as a glyph-to-index map."""
    if "GPOS" not in font:
        return []
    table = font["GPOS"].table
    indices = sorted({i for record in table.FeatureList.FeatureRecord if record.FeatureTag == "kern"
                      for i in record.Feature.LookupListIndex})
    found = []
    for index in indices:
        lookup = table.LookupList.Lookup[index]
        for subtable in lookup.SubTable:
            kind = subtable.ExtensionLookupType if lookup.LookupType == 9 else lookup.LookupType
            subtable = getattr(subtable, "ExtSubTable", subtable)
            if kind == 2:
                found.append((subtable, {g: i for i, g in enumerate(subtable.Coverage.glyphs)}))
    return found


def pair_adjustment(subtables: Sequence[tuple[object, dict[str, int]]], left: str, right: str) -> int:
    """X advance adjustment for the glyph pair, 0 when no subtable covers it."""
    for subtable, coverage in subtables:
        if left not in coverage:
            continue
        if subtable.Format == 1:
            for record in subtable.PairSet[coverage[left]].PairValueRecord:
                if record.SecondGlyph == right:
                    return getattr(record.Value1, "XAdvance", None) or 0
            continue
        first = subtable.ClassDef1.classDefs.get(left, 0)
        second = subtable.ClassDef2.classDefs.get(right, 0)
        return getattr(subtable.Class1Record[first].Class2Record[second].Value1, "XAdvance", None) or 0
    return 0


@cache
def faces() -> dict[str, tuple[Face, ...]]:
    """Each text role's face followed by its DejaVu fallback."""
    from pipeline.poster import build_fonts

    built = build_fonts()
    fallback_dir = Path(matplotlib.get_data_path()) / "fonts" / "ttf"
    chains = {}
    for role, fallback in FALLBACK_FILES.items():
        chain = [Face(built[role])] if built.get(role) else []
        chains[role] = tuple(chain + [Face(fallback_dir / fallback)])
    return chains


def role_for(size: float, weight: int = 400, serif: bool = False, italic: bool = False) -> str:
    """Text role for a type size, weight, family and style."""
    if serif:
        if italic:
            return "serif_italic"
        if weight >= 600:
            return "serif_bold"
        return "display" if size >= DISPLAY_SIZE else "serif"
    if italic:
        return "sans_italic"
    if weight >= 600:
        return "sans_bold"
    return "sans_medium" if weight >= 500 else "sans"


def layout(s: str, size: float, role: str) -> tuple[list[tuple[Face, str, float]], float]:
    """Glyphs of ``s`` with their x offsets in canvas units, kerned within a face, and the total advance."""
    chain = faces()[role]
    placed: list[tuple[Face, str, float]] = []
    x = 0.0
    previous: tuple[Face, str] | None = None
    for ch in s:
        face, glyph = next(((f, g) for f in chain if (g := f.glyph(ch))), (chain[-1], ".notdef"))
        scale = size / face.upem
        if previous and previous[0] is face:
            x += face.kern(previous[1], glyph) * scale
        placed.append((face, glyph, x))
        x += face.advance(glyph) * scale
        previous = (face, glyph)
    return placed, x


def face_groups(placed: Sequence[tuple[Face, str, float]]) -> list[tuple[Face, list[tuple[str, float]]]]:
    """Consecutive glyphs that share a face, as (face, [(glyph, offset)]) groups."""
    groups: list[tuple[Face, list[tuple[str, float]]]] = []
    for face, glyph, offset in placed:
        if not groups or groups[-1][0] is not face:
            groups.append((face, []))
        groups[-1][1].append((glyph, offset))
    return groups


def text_width(s: str, size: float, bold: bool = False, serif: bool = False, italic: bool = False) -> float:
    """Rendered width of ``s`` in canvas units, measured from the glyph advances and kerning."""
    return layout(s, size, role_for(size, 700 if bold else 400, serif, italic))[1]


def wrap(s: str, size: float, max_width: float, bold: bool = False) -> list[str]:
    """Greedy word wrap of ``s`` so that each line fits ``max_width`` by the width estimate."""
    lines: list[str] = []
    current = ""
    for word in s.split():
        candidate = f"{current} {word}".strip()
        if current and text_width(candidate, size, bold) > max_width:
            lines.append(current)
            current = word
        else:
            current = candidate
    if current:
        lines.append(current)
    return lines


def spread(positions: Sequence[float], gap: float, lo: float = -math.inf, hi: float = math.inf) -> list[float]:
    """Move label positions apart so neighbours are at least ``gap`` apart, keeping the input order.

    Parameters: positions, the preferred coordinates; gap, the minimum separation; lo and hi, bounds.
    Returns the adjusted coordinates in the original order.
    """
    order = sorted(range(len(positions)), key=lambda i: positions[i])
    clusters: list[list[float]] = []
    for i in order:
        clusters.append([positions[i]])
        while len(clusters) > 1:
            prev, last = clusters[-2], clusters[-1]
            if cluster_start(prev, gap) + len(prev) * gap <= cluster_start(last, gap):
                break
            clusters[-2:] = [prev + last]
    placed = [cluster_start(c, gap) + k * gap for c in clusters for k in range(len(c))]
    for k in range(len(placed)):
        placed[k] = max(placed[k], lo if k == 0 else placed[k - 1] + gap)
    for k in range(len(placed) - 1, -1, -1):
        placed[k] = min(placed[k], hi if k == len(placed) - 1 else placed[k + 1] - gap)
    result = [0.0] * len(positions)
    for rank, i in enumerate(order):
        result[i] = placed[rank]
    return result


def italic_segments(s: str, words: Sequence[str]) -> list[tuple[str, bool]]:
    """Split ``s`` into (text, italic) runs, with every occurrence of ``words`` italic."""
    if not words:
        return [(s, False)] if s else []
    pattern = "(" + "|".join(re.escape(w) for w in words) + ")"
    return [(part, part in words) for part in re.split(pattern, s) if part]


def cluster_start(members: Sequence[float], gap: float) -> float:
    """First position of evenly spaced labels whose mean offset from ``members`` is zero."""
    return sum(m - k * gap for k, m in enumerate(members)) / len(members)


def hex_to_rgb(color: str) -> tuple[int, int, int]:
    """Parse '#rrggbb' into an (r, g, b) tuple."""
    color = color.lstrip("#")
    return int(color[0:2], 16), int(color[2:4], 16), int(color[4:6], 16)


def ramp_color(stops: Sequence[str], t: float) -> str:
    """Color at position ``t`` in [0, 1] along evenly spaced hex ``stops``."""
    t = min(max(t, 0.0), 1.0)
    scaled = t * (len(stops) - 1)
    i = min(int(scaled), len(stops) - 2)
    f = scaled - i
    a, b = hex_to_rgb(stops[i]), hex_to_rgb(stops[i + 1])
    return "#" + "".join(f"{round(x + (y - x) * f):02x}" for x, y in zip(a, b))


def impact_position(drop: float, top: float, gamma: float = 0.5) -> float:
    """Position on the color ramp for a share of flow lost, compressed by ``gamma`` up to ``top``."""
    return (max(drop, 0.0) / top) ** gamma if top > 0 else 0.0


def path_bounds(d: str) -> tuple[float, float, float, float]:
    """Bounding box (x0, y0, x1, y1) of an SVG path made of absolute M and L commands."""
    values = np.array([float(v) for v in re.findall(r"-?\d+(?:\.\d+)?", d)]).reshape(-1, 2)
    return values[:, 0].min(), values[:, 1].min(), values[:, 0].max(), values[:, 1].max()


def mean_ci(trials: np.ndarray, level: float = 0.95) -> tuple[np.ndarray, np.ndarray]:
    """Column means of a trials-by-points array and the half-width of their Student-t interval."""
    n = trials.shape[0]
    mean = trials.mean(axis=0)
    half = stats.t.ppf(0.5 + level / 2, n - 1) * trials.std(axis=0, ddof=1) / math.sqrt(n)
    return mean, half


def half_flow_batch(flow: Sequence[float], intact: float) -> int | None:
    """Index of the first batch whose flow falls below half of ``intact``, or None."""
    for i, value in enumerate(flow):
        if value < intact / 2:
            return i
    return None


# SVG drawing.

class Svg:
    """An SVG canvas 1760 units wide on a rounded ground, drawn in one theme."""

    def __init__(self, height: int, theme: str, field: bool = False) -> None:
        self.height = height
        self.theme_name = theme
        self.theme = THEMES[theme]
        self.field = field
        self.defs: list[str] = []
        self.style: list[str] = []
        self.parts: list[str] = []
        self.glyph_ids: dict[tuple[str, str], str] = {}
        self.glyph_defs: list[str] = []

    def c(self, name: str) -> str:
        """Resolve a theme token, a strategy id or a literal color."""
        if name in self.theme:
            return self.theme[name]
        if name in STRATEGY_INK[self.theme_name]:
            return STRATEGY_INK[self.theme_name][name]
        return name

    def glyph_ref(self, face: Face, glyph: str) -> str | None:
        """Id of the shared definition of ``glyph``, added on first use; None for a glyph with no outline."""
        key = (face.key, glyph)
        if key not in self.glyph_ids:
            outline = face.outline(glyph)
            self.glyph_ids[key] = f"g{len(self.glyph_defs)}" if outline else ""
            if outline:
                self.glyph_defs.append(f'<path id="{self.glyph_ids[key]}" d="{outline}"/>')
        return self.glyph_ids[key] or None

    def text(self, x: float, y: float, s: str, size: float = 26, color: str = "ink", weight: int = 400,
             anchor: str = "start", serif: bool = False, italic: bool = False,
             italic_words: Sequence[str] = ()) -> float:
        """Set ``s`` as outlines with its baseline at ``y``; returns the width drawn."""
        runs = [layout(part, size, role_for(size, weight, serif, italic or slanted))
                for part, slanted in italic_segments(s, italic_words)]
        width = sum(advance for _, advance in runs)
        start = x - {"start": 0, "middle": width / 2, "end": width}[anchor]
        for placed, advance in runs:
            for face, glyphs in face_groups(placed):
                self.glyph_group(face, glyphs, size, start, y, self.c(color))
            start += advance
        return width

    def glyph_group(self, face: Face, glyphs: Sequence[tuple[str, float]], size: float, x: float, y: float,
                    fill: str) -> None:
        """One group of glyphs from a single face, scaled from font units and offset from the first glyph."""
        scale = size / face.upem
        first = glyphs[0][1]
        uses = []
        for glyph, offset in glyphs:
            ref = self.glyph_ref(face, glyph)
            if ref:
                shift = round((offset - first) / scale)
                uses.append(f'<use href="#{ref}"' + (f' x="{shift}"' if shift else "") + "/>")
        if uses:
            self.parts.append(
                f'<g transform="matrix({scale:.6g} 0 0 {-scale:.6g} {num(x + first)} {num(y)})" '
                f'fill="{fill}">{"".join(uses)}</g>'
            )

    def line(self, x1: float, y1: float, x2: float, y2: float, color: str, width: float = 2,
             dash: str | None = None, opacity: float | None = None, cap: str | None = None) -> None:
        extra = f' stroke-dasharray="{dash}"' if dash else ""
        extra += f' stroke-opacity="{opacity}"' if opacity is not None else ""
        extra += f' stroke-linecap="{cap}"' if cap else ""
        self.parts.append(
            f'<path d="M{num(x1)} {num(y1)}L{num(x2)} {num(y2)}" stroke="{self.c(color)}" '
            f'stroke-width="{num(width)}" fill="none"{extra}/>'
        )

    def polyline(self, xs: Iterable[float], ys: Iterable[float], color: str, width: float = 3,
                 dash: str | None = None, opacity: float | None = None) -> None:
        points = list(zip(xs, ys))
        d = "M" + "L".join(f"{num(x)} {num(y)}" for x, y in points)
        extra = f' stroke-dasharray="{dash}"' if dash else ""
        extra += f' stroke-opacity="{opacity}"' if opacity is not None else ""
        self.parts.append(
            f'<path d="{d}" stroke="{self.c(color)}" stroke-width="{num(width)}" fill="none" '
            f'stroke-linejoin="round" stroke-linecap="round"{extra}/>'
        )

    def polygon(self, xs: Iterable[float], ys: Iterable[float], fill: str, opacity: float = 1) -> None:
        d = "M" + "L".join(f"{num(x)} {num(y)}" for x, y in zip(xs, ys)) + "Z"
        self.parts.append(f'<path d="{d}" fill="{self.c(fill)}" fill-opacity="{opacity}"/>')

    def rect(self, x: float, y: float, w: float, h: float, fill: str, rx: float = 0, stroke: str | None = None,
             stroke_width: float = 2, opacity: float | None = None) -> None:
        extra = f' rx="{num(rx)}"' if rx else ""
        extra += f' stroke="{self.c(stroke)}" stroke-width="{num(stroke_width)}"' if stroke else ""
        extra += f' fill-opacity="{opacity}"' if opacity is not None else ""
        self.parts.append(
            f'<rect x="{num(x)}" y="{num(y)}" width="{num(max(w, 0))}" height="{num(max(h, 0))}" '
            f'fill="{self.c(fill)}"{extra}/>'
        )

    def circle(self, cx: float, cy: float, r: float, fill: str, stroke: str | None = None, stroke_width: float = 3) -> None:
        extra = f' stroke="{self.c(stroke)}" stroke-width="{num(stroke_width)}"' if stroke else ""
        self.parts.append(f'<circle cx="{num(cx)}" cy="{num(cy)}" r="{num(r)}" fill="{self.c(fill)}"{extra}/>')

    def dot(self, cx: float, cy: float, r: float, color: str, hollow: bool = False, ring: float = 0) -> None:
        """Filled or hollow marker, with an optional ground-colored halo of width ``ring``."""
        ground = "#000000" if self.field else "ground"
        if ring:
            self.circle(cx, cy, r + ring, ground)
        if hollow:
            self.circle(cx, cy, r - 1.5, ground, stroke=color, stroke_width=3)
        else:
            self.circle(cx, cy, r, color)

    def raw(self, fragment: str) -> None:
        self.parts.append(fragment)

    def render(self, title: str, desc: str) -> str:
        """Complete SVG document with title, description, ground and every drawn part."""
        head = (
            f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {WIDTH} {self.height}" width="{WIDTH}" '
            f'height="{self.height}" role="img" aria-labelledby="t d">'
            f'<title id="t">{escape(title)}</title><desc id="d">{escape(desc)}</desc>'
        )
        style = f"<style>{''.join(self.style)}</style>" if self.style else ""
        definitions = self.defs + self.glyph_defs
        defs = f"<defs>{''.join(definitions)}</defs>" if definitions else ""
        if self.field:
            ground = f'<rect width="{WIDTH}" height="{self.height}" rx="16" fill="#000000"/>'
        elif self.theme["border"]:
            ground = (
                f'<rect x="1" y="1" width="{WIDTH - 2}" height="{self.height - 2}" rx="15" '
                f'fill="{self.theme["ground"]}" stroke="{self.theme["border"]}" stroke-width="2"/>'
            )
        else:
            ground = f'<rect width="{WIDTH}" height="{self.height}" rx="16" fill="{self.theme["ground"]}"/>'
        return head + style + defs + ground + "".join(self.parts) + "</svg>\n"


def heading(svg: Svg, y: float, title: str, subtitle: str | None = None, x: float = MARGIN) -> None:
    svg.text(x, y, title, 34, weight=700)
    if subtitle:
        svg.text(x, y + 42, subtitle, 26, "ink2")


# Inputs.

def load_inputs(results: Path = RESULTS) -> dict:
    """Read every results file the README assets are drawn from."""
    def read(name: str) -> dict:
        return json.loads((results / name).read_text(encoding="utf-8"))

    null_summary = results / "null_model_summary.json"
    return {
        "thresholds": read("critical_thresholds.json"),
        "fragility": read("fragility_scores.json"),
        "curves": pd.read_csv(results / "percolation_curves.csv"),
        "atlas": read("type_atlas.json"),
        "regions": pd.read_csv(results / "regional_impact.csv"),
        "superclasses": pd.read_csv(results / "superclass_impact.csv"),
        "compartments": read("brain_vnc_comparison.json"),
        "edges": read("edge_attack.json"),
        "edge_curves": pd.read_csv(results / "edge_attack.csv"),
        "bottleneck": read("hidden_bottleneck.json"),
        "avalanches": read("avalanche_analysis.json"),
        "null_summary": read("null_model_summary.json") if null_summary.exists() else None,
    }


def strategy_order(thresholds: dict) -> list[str]:
    """Strategies from most to least damaging by critical fraction, random last."""
    targeted = [k for k in thresholds["strategies"] if k != "random"]
    return sorted(targeted, key=lambda k: thresholds["strategies"][k]["f_c"]) + ["random"]


def curve(curves: pd.DataFrame, strategy: str, trial: int = 0) -> pd.DataFrame:
    rows = curves[(curves["strategy"] == strategy) & (curves["trial"] == trial)]
    return rows.sort_values("batch")


def random_trials(curves: pd.DataFrame, column: str) -> tuple[np.ndarray, np.ndarray]:
    """Fractions removed and a trials-by-batches array of ``column`` for random removal."""
    rows = curves[curves["strategy"] == "random"].sort_values(["trial", "batch"])
    table = rows.pivot(index="trial", columns="batch", values=column).to_numpy(dtype=float)
    fractions = rows[rows["trial"] == rows["trial"].min()]["fraction_removed"].to_numpy()
    return fractions, table


def headline(data: dict) -> dict:
    """Numbers shared by the stat plate, the figures and their descriptions."""
    th = data["thresholds"]
    curves = data["curves"]
    intact = th["intact_flow"]
    replay = data["atlas"]["replay"]
    silenced_at_half = {}
    for strategy in th["strategies"]:
        batch = half_flow_batch(curve(curves, strategy)["flow"].tolist(), intact)
        silenced_at_half[strategy] = replay[strategy]["silenced_types"][batch]
    sm = curve(curves, "sm_betweenness").reset_index(drop=True)
    peak = int(sm["avalanche"].fillna(0).idxmax())
    edges = data["edges"]["orders"]
    rand = th["strategies"]["random"]
    return {
        "types": data["fragility"]["graph"]["cell_types"],
        "edges": data["fragility"]["graph"]["edges"],
        "sensory": data["fragility"]["graph"]["sensory_types"],
        "motor": data["fragility"]["graph"]["motor_types"],
        "intact": intact,
        "pairs": data["fragility"]["graph"]["intact_reachable_pairs"],
        "fc_top": th["strategies"][th["most_damaging"]]["f_c"],
        "top": th["most_damaging"],
        "fc_random": rand["f_c"],
        "fc_random_ci": rand["f_c_ci95"],
        "silenced_at_half_max": max(silenced_at_half.values()),
        "silenced_at_half": silenced_at_half,
        "survivors_end": data["atlas"]["types"] - replay["sm_betweenness"]["removed_types"][-1],
        "silenced_end": {k: v["silenced_types"][-1] for k, v in replay.items()},
        "fraction_end": replay["sm_betweenness"]["fraction_removed"][-1],
        "avalanche": int(sm.loc[peak, "avalanche"]),
        "avalanche_from": float(sm.loc[peak - 1, "fraction_removed"]),
        "avalanche_to": float(sm.loc[peak, "fraction_removed"]),
        "avalanche_flow_before": float(sm.loc[peak - 1, "flow"]) / intact,
        "edge_strongest": edges["strongest"]["critical_fraction"],
        "edge_random": edges["random"]["critical_fraction"],
        "edge_random_range": edges["random"]["critical_fraction_range"],
        "edge_random_trials": len(edges["random"]["critical_fraction_trials"]),
        "edge_weakest": edges["weakest"]["critical_fraction"],
    }


# Plates.

def title_plate(data: dict) -> tuple[str, str, str]:
    """Title plate on the black field: the name, the question and the neuropil impact map."""
    svg = Svg(900, "dark", field=True)
    h = headline(data)
    svg.text(MARGIN + 4, 230, "Fault Lines", 150, "#e8edef", serif=True)
    question = ["How much of a nervous system can be", "taken away before sensory input no longer", "reaches the motor system?"]
    for i, line in enumerate(question):
        svg.text(MARGIN + 12, 310 + i * 46, line, 36, "#e8edef", serif=True)

    # The fault motif: one hairline, displaced once, the break drawn in the signal color.
    svg.line(MARGIN + 12, 470, 470, 470, "#3a4348", 2)
    svg.line(470, 470, 482, 482, "#ff4b63", 3, cap="round")
    svg.line(482, 482, 820, 482, "#3a4348", 2)

    facts = [
        f"{count(h['types'])} cell types of the adult male Drosophila CNS",
        f"{count(h['edges'])} connections, {count(h['intact'])} sensory-to-motor routes",
        "Six orders of removal, fixed in advance",
    ]
    for i, line in enumerate(facts):
        svg.text(MARGIN + 12, 560 + i * 44, line, 28, "#9ba5aa", italic_words=("Drosophila",))
    svg.text(MARGIN + 12, 744, f"Routing halves after {pct(h['fc_top'])} of cell types are removed", 28, "#e8edef", 600)
    svg.text(MARGIN + 12, 784, f"in order of output synapses, against {pct(h['fc_random'])} at random.", 28, "#9ba5aa")

    top_regions = atlas_layer(svg, data, x0=920, y0=40, size=820, theme="dark", animate=True)
    svg.text(WIDTH - MARGIN, 870, "Neuropils shaded by the routing lost when their cell types are removed", 20,
             "#7a858a", anchor="end")
    desc = (
        "Fault Lines. How much of a nervous system can be taken away before sensory input no longer reaches the "
        f"motor system? The male fruit fly central nervous system seen from the front on a black field, its neuropils "
        f"shaded from dark to bright red by the share of sensory-to-motor flow capacity lost when every cell type "
        f"anchored in them is removed; the {top_regions[0][0]} is brightest at {pct(top_regions[0][1])}. "
        f"{count(h['types'])} cell types, {count(h['edges'])} connections. Routing halves after {pct(h['fc_top'])} "
        f"of cell types are removed in order of output synapses, against {pct(h['fc_random'])} at random."
    )
    return svg.render("Fault Lines", desc), desc, "plate-title.svg"


def atlas_layer(svg: Svg, data: dict, x0: float, y0: float, size: float, theme: str,
                animate: bool = False) -> list[tuple[str, float]]:
    """Draw neuropil outlines shaded by regional flow lost into a square box; returns neuropils by impact."""
    atlas = data["atlas"]
    regions = data["regions"].set_index("neuropil")
    top = float(regions["flow_drop"].max())
    stops = THEMES[theme]["ramp"]
    scale = size / atlas["canvas"][0]
    transform = f'transform="translate({num(x0)} {num(y0)}) scale({scale:.4f})"'
    stroke = "#000000" if svg.field else THEMES[theme]["ground"]
    body = []
    for outline in atlas["outlines"]:
        name = outline["neuropil"]
        if outline["scored"] and name in regions.index:
            fill = ramp_color(stops, impact_position(float(regions.loc[name, "flow_drop"]), top))
        else:
            fill = THEMES[theme]["track"]
        body.append(f'<path d="{outline["path"]}" fill="{fill}"/>')
    svg.raw(
        f'<g {transform} stroke="{stroke}" stroke-width="{num(1.4 / scale)}" stroke-linejoin="round">{"".join(body)}</g>'
    )
    svg.raw(
        f'<path {transform} d="{atlas["cns_outline"]}" fill="none" stroke="{THEMES[theme]["rule_strong"]}" '
        f'stroke-width="{num(2 / scale)}" stroke-linejoin="round"/>'
    )
    ranked = sorted(
        ((o["neuropil"], float(regions.loc[o["neuropil"], "flow_drop"])) for o in atlas["outlines"]
         if o["scored"] and o["neuropil"] in regions.index),
        key=lambda item: -item[1],
    )
    if animate:
        paths = {o["neuropil"]: o["path"] for o in atlas["outlines"]}
        highlight = ranked[:6]
        period = 12
        svg.style.append(".nx{opacity:0;animation:nx 12s linear infinite}")
        svg.style.append(
            "@keyframes nx{0%{opacity:0}4%{opacity:.6}12%{opacity:.6}18%{opacity:0}100%{opacity:0}}"
            "@media (prefers-reduced-motion:reduce){.nx{animation:none;opacity:0}}"
        )
        glows = "".join(
            f'<path class="nx" style="animation-delay:{i * period / len(highlight):.2f}s" d="{paths[name]}"/>'
            for i, (name, _) in enumerate(highlight)
        )
        svg.raw(f'<g {transform} fill="#ffd9df" stroke="#ff4b63" stroke-width="{num(3 / scale)}">{glows}</g>')
    return ranked


def stat_plate(data: dict, theme: str) -> tuple[str, str, str]:
    """Four headline numbers in a two-by-two grid."""
    svg = Svg(1152, theme)
    h = headline(data)
    col = [MARGIN, 928]
    tops = [60, 618]
    lo, hi = h["fc_random_ci"]
    ends = h["silenced_end"]
    cells = [
        (pct(h["fc_top"]), "", "signal",
         ["Of cell types removed, largest", "output first, halves routing"],
         [f"Random removal needs {pct(h['fc_random'])}", f"95% CI {pct(lo)} to {pct(hi)}"]),
        (str(h["silenced_at_half_max"]), f"of {count(h['types'])}", "ink",
         ["Types cut off from sensory input", "at any strategy's half-flow point"],
         [f"At {pct(h['fraction_end'], 0)} removed, sensory-motor betweenness",
          f"cuts off {count(ends['sm_betweenness'])} types; random removal {count(ends['random'])}"]),
        (pct(h["edge_strongest"]), "", "ink",
         ["Of connections removed, most", "synapses first, halves routing"],
         [f"Random connections {pct(h['edge_random'])}, weakest first",
          "never halve it within the first 50%"]),
        (count(h["avalanche"]), "types", "ink",
         ["Cut off from sensory input by", "a single removal batch"],
         ["Sensory-motor betweenness order,",
          f"flow already down to {pct(h['avalanche_flow_before'])} of intact"]),
    ]
    for i, (big, small, color, label, sub) in enumerate(cells):
        x = col[i % 2]
        y = tops[i // 2]
        svg.line(x, y, x + 768, y, "rule", 2)
        big_width = svg.text(x, y + 200, big, 150, color, serif=True)
        if small:
            svg.text(x + big_width + 24, y + 200, small, 84, color, serif=True)
        for k, line in enumerate(label):
            svg.text(x, y + 276 + k * 58, line, 44, weight=700)
        for k, line in enumerate(sub):
            svg.text(x, y + 404 + k * 54, line, 34, "ink2")
    desc = (
        f"Results at a glance. Removing cell types in order of output synapses halves sensory-to-motor flow capacity "
        f"after {pct(h['fc_top'])} of {count(h['types'])} types; random removal needs {pct(h['fc_random'])} "
        f"(95% CI {pct(lo)} to {pct(hi)}). At each strategy's half-flow point at most {h['silenced_at_half_max']} types "
        f"have lost every path from sensory input; at {pct(h['fraction_end'], 2)} removed, "
        f"{count(ends['sm_betweenness'])} of {count(h['survivors_end'])} surviving types are cut off under "
        f"sensory-motor betweenness against {count(ends['random'])} at random. Removing the connections with the most "
        f"synapses first halves routing after {pct(h['edge_strongest'])} of connections, against "
        f"{pct(h['edge_random'])} at random. A single batch of sensory-motor betweenness removal cuts off "
        f"{count(h['avalanche'])} types at once."
    )
    return svg.render("Results at a glance", desc), desc, f"stat-plate-{theme}.svg"


# Figures.

def figure_curves(data: dict, theme: str) -> tuple[str, str, str]:
    """Figure 1: flow capacity retained against the fraction of types removed, six strategies."""
    svg = Svg(1000, theme)
    h = headline(data)
    th = data["thresholds"]
    curves = data["curves"]
    intact = h["intact"]
    heading(svg, 80, "Sensory-to-motor flow capacity as cell types are removed",
            "Batches of 1% of the remaining types, scores recomputed before each batch. Random: 30 trials, mean and 95% band.")

    px0, px1, py0, py1 = 150, 1110, 214, 850
    to_x = linear(0, 0.5, px0, px1)
    to_y = linear(0, 1, py1, py0)
    svg.text(MARGIN, 190, "Flow capacity retained", 26, "ink2")
    for v in (0.25, 0.5, 0.75, 1.0):
        svg.line(px0, to_y(v), px1, to_y(v), "rule", 1)
    for v in (0, 0.25, 0.5, 0.75, 1.0):
        svg.line(px0 - 8, to_y(v), px0, to_y(v), "axis", 2)
        svg.text(px0 - 16, to_y(v) + 9, pct(v, 0), 26, "ink2", anchor="end")
    for v in (0, 0.1, 0.2, 0.3, 0.4, 0.5):
        svg.line(to_x(v), py1, to_x(v), py1 + 8, "axis", 2)
        svg.text(to_x(v), py1 + 38, pct(v, 0), 26, "ink2", anchor="middle")
    svg.line(px0, py0, px0, py1, "axis", 2)
    svg.line(px0, py1, px1, py1, "axis", 2)
    svg.text((px0 + px1) / 2, py1 + 84, "Cell types removed", 26, "ink2", anchor="middle")

    fractions, table = random_trials(curves, "flow")
    mean, half = mean_ci(table / intact)
    xs = [to_x(f) for f in fractions]
    svg.polygon(xs + xs[::-1], [to_y(v) for v in mean + half] + [to_y(v) for v in (mean - half)[::-1]],
                STRATEGY_COLORS["random"], 0.3)

    svg.line(px0, to_y(0.5), px1, to_y(0.5), "signal", 2.5, dash="10 8")
    svg.text(px1, to_y(0.5) - 14, "Half of intact flow", 24, "signal", 600, anchor="end")

    order = strategy_order(th)
    for strategy in reversed(order):
        if strategy == "random":
            svg.polyline(xs, [to_y(v) for v in mean], "random", 3.5)
        else:
            run = curve(curves, strategy)
            svg.polyline([to_x(f) for f in run["fraction_removed"]], [to_y(v / intact) for v in run["flow"]],
                         strategy, 3.5)
    for strategy in order:
        svg.dot(to_x(th["strategies"][strategy]["f_c"]), to_y(0.5), 9, strategy, ring=3)

    kx = 1180
    svg.text(WIDTH - MARGIN, 250, "Halves at", 26, "ink3", anchor="end")
    for i, strategy in enumerate(order):
        y = 304 + i * 54
        svg.line(kx, y - 9, kx + 44, y - 9, strategy, 4, cap="round")
        lead = i == 0
        name = STRATEGY_NAMES[strategy] + (" (30 trials)" if strategy == "random" else "")
        svg.text(kx + 60, y, name, 26, "ink" if lead else "ink2", 700 if lead else 400)
        svg.text(WIDTH - MARGIN, y, pct(th["strategies"][strategy]["f_c"]), 26, "ink" if lead else "ink2",
                 700 if lead else 400, anchor="end")
    lo, hi = th["strategies"]["random"]["f_c_ci95"]
    y = 304 + len(order) * 54
    svg.text(WIDTH - MARGIN, y - 10, f"95% CI {pct(lo)} to {pct(hi)}", 24, "ink3", anchor="end")
    note = ("Each dot marks where a curve first crosses half of the intact flow capacity, interpolated between "
            "batches. Flow counts edge-disjoint routes from 368 sensory to 665 descending and motor types.")
    svg.dot(kx + 22, 689, 9, "ink2", ring=3)
    for k, line in enumerate(wrap(note, 26, WIDTH - MARGIN - kx - 60)):
        svg.text(kx + 60, 698 + k * 38, line, 26, "ink2")

    listing = ", ".join(f"{STRATEGY_NAMES[s].lower()} {pct(th['strategies'][s]['f_c'])}" for s in order)
    desc = (
        f"Figure 1. Line chart of sensory-to-motor flow capacity retained, from 100% down, as cell types are removed "
        f"from 0% to 50%. All five targeted orders fall steeply and cross the dashed half line early; random removal, "
        f"the mean of 30 trials with a narrow band, falls slowly and ends near {pct(float(mean[-1]), 0)}. Fractions "
        f"removed when flow first halves: {listing}."
    )
    return svg.render("Figure 1. Flow capacity under six removal orders", desc), desc, f"fig-curves-{theme}.svg"


def figure_thresholds(data: dict, theme: str) -> tuple[str, str, str]:
    """Figure 2: critical fraction per strategy against the random-removal trials and interval."""
    svg = Svg(730, theme)
    th = data["thresholds"]
    rand = th["strategies"]["random"]
    order = strategy_order(th)
    heading(svg, 80, "Share of cell types removed when flow capacity halves",
            "Targeted orders are single deterministic runs. Random: each tick is one of 30 trials, with the mean and its 95% CI.")

    ax0, ax1 = 600, 1300
    to_x = linear(0, 0.35, ax0, ax1)
    first, pitch = 250, 64
    top, bottom = first - 40, first + pitch * (len(order) - 1) + 34
    lo, hi = rand["f_c_ci95"]
    svg.rect(to_x(lo), top, to_x(hi) - to_x(lo), bottom - top, STRATEGY_COLORS["random"], opacity=0.25)
    for t in np.arange(0, 0.351, 0.05):
        svg.line(to_x(t), top, to_x(t), bottom, "rule", 1)
        svg.line(to_x(t), bottom, to_x(t), bottom + 8, "axis", 2)
        svg.text(to_x(t), bottom + 38, pct(t, 0), 26, "ink2", anchor="middle")
    svg.line(ax0, bottom, ax1, bottom, "axis", 2)
    svg.text(ax1, bottom + 84, "Cell types removed", 26, "ink2", anchor="end")
    svg.text(1420, top - 14, "Removed", 26, "ink3", anchor="end")
    svg.text(WIDTH - MARGIN, top - 14, "Random needs", 26, "ink3", anchor="end")

    for i, strategy in enumerate(order):
        y = first + i * pitch
        fc = th["strategies"][strategy]["f_c"]
        lead = i == 0
        svg.text(MARGIN, y + 10, STRATEGY_NAMES[strategy], 28, "ink", 700 if lead else 400)
        if strategy == "random":
            for trial in rand["f_c_trials"]:
                svg.line(to_x(trial), y - 18, to_x(trial), y + 18, "random", 2, opacity=0.8)
            svg.line(to_x(lo), y, to_x(hi), y, "ink", 4)
            svg.dot(to_x(fc), y, 11, "ink", ring=3)
            svg.text(WIDTH - MARGIN, y + 9, "baseline", 26, "ink3", anchor="end")
        else:
            svg.line(ax0, y, to_x(fc), y, "rule_strong", 2)
            svg.dot(to_x(fc), y, 12, strategy, ring=3)
            svg.text(WIDTH - MARGIN, y + 9, f"{rand['f_c'] / fc:.1f} times as many", 26,
                     "ink" if lead else "ink2", 700 if lead else 400, anchor="end")
        svg.text(1420, y + 9, pct(fc), 26, "ink" if lead else "ink2", 700 if lead else 400, anchor="end")
    svg.text(to_x(lo) - 10, top - 14, f"Random 95% CI, {pct(lo)} to {pct(hi)}", 24, "ink3", anchor="end")

    listing = ", ".join(
        f"{STRATEGY_NAMES[s].lower()} {pct(th['strategies'][s]['f_c'])}" for s in order if s != "random"
    )
    desc = (
        f"Figure 2. Dot plot of the fraction of cell types removed when flow capacity first halves. {listing}. "
        f"Random removal: 30 trials between {pct(min(rand['f_c_trials']))} and {pct(max(rand['f_c_trials']))}, "
        f"mean {pct(rand['f_c'])} with a 95% CI of {pct(lo)} to {pct(hi)}, shaded across every row. Every targeted "
        f"order lies left of the interval; random removal needs {rand['f_c'] / th['strategies'][order[0]]['f_c']:.1f} "
        f"times as many types as {STRATEGY_NAMES[order[0]].lower()}."
    )
    return svg.render("Figure 2. Critical removal fractions", desc), desc, f"fig-thresholds-{theme}.svg"


def figure_regions(data: dict, theme: str) -> tuple[str, str, str]:
    """Figure 3: neuropils shaded by flow lost, with the ten largest losses against same-size random sets."""
    svg = Svg(1080, theme)
    regions = data["regions"].sort_values("flow_drop", ascending=False).reset_index(drop=True)
    heading(svg, 80, "Removing every cell type anchored in one neuropil",
            "Each type is anchored where most of its synapses are. Exploratory; p-values are uncorrected.")
    ranked = atlas_layer(svg, data, x0=MARGIN - 20, y0=150, size=800, theme=theme)
    top = float(regions["flow_drop"].max())

    # Color key under the map.
    gx0, gx1, gy = MARGIN + 150, 760, 1020
    stops = [f'<stop offset="{k / 20:.2f}" stop-color="{ramp_color(THEMES[theme]["ramp"], k / 20)}"/>' for k in range(21)]
    svg.defs.append(f'<linearGradient id="ramp">{"".join(stops)}</linearGradient>')
    svg.raw(f'<rect x="{gx0}" y="{gy - 44}" width="{gx1 - gx0}" height="18" fill="url(#ramp)"/>')
    for tick in (0, 0.02, 0.05, 0.1, 0.2, round(top, 2)):
        x = gx0 + impact_position(tick, top) * (gx1 - gx0)
        svg.line(x, gy - 26, x, gy - 18, "axis", 2)
        svg.text(x, gy + 8, pct(tick, 0), 22, "ink2", anchor="middle")
    svg.text(gx0 - 12, gy - 28, "Flow lost", 22, "ink3", anchor="end")

    x0 = 900
    bx0, bx1 = 1150, 1480
    to_x = linear(0, 0.4, bx0, bx1)
    svg.text(x0, 214, "Ten largest losses", 28, weight=700)
    svg.text(bx0, 214, "Flow lost, with same-size random sets", 22, "ink3")
    svg.text(WIDTH - MARGIN, 214, "p", 22, "ink3", anchor="end", italic=True)
    svg.line(x0, 232, WIDTH - MARGIN, 232, "rule", 2)
    for i, row in regions.head(10).iterrows():
        y = 290 + i * 60
        svg.text(x0, y, row["neuropil"], 28, weight=700 if i == 0 else 400)
        svg.text(x0, y + 26, f"{count(row['n_types'])} types", 20, "ink3")
        svg.rect(bx0, y - 22, to_x(row["flow_drop"]) - bx0, 26, "signal")
        svg.line(to_x(row["random_mean"]), y - 30, to_x(row["random_mean"]), y + 12, "ink", 4)
        svg.text(to_x(row["flow_drop"]) + 12, y, pct(row["flow_drop"]), 26, weight=700)
        svg.text(WIDTH - MARGIN, y, fmt_p(row["p_value"]), 26, "ink2", anchor="end")
    ky = 290 + 10 * 60 + 10
    svg.rect(x0, ky - 20, 34, 22, "signal")
    svg.text(x0 + 46, ky, "flow lost", 24, "ink2")
    svg.line(x0 + 220, ky - 28, x0 + 220, ky + 6, "ink", 4)
    svg.text(x0 + 236, ky, "mean of 200 same-size random sets", 24, "ink2")
    significant = int((data["regions"]["p_value"] < 0.05).sum())
    at_floor = int((data["regions"]["p_value"] <= 1 / 201 + 1e-9).sum())
    note = (f"{significant} of {len(data['regions'])} neuropils exceed their null at p < 0.05, {at_floor} at the "
            f"smallest attainable 1/201. Neuropils holding many sensory or motor types lead, because removing them "
            f"deletes sources and sinks.")
    for k, line in enumerate(wrap(note, 24, WIDTH - MARGIN - x0)):
        svg.text(x0, ky + 56 + k * 34, line, 24, "ink2")

    first = regions.iloc[0]
    listing = ", ".join(f"{r['neuropil']} {pct(r['flow_drop'])}" for _, r in regions.head(10).iterrows())
    desc = (
        f"Figure 3. Left: the male central nervous system seen from the front, brain above and nerve cord below, "
        f"each neuropil shaded by the share of flow capacity lost when all cell types anchored in it are removed; "
        f"{ranked[0][0]} is darkest. Right: the ten largest losses as bars with the mean loss of 200 same-size random "
        f"sets marked: {listing}. The gnathal ganglia lose {pct(first['flow_drop'])} against "
        f"{pct(first['random_mean'])} for random sets, p = {fmt_p(first['p_value'])}. {significant} of "
        f"{len(data['regions'])} neuropils exceed their null at uncorrected p below 0.05."
    )
    return svg.render("Figure 3. Regional impact", desc), desc, f"fig-regions-{theme}.svg"


def figure_classes(data: dict, theme: str) -> tuple[str, str, str]:
    """Figure 4: flow lost when a whole superclass is removed, against same-size random sets."""
    table = data["superclasses"].sort_values("flow_drop", ascending=False).reset_index(drop=True)
    first, pitch = 270, 56
    svg = Svg(first + pitch * len(table) + 150, theme)
    heading(svg, 80, "Removing every cell type of one superclass",
            "Flow capacity lost, against 200 random sets of the same number of types.")

    ax0, ax1 = 620, 1340
    to_x = linear(0, 1, ax0, ax1)
    top = first - 44
    bottom = first + pitch * (len(table) - 1) + 30
    for t in (0, 0.25, 0.5, 0.75, 1):
        svg.line(to_x(t), top, to_x(t), bottom, "rule", 1)
        svg.line(to_x(t), bottom, to_x(t), bottom + 8, "axis", 2)
        svg.text(to_x(t), bottom + 38, pct(t, 0), 26, "ink2", anchor="middle")
    svg.line(ax0, bottom, ax1, bottom, "axis", 2)
    svg.text(ax1, bottom + 80, "Flow capacity lost", 26, "ink2", anchor="end")
    svg.text(MARGIN + 34, top - 18, "Superclass", 24, "ink3")
    svg.text(560, top - 18, "Types", 24, "ink3", anchor="end")
    svg.text(1520, top - 18, "Random", 24, "ink3", anchor="end")
    svg.text(WIDTH - MARGIN, top - 18, "p", 24, "ink3", anchor="end", italic=True)

    for i, row in table.iterrows():
        y = first + i * pitch
        name = row["superclass"]
        terminal = name in TERMINAL_SUPERCLASSES
        significant = row["p_value"] < 0.05 and row["flow_drop"] > row["random_mean"]
        highlight = significant and not terminal
        if terminal:
            svg.rect(MARGIN, y - 16, 18, 18, "ink3")
        svg.text(MARGIN + 34, y + 9, SUPERCLASS_NAMES.get(name, name.replace("_", " ")), 28, "ink", 700 if highlight else 400)
        svg.text(560, y + 9, count(row["types"]), 26, "ink2", anchor="end")
        a, b = to_x(row["random_mean"]), to_x(row["flow_drop"])
        svg.line(a, y, b, y, "signal" if significant else "rule_strong", 4 if significant else 2)
        svg.dot(a, y, 10, "ink2", hollow=True)
        svg.dot(b, y, 11, "signal" if significant else "ink")
        svg.text(1400, y + 9, pct(row["flow_drop"]), 26, "ink", 700 if significant else 400, anchor="end")
        svg.text(1520, y + 9, pct(row["random_mean"]), 26, "ink3", anchor="end")
        svg.text(WIDTH - MARGIN, y + 9, fmt_p(row["p_value"]), 26, "ink2", anchor="end")
    ky = bottom + 80
    svg.rect(MARGIN, ky - 16, 18, 18, "ink3")
    svg.text(MARGIN + 30, ky, "holds sensory or motor terminal types", 24, "ink2")
    svg.dot(MARGIN + 11, ky + 38, 10, "ink2", hollow=True)
    svg.text(MARGIN + 30, ky + 46, "same-size random sets", 24, "ink2")
    svg.dot(470, ky + 38, 11, "signal")
    svg.text(490, ky + 46, "more than random, p < 0.05", 24, "ink2")

    asc = table.set_index("superclass").loc["ascending_neuron"]
    cbi = table.set_index("superclass").loc["cb_intrinsic"]
    listing = ", ".join(
        f"{SUPERCLASS_NAMES[r['superclass']].lower()} {pct(r['flow_drop'])} against {pct(r['random_mean'])}"
        for _, r in table.iterrows()
    )
    desc = (
        f"Figure 4. Dumbbell chart of flow capacity lost when every cell type of one superclass is removed, each "
        f"against the mean of 200 random sets of the same size: {listing}. Classes that hold sensory or motor terminal "
        f"types lose far more than random, as expected. Among the others, ascending neurons lose {pct(asc['flow_drop'])} "
        f"against {pct(asc['random_mean'])}, p = {fmt_p(asc['p_value'])}, while central brain intrinsic neurons lose "
        f"{pct(cbi['flow_drop'])} against {pct(cbi['random_mean'])}."
    )
    return svg.render("Figure 4. Superclass removal", desc), desc, f"fig-classes-{theme}.svg"


def figure_compartments(data: dict, theme: str) -> tuple[str, str, str]:
    """Figure 5: flow AUC of each strategy in the brain and the nerve cord subgraphs."""
    svg = Svg(950, theme)
    comp = data["compartments"]
    brain, vnc = comp["compartments"]["brain"], comp["compartments"]["vnc"]
    heading(svg, 80, "The same six orders in the brain and in the nerve cord",
            "Area under the flow curve over the first 50% of removals, lower is more fragile. Random: mean of 30 trials.")
    xa, xb = 700, 1060
    py0, py1 = 300, 800
    lo_v, hi_v = 0.1, 0.7
    to_y = linear(lo_v, hi_v, py1, py0)
    for x, name, part in ((xa, "Brain", brain), (xb, "Nerve cord", vnc)):
        svg.line(x, py0 - 20, x, py1 + 20, "axis", 2)
        svg.text(x, 214, name, 30, weight=700, anchor="middle")
        svg.text(x, 250, f"{count(part['types'])} types, {count(part['intact_flow'])} routes", 22, "ink3", anchor="middle")
    for v in (0.2, 0.4, 0.6):
        svg.line(xa, to_y(v), xb, to_y(v), "rule", 1, dash="2 6")
        svg.text((xa + xb) / 2, to_y(v) - 8, f"{v:.1f}", 20, "ink3", anchor="middle")

    order = ["sm_betweenness", "out_strength", "in_strength", "betweenness", "pagerank", "random"]
    for x, part in ((xa, brain), (xb, vnc)):
        lo, hi = part["scores"]["random"]["auc_flow_ci95"]
        svg.rect(x - 12, to_y(hi), 24, to_y(lo) - to_y(hi), STRATEGY_COLORS["random"], opacity=0.4)
    left = spread([to_y(brain["scores"][s]["auc_flow"]) for s in order], 40, py0 - 40, py1 + 40)
    right = spread([to_y(vnc["scores"][s]["auc_flow"]) for s in order], 40, py0 - 40, py1 + 40)
    for strategy, ly, ry in zip(order, left, right):
        a, b = brain["scores"][strategy]["auc_flow"], vnc["scores"][strategy]["auc_flow"]
        svg.line(xa, to_y(a), xb, to_y(b), strategy, 4, cap="round")
        svg.dot(xa, to_y(a), 9, strategy, ring=3)
        svg.dot(xb, to_y(b), 9, strategy, ring=3)
        svg.line(xa - 16, to_y(a), xa - 34, ly, "rule_strong", 1.5)
        svg.line(xb + 16, to_y(b), xb + 34, ry, "rule_strong", 1.5)
        svg.text(xa - 42, ly + 9, f"{STRATEGY_NAMES[strategy]}  {a:.3f}", 26, "ink", anchor="end")
        svg.text(xb + 42, ry + 9, f"{b:.3f}  {STRATEGY_NAMES[strategy]}", 26, "ink")
    welch = comp["welch_random_trials"]["auc_flow"]
    welch_t = f"{welch['t']:.2f}".replace("-", "−")
    note = (f"Under random removal the two do not differ significantly (Welch t = {welch_t}, "
            f"p = {welch['p_value']:.2f}). The most damaging order differs: sensory-motor betweenness in the brain, "
            f"weighted in-degree in the nerve cord.")
    note_lines = wrap(note, 26, WIDTH - 2 * MARGIN)
    for k, line in enumerate(note_lines):
        svg.text(MARGIN, 910 - (len(note_lines) - 1 - k) * 36, line, 26, "ink2")

    def listing(part: dict) -> str:
        return ", ".join(f"{STRATEGY_NAMES[s].lower()} {part['scores'][s]['auc_flow']:.3f}" for s in order)

    desc = (
        f"Figure 5. Slope chart of flow-capacity AUC for each removal order in the brain-dominant subgraph "
        f"({count(brain['types'])} types) and the nerve cord-dominant subgraph ({count(vnc['types'])} types); lower is "
        f"more fragile. Brain: {listing(brain)}. Nerve cord: {listing(vnc)}. Under random removal they do not differ "
        f"significantly (Welch t = {welch_t}, p = {welch['p_value']:.2f}), but the most damaging order changes."
    )
    return svg.render("Figure 5. Brain and nerve cord", desc), desc, f"fig-compartments-{theme}.svg"


EDGE_ORDERS = {
    "strongest": ("Strongest first", "ink", None),
    "random": ("Random order", "random", None),
    "weakest": ("Weakest first", "ink2", "2 9"),
}


def edge_runs(curves: pd.DataFrame, order: str) -> list[pd.DataFrame]:
    """Every trial of one connection-removal order, sorted by fraction removed."""
    rows = curves[curves["order"] == order]
    return [rows[rows["trial"] == t].sort_values("fraction_removed") for t in sorted(rows["trial"].unique())]


def figure_connections(data: dict, theme: str) -> tuple[str, str, str]:
    """Figure 6: flow capacity and connected pairs as connections are removed by synapse count or at random."""
    svg = Svg(1060, theme)
    edges = data["edges"]
    curves = data["edge_curves"]
    intact_pairs = data["fragility"]["graph"]["intact_reachable_pairs"]
    random_order = edges["orders"]["random"]
    trials = len(random_order["critical_fraction_trials"])
    heading(svg, 80, "Removing connections instead of cell types",
            f"Batches of 1% of the {count(edges['edges'])} connections, ordered by synapse count. "
            f"Random: trial 0 drawn, the other {trials - 1} trials faint.")

    x = MARGIN
    for order, (label, color, dash) in EDGE_ORDERS.items():
        svg.line(x, 181, x + 44, 181, color, 4, dash=dash, cap="round")
        x += 60 + svg.text(x + 58, 190, label, 26, "ink2") + 40

    panels = [
        (150, 770, "flow", edges["intact_flow"], "Flow capacity retained"),
        (980, 1600, "reachable_pairs", intact_pairs, "Connected sensory-motor pairs retained"),
    ]
    py0, py1 = 290, 840
    to_y = linear(0, 1, py1, py0)
    ends: dict[str, dict[str, float]] = {}
    for px0, px1, column, intact, title in panels:
        to_x = linear(0, 0.5, px0, px1)
        svg.text(px0 - 86, py0 - 36, title, 26, "ink2")
        for v in (0.25, 0.5, 0.75, 1.0):
            svg.line(px0, to_y(v), px1, to_y(v), "rule", 1)
        for v in (0, 0.25, 0.5, 0.75, 1.0):
            svg.line(px0 - 8, to_y(v), px0, to_y(v), "axis", 2)
            svg.text(px0 - 16, to_y(v) + 9, pct(v, 0), 26, "ink2", anchor="end")
        for v in (0, 0.1, 0.2, 0.3, 0.4, 0.5):
            svg.line(to_x(v), py1, to_x(v), py1 + 8, "axis", 2)
            svg.text(to_x(v), py1 + 38, pct(v, 0), 26, "ink2", anchor="middle")
        svg.line(px0, py0, px0, py1, "axis", 2)
        svg.line(px0, py1, px1, py1, "axis", 2)
        svg.text((px0 + px1) / 2, py1 + 84, "Connections removed", 26, "ink2", anchor="middle")
        if column == "flow":
            svg.line(px0, to_y(0.5), px1, to_y(0.5), "signal", 2.5, dash="10 8")
            svg.text(px0 + 16, to_y(0.5) - 14, "Half of intact flow", 24, "signal", 600)
        for trial, run in enumerate(edge_runs(curves, "random")):
            if trial:
                svg.polyline([to_x(f) for f in run["fraction_removed"]], [to_y(v / intact) for v in run[column]],
                             "random", 2, opacity=0.45)
        for order, (_, color, dash) in reversed(EDGE_ORDERS.items()):
            run = edge_runs(curves, order)[0]
            svg.polyline([to_x(f) for f in run["fraction_removed"]], [to_y(v / intact) for v in run[column]],
                         color, 3.5, dash=dash)
            ends.setdefault(order, {})[column] = float(run[column].iloc[-1]) / intact
        labels = spread([to_y(ends[o][column]) for o in EDGE_ORDERS], 34, py0, py1)
        for order, ly in zip(EDGE_ORDERS, labels):
            svg.text(px1 + 12, ly + 9, pct(ends[order][column]), 24, "ink", 700 if order == "strongest" else 400)
        if column == "flow":
            for trial_fc in random_order["critical_fraction_trials"]:
                svg.line(to_x(trial_fc), to_y(0.5) - 14, to_x(trial_fc), to_y(0.5) + 14, "random", 2)
            svg.dot(to_x(edges["orders"]["strongest"]["critical_fraction"]), to_y(0.5), 9, "ink", ring=3)
            svg.dot(to_x(random_order["critical_fraction"]), to_y(0.5), 9, "random", ring=3)

    strongest = edges["orders"]["strongest"]["critical_fraction"]
    lo, hi = random_order["critical_fraction_range"]
    note = (f"Flow halves after {pct(strongest)} of connections are removed strongest first, and after a mean of "
            f"{pct(random_order['critical_fraction'])} in random order (ticks: {trials} trials, {pct(lo)} to "
            f"{pct(hi)}). Weakest first never halves it, yet it disconnects more pairs than random removal.")
    note_lines = wrap(note, 26, WIDTH - 2 * MARGIN)
    for k, line in enumerate(note_lines):
        svg.text(MARGIN, 1026 - (len(note_lines) - 1 - k) * 36, line, 26, "ink2")

    desc = (
        f"Figure 6. Two line charts over the first 50% of the {count(edges['edges'])} connections removed, in batches "
        f"of 1%. Left, flow capacity retained: removing the connections with the most synapses first crosses half "
        f"after {pct(strongest)} and ends at {pct(ends['strongest']['flow'])}; random order crosses half after a "
        f"mean of {pct(random_order['critical_fraction'])} over {trials} trials, {pct(lo)} to {pct(hi)}, and trial 0 "
        f"ends at {pct(ends['random']['flow'])}; weakest first never crosses half and ends at "
        f"{pct(ends['weakest']['flow'])}. Right, connected sensory-motor pairs retained: strongest first ends at "
        f"{pct(ends['strongest']['reachable_pairs'])}, weakest first at {pct(ends['weakest']['reachable_pairs'])} "
        f"and random trial 0 at {pct(ends['random']['reachable_pairs'])}."
    )
    return svg.render("Figure 6. Removing connections", desc), desc, f"fig-connections-{theme}.svg"


def figure_bottleneck(data: dict, theme: str) -> tuple[str, str, str]:
    """Figure 7: the hidden-bottleneck candidates by percentile, and the wiring and removal cost of the first."""
    svg = Svg(1250, theme)
    bottleneck = data["bottleneck"]
    criteria = bottleneck["criteria"]
    candidates = bottleneck["candidates"]
    ex = bottleneck["example"]
    types = data["fragility"]["graph"]["cell_types"]
    top_share = 100 - criteria["sm_betweenness_percentile_at_least"]
    heading(svg, 80, "Unremarkable by partners and PageRank, near the top by sensory-motor betweenness",
            f"Percentiles among {count(types)} types. Shaded: where a type must fall to qualify. Betweenness is drawn "
            f"from {betweenness_floor(candidates, criteria)} to 100 so the candidates separate.")

    floor = betweenness_floor(candidates, criteria)
    measures = [
        ("Degree", "degree_pct", (0, 100), criteria["degree_percentile_below"], True, 1),
        ("PageRank", "pagerank_pct", (0, 100), criteria["pagerank_percentile_below"], True, 1),
        ("Sensory-motor betweenness", "sm_betweenness_pct", (floor, 100),
         criteria["sm_betweenness_percentile_at_least"], False, 2),
    ]
    first, pitch = 276, 64
    columns = [(330, 690, 750), (820, 1180, 1240), (1310, 1600, WIDTH - MARGIN)]
    bottom = first + pitch * (len(candidates) - 1) + 30
    for i, candidate in enumerate(candidates):
        y = first + i * pitch
        lead = candidate["cell_type"] == ex["cell_type"]
        svg.text(MARGIN, y + 4, candidate["cell_type"], 28, weight=700 if lead else 400)
        svg.text(MARGIN, y + 28, SUPERCLASS_NAMES[candidate["superclass"]].lower(), 18, "ink3")
    for (title, key, (d0, d1), cut, below, digits), (ax0, ax1, value_x) in zip(measures, columns):
        to_x = linear(d0, d1, ax0, ax1)
        zone = (ax0, to_x(cut)) if below else (to_x(cut), ax1)
        svg.rect(zone[0], first - 34, zone[1] - zone[0], bottom - first + 34, "track")
        svg.line(to_x(cut), first - 34, to_x(cut), bottom, "axis", 2, dash="6 5")
        svg.text(ax0, first - 56, title, 24, "ink2", 700)
        for i, candidate in enumerate(candidates):
            y = first + i * pitch
            lead = candidate["cell_type"] == ex["cell_type"]
            svg.line(ax0, y, ax1, y, "rule", 1.5)
            svg.dot(to_x(candidate[key]), y, 10 if lead else 8, "ink" if lead else "ink2", ring=3)
            svg.text(value_x, y + 8, f"{candidate[key]:.{digits}f}", 22, "ink" if lead else "ink2",
                     700 if lead else 400, anchor="end")
        svg.line(ax0, bottom, ax1, bottom, "axis", 2)
        for tick in (d0, cut, d1):
            svg.line(to_x(tick), bottom, to_x(tick), bottom + 8, "axis", 2)
            svg.text(to_x(tick), bottom + 36, f"{tick:g}", 22, "ink2", anchor="middle")

    # The wiring around the first candidate, line width proportional to synapses.
    top = 620
    svg.line(MARGIN, top - 44, WIDTH - MARGIN, top - 44, "rule", 2)
    svg.text(MARGIN, top, f"{ex['cell_type']}, {ex['n_neurons']} neurons: its five strongest inputs and outputs", 28,
             weight=700)
    heaviest = max(p["synapses"] for p in ex["strongest_inputs"] + ex["strongest_outputs"])
    node_x, node_y, row = 880, top + 190, 52
    svg.circle(node_x, node_y, 46, "signal")
    svg.text(node_x, node_y + 9, ex["cell_type"], 24, "#ffffff", 700, anchor="middle")
    for side, partners, text_x, anchor in ((-1, ex["strongest_inputs"], 470, "end"),
                                           (1, ex["strongest_outputs"], 1290, "start")):
        for k, partner in enumerate(partners):
            y = node_y + (k - 2) * row
            x0 = node_x + side * 46
            x1 = text_x + side * -16
            width = 2 + 14 * partner["synapses"] / heaviest
            svg.raw(
                f'<path d="M{num(x1)} {num(y)}C{num((x0 + x1) / 2)} {num(y)} {num((x0 + x1) / 2)} {num(node_y)} '
                f'{num(x0)} {num(node_y)}" fill="none" stroke="{svg.c("rule_strong")}" '
                f'stroke-width="{num(width)}"/>'
            )
            name = f"{partner['cell_type']}  {count(partner['synapses'])}"
            svg.text(text_x, y + 8, name, 24, "ink", anchor=anchor)
            kind = SUPERCLASS_NAMES.get(partner["superclass"], partner["superclass"]).lower()
            svg.text(text_x, y + 32, kind, 18, "ink3", anchor=anchor)
    svg.text(470, top + 56, "Inputs, synapses", 22, "ink3", anchor="end")
    svg.text(1290, top + 56, "Outputs, synapses", 22, "ink3")

    lost = ex["intact_flow"] - ex["flow_after_removal"]
    cells = [
        (f"{count(lost)}", f"of {count(ex['intact_flow'])} routes lost when {ex['cell_type']} alone is removed"),
        (count(ex["pairs_lost_when_removed"]), f"of {count(ex['reachable_pairs'])} sensory-motor pairs disconnected"),
        (count(ex["pairs_with_longer_shortest_path_when_removed"]), "pairs whose shortest route gets longer"),
        (ordinal(ex["sm_betweenness_rank"]), f"of {count(types)} by sensory-motor betweenness, "
                                           f"{pct(ex['share_of_shortest_routes'], 2)} of shortest routes"),
    ]
    cell_w = (WIDTH - 2 * MARGIN) / len(cells)
    for i, (big, label) in enumerate(cells):
        x = MARGIN + i * cell_w
        svg.text(x, top + 490, big, 72, serif=True)
        for k, line in enumerate(wrap(label, 24, cell_w - 40)):
            svg.text(x, top + 530 + k * 32, line, 24, "ink2")

    listing = "; ".join(
        f"{c['cell_type']}, degree percentile {c['degree_pct']:.1f}, PageRank {c['pagerank_pct']:.1f}, sensory-motor "
        f"betweenness {c['sm_betweenness_pct']:.2f}" for c in candidates
    )
    inputs = ", ".join(f"{p['cell_type']} {count(p['synapses'])}" for p in ex["strongest_inputs"])
    outputs = ", ".join(f"{p['cell_type']} {count(p['synapses'])}" for p in ex["strongest_outputs"])
    sensory_inputs = ("all sensory" if all(p["superclass"].endswith("sensory") for p in ex["strongest_inputs"])
                      else "not all sensory")
    desc = (
        f"Figure 7. Top: {len(candidates)} cell types in the bottom half by degree and by PageRank but in the top "
        f"{top_share:g}% by sensory-motor betweenness, as dots on percentile tracks: {listing}. Bottom: "
        f"{ex['cell_type']}, a type of {ex['n_neurons']} neurons, with its five strongest inputs ({inputs} synapses), "
        f"{sensory_inputs}, and five strongest outputs ({outputs}). Removing it alone loses {count(lost)} of "
        f"{count(ex['intact_flow'])} routes and disconnects {count(ex['pairs_lost_when_removed'])} pairs, but "
        f"{count(ex['pairs_with_longer_shortest_path_when_removed'])} pairs take a longer shortest route. It ranks "
        f"{ordinal(ex['sm_betweenness_rank'])} of {count(types)} by sensory-motor betweenness."
    )
    return svg.render("Figure 7. A hidden bottleneck", desc), desc, f"fig-bottleneck-{theme}.svg"


def ordinal(n: int) -> str:
    """English ordinal, e.g. 21 -> '21st'."""
    suffix = "th" if 11 <= n % 100 <= 13 else {1: "st", 2: "nd", 3: "rd"}.get(n % 10, "th")
    return f"{n}{suffix}"


def betweenness_floor(candidates: Sequence[dict], criteria: dict) -> int:
    """Lower end of the betweenness percentile axis: one below the lowest candidate or the cut, whichever is lower."""
    low = min([criteria["sm_betweenness_percentile_at_least"]] + [c["sm_betweenness_pct"] for c in candidates])
    return max(0, math.floor(low) - 1)


def avalanche_sizes(curves: pd.DataFrame, runs: Iterable[tuple[str, int]]) -> np.ndarray:
    """Cascade sizes of the batches within the first 50% of removals, pooled over (strategy, trial) runs."""
    pooled = []
    for strategy, trial in runs:
        run = curve(curves, strategy, trial)
        window = int(np.argmax(run["fraction_removed"].to_numpy() >= 0.5)) + 1
        pooled.append(run["avalanche"].to_numpy()[1:window].astype(int))
    return np.concatenate(pooled)


def power_law_ccdf(x: np.ndarray, alpha: float, xmin: float) -> np.ndarray:
    """P(X >= x | X >= xmin) for the discrete power law, from Hurwitz zeta functions."""
    return special.zeta(alpha, x) / special.zeta(alpha, xmin)


def figure_avalanches(data: dict, theme: str) -> tuple[str, str, str]:
    """Figure 8: cascade-size CCDFs in both poolings with their fitted power laws, and the fit statistics."""
    svg = Svg(900, theme)
    fits = data["avalanches"]
    curves = data["curves"]
    targeted = [s for s in data["thresholds"]["strategies"] if s != "random"]
    random_trials_n = int(curves.loc[curves["strategy"] == "random", "trial"].nunique())
    sets = [
        ("Primary", "primary", [(s, 0) for s in ["random", *targeted]], "signal", False),
        ("Sensitivity", "sensitivity_all_random_trials",
         [(s, 0) for s in targeted] + [("random", t) for t in range(random_trials_n)], "ink2", True),
    ]
    heading(svg, 80, "Cascade sizes are not established as scale-free",
            "Cell types newly cut off from sensory input by one removal batch, within the first 50% of removals.")

    px0, px1, py0, py1 = 170, 900, 214, 740
    to_x = linear(0, 4, px0, px1)
    to_y = linear(-3, 0, py1, py0)
    for e in range(0, 5):
        svg.line(to_x(e), py1, to_x(e), py1 + 8, "axis", 2)
        svg.text(to_x(e), py1 + 38, count(10 ** e), 24, "ink2", anchor="middle")
    for e, label in ((0, "100%"), (-1, "10%"), (-2, "1%"), (-3, "0.1%")):
        svg.line(px0, to_y(e), px1, to_y(e), "rule", 1)
        svg.line(px0 - 8, to_y(e), px0, to_y(e), "axis", 2)
        svg.text(px0 - 16, to_y(e) + 9, label, 24, "ink2", anchor="end")
    svg.line(px0, py0, px0, py1, "axis", 2)
    svg.line(px0, py1, px1, py1, "axis", 2)
    svg.text((px0 + px1) / 2, py1 + 82, "Cascade size, cell types", 26, "ink2", anchor="middle")
    svg.text(MARGIN, 190, "Share of cascades at least this size", 26, "ink2")

    for name, key, runs, color, hollow in reversed(sets):
        fit = fits[key]
        sizes = avalanche_sizes(curves, runs)
        positive = np.sort(sizes[sizes > 0])
        checks = (len(sizes), int((sizes == 0).sum()), len(positive), int((positive >= fit["xmin"]).sum()),
                  int(positive.max()))
        expected = (fit["batches"], fit["zero_size"], fit["fitted"], fit["n_tail"], fit["max_size"])
        if checks != expected:
            raise ValueError(f"{key}: cascade sizes {checks} do not match avalanche_analysis.json {expected}")
        values = np.unique(positive)
        share = 1 - np.searchsorted(positive, values, side="left") / len(positive)
        xs = np.geomspace(fit["xmin"], positive.max(), 60)
        model = fit["n_tail"] / fit["fitted"] * power_law_ccdf(xs, fit["alpha"], fit["xmin"])
        xs, model = xs[model >= 1e-3], model[model >= 1e-3]
        svg.polyline([to_x(math.log10(v)) for v in xs], [to_y(math.log10(v)) for v in model], color, 3, dash="12 8")
        for v, s in zip(values, share):
            svg.dot(to_x(math.log10(v)), to_y(math.log10(s)), 7, color, hollow=hollow)

    lx = 560
    svg.dot(lx, 250, 7, "signal")
    svg.text(lx + 20, 259, "Primary: one run per order", 24, "ink2")
    svg.dot(lx, 290, 7, "ink2", hollow=True)
    svg.text(lx + 20, 299, f"Sensitivity: all {random_trials_n} random trials", 24, "ink2")
    svg.line(lx - 12, 330, lx + 12, 330, "ink2", 3, dash="8 5")
    svg.text(lx + 20, 339, "Fitted power law, over the sizes it fits", 24, "ink2")

    tx0, col_a, col_b = 1000, 1480, WIDTH - MARGIN
    svg.text(col_a, 214, "Primary", 24, "ink3", 700, anchor="end")
    svg.text(col_b, 214, "Sensitivity", 24, "ink3", 700, anchor="end")
    svg.line(tx0, 232, col_b, 232, "rule", 2)
    primary, sensitivity = fits["primary"], fits["sensitivity_all_random_trials"]

    def lr(r: dict, alternative: str) -> str:
        c = r["comparisons"][alternative]
        return f"{c['loglikelihood_ratio']:+.3f} ({c['p_value']:.3f})".replace("-", "−")

    rows = [
        ("Batches, positive sizes", f"{primary['batches']}, {primary['fitted']}",
         f"{count(sensitivity['batches'])}, {sensitivity['fitted']}"),
        ("Exponent", f"{primary['alpha']:.3f} ± {primary['alpha_se']:.3f}",
         f"{sensitivity['alpha']:.3f} ± {sensitivity['alpha_se']:.3f}"),
        ("Fitted from size", f"{primary['xmin']:g} ({primary['n_tail']} sizes)",
         f"{sensitivity['xmin']:g} ({sensitivity['n_tail']} sizes)"),
        ("Bootstrap p", f"{primary['bootstrap_p']:.3f}", f"{sensitivity['bootstrap_p']:.3f}"),
        ("Power law", "plausible" if primary["power_law_plausible"] else "rejected",
         "plausible" if sensitivity["power_law_plausible"] else "rejected"),
        ("Against lognormal, R (p)", lr(primary, "lognormal"), lr(sensitivity, "lognormal")),
        ("Against exponential, R (p)", lr(primary, "exponential"), lr(sensitivity, "exponential")),
    ]
    for i, (label, a, b) in enumerate(rows):
        y = 284 + i * 56
        verdict = label == "Power law"
        svg.text(tx0, y, label, 24, "ink2")
        for value, x, result in ((a, col_a, primary), (b, col_b, sensitivity)):
            rejected = verdict and not result["power_law_plausible"]
            svg.text(x, y, value, 24, "signal" if rejected else "ink", 700 if verdict else 400, anchor="end")
        svg.line(tx0, y + 22, col_b, y + 22, "rule", 1)
    note = ("A power law counts as plausible at bootstrap p of 0.1 or more. It passes in one pooling and fails in the "
            "other, and a lognormal cannot be told apart in either. R above 0 favors the power law.")
    for k, line in enumerate(wrap(note, 24, col_b - tx0)):
        svg.text(tx0, 700 + k * 34, line, 24, "ink2")
    svg.text(MARGIN, 862, f"The largest cascade, {count(primary['max_size'])} types, comes from a single sensory-motor "
                          "betweenness batch.", 24, "ink3")

    desc = (
        f"Figure 8. Log-log plot of the share of structural cascades at least a given size, for the primary pooling of "
        f"one run per removal order ({primary['fitted']} positive sizes) and the sensitivity pooling with all "
        f"{random_trials_n} random trials ({sensitivity['fitted']} positive sizes), each with its fitted discrete power "
        f"law. Primary: exponent {primary['alpha']:.3f} above size {primary['xmin']:g}, bootstrap p = "
        f"{primary['bootstrap_p']:.3f}, plausible. Sensitivity: exponent {sensitivity['alpha']:.3f} above size "
        f"{sensitivity['xmin']:g}, bootstrap p = {sensitivity['bootstrap_p']:.3f}, rejected. Against a lognormal the "
        f"likelihood ratio is not significant in either pooling (p = "
        f"{primary['comparisons']['lognormal']['p_value']:.3f} and "
        f"{sensitivity['comparisons']['lognormal']['p_value']:.3f}). The largest cascade is "
        f"{count(primary['max_size'])} types."
    )
    return svg.render("Figure 8. Cascade sizes", desc), desc, f"fig-avalanches-{theme}.svg"


def methods_pipeline(data: dict, theme: str) -> tuple[str, str, str]:
    """The analysis pipeline as eight numbered steps in two rows, with a pulse travelling along the flow."""
    svg = Svg(660, theme)
    h = headline(data)
    null_done = data["null_summary"] is not None
    steps = [
        ("Data", f"{count(164506)} typed neurons", "neuPrint male-cns:v1.0"),
        ("Type graph", f"{count(h['edges'])} edges", "build_type_graph.py"),
        ("Terminals", f"{h['sensory']} sensory, {h['motor']} motor", "identify_sensory_motor_sets.py"),
        ("Pre-registration", f"commit {PREREGISTRATION_COMMIT}", "results/preregistration.md"),
        ("Removal", "6 orders, 1% batches", "run_percolation.py"),
        ("Thresholds", f"{pct(h['fc_top'])} against {pct(h['fc_random'])}", "critical_thresholds.py"),
        ("Null model", "200 rewired graphs", "null_model.py"),
        ("Follow-ups", "regions, classes, edges", "make analyze, make hero"),
    ]
    box_w, box_h = 370, 218
    xs = [65 + i * 420 for i in range(4)]
    ys = [61, 381]
    arrow = "rule_strong"
    paths, heads = [], []
    for row, y in enumerate(ys):
        for i in range(3):
            x = xs[i] + box_w + 1
            paths.append(f"M{x} {y + 109}H{x + 36}")
            heads.append(f"M{x + 45} {y + 109}L{x + 35} {y + 104}V{y + 114}Z")
    paths.append("M1510 280V318A12 12 0 0 1 1498 330H262A12 12 0 0 0 250 342V368")
    heads.append("M250 377L245 367H255Z")
    opacity = ' opacity="0.7"' if theme == "dark" else ""
    svg.raw(
        f'<g{opacity}><path d="{"".join(paths)}" fill="none" stroke="{svg.c(arrow)}" stroke-width="2"/>'
        f'<path d="{"".join(heads)}" fill="{svg.c(arrow)}"/></g>'
    )
    track = "M250 170H1510V318A12 12 0 0 1 1498 330H262A12 12 0 0 0 250 342V490H1510"
    svg.style.append(
        ".pulse{animation:pulse 10s linear infinite}"
        "@keyframes pulse{0%{stroke-dashoffset:0}100%{stroke-dashoffset:-4090}}"
        "@media (prefers-reduced-motion:reduce){.pulse{animation:none;display:none}}"
    )
    svg.raw(
        f'<path class="pulse" d="{track}" fill="none" stroke="{svg.c("signal")}" stroke-opacity="0.55" '
        f'stroke-width="8" stroke-linecap="round" stroke-dasharray="0.1 4290"/>'
    )
    for k, (title, value, module) in enumerate(steps):
        x, y = xs[k % 4], ys[k // 4]
        svg.rect(x, y, box_w, box_h, "plate", rx=11, stroke="rule")
        svg.text(x + 22, y + 52, str(k + 1), 34, "ink3", serif=True)
        svg.text(x + 56, y + 52, title, 26, weight=700)
        if title == "Null model" and not null_done:
            svg.text(x + box_w - 22, y + 52, "computing", 20, "signal", 600, anchor="end")
        svg.text(x + 22, y + 116, value, 28, serif=True)
        svg.text(x + 22, y + 170, module, 20, "ink2")
    status = "complete" if null_done else "still computing"
    desc = (
        "The analysis pipeline in eight steps: 1 data, 164,506 typed neurons from neuPrint male-cns:v1.0; "
        f"2 type graph, {count(h['edges'])} edges between {count(h['types'])} cell types; 3 terminals, {h['sensory']} "
        f"sensory and {h['motor']} descending or motor types; 4 pre-registration, committed as "
        f"{PREREGISTRATION_COMMIT} before any removal; 5 removal, six adaptive orders in batches of 1%; "
        f"6 thresholds, flow halves after {pct(h['fc_top'])} against {pct(h['fc_random'])} at random; "
        f"7 null model, 200 degree-preserving rewired graphs, {status}; 8 follow-up analyses of regions, "
        "superclasses and connections."
    )
    return svg.render("The analysis pipeline in eight steps", desc), desc, f"methods-pipeline-{theme}.svg"


THEMED = (stat_plate, figure_curves, figure_thresholds, figure_regions, figure_classes, figure_compartments,
          figure_connections, figure_bottleneck, figure_avalanches, methods_pipeline)


def build_all(data: dict, out_dir: Path) -> list[Path]:
    """Write every README asset into ``out_dir`` and return the paths written."""
    out_dir.mkdir(parents=True, exist_ok=True)
    written = []
    jobs: list[tuple[str, str, str]] = [title_plate(data)]
    for build in THEMED:
        for theme in THEMES:
            jobs.append(build(data, theme))
    for svg, _, name in jobs:
        path = out_dir / name
        path.write_text(svg, encoding="utf-8", newline="\n")
        written.append(path)
    return written


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, default=OUT_DIR)
    args = parser.parse_args()
    for path in build_all(load_inputs(), args.out):
        print(f"Wrote {path} ({path.stat().st_size / 1024:.0f} KB)")


if __name__ == "__main__":
    main()
