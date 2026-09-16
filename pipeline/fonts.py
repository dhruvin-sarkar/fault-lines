"""Fetch the project's two typefaces from Google Fonts and make them available to matplotlib."""

import re

import requests
from matplotlib import font_manager

from pipeline.common import DATA

FONT_CACHE = DATA / "fonts"
CSS_URL = ("https://fonts.googleapis.com/css2?family=Archivo:wght@400;500;600&"
           "family=Spline+Sans+Mono:wght@400;500&display=swap")
SANS = "Archivo"
MONO = "Spline Sans Mono"


def font_urls(user_agent: str = "Wget/1.20") -> list[str]:
    """Font file URLs from the Google Fonts stylesheet; the user agent decides the format served."""
    response = requests.get(CSS_URL, headers={"User-Agent": user_agent}, timeout=60)
    response.raise_for_status()
    return re.findall(r"url\((https://[^)]+)\)", response.text)


def download_fonts(destination=FONT_CACHE, user_agent: str = "Wget/1.20") -> list:
    """Download every font file in the stylesheet, skipping files already present."""
    destination.mkdir(parents=True, exist_ok=True)
    paths = []
    for url in font_urls(user_agent):
        path = destination / url.rsplit("/", 1)[-1]
        if not path.exists():
            response = requests.get(url, timeout=120)
            response.raise_for_status()
            path.write_bytes(response.content)
        paths.append(path)
    return paths


def register() -> tuple[str, str]:
    """Register the typefaces with matplotlib and return the (sans, mono) family names."""
    for path in download_fonts():
        font_manager.fontManager.addfont(str(path))
    available = {f.name for f in font_manager.fontManager.ttflist}
    missing = {SANS, MONO} - available
    if missing:
        raise RuntimeError(f"Typefaces not registered: {', '.join(sorted(missing))}")
    return SANS, MONO
