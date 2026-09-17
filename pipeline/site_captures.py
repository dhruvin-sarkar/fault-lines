"""Record README animations and a phone-width strip of the site, then assemble them from the saved frames.

Recording connects to an already-running Chrome started with ``--remote-debugging-port``, opens one tab of its
own, saves full-viewport screenshots and a ``plan.json`` per scene under the frames directory, and closes the tab.
Assembly reads those frames and plans and writes the GIFs and the strip to ``assets/readme/``; it needs no browser,
so frames taken by any DevTools client that follows the same plans can be assembled the same way.
"""

import argparse
import base64
import hashlib
import json
import math
import os
import re
import socket
import struct
import time
import urllib.parse
import urllib.request
from collections.abc import Sequence
from pathlib import Path

import numpy as np
from PIL import Image, ImageChops, ImageDraw

from pipeline.common import ASSETS, DATA

OUT_DIR = ASSETS / "readme"
FRAMES_DIR = DATA / "captures"
SITE = "http://localhost:4173/fault-lines/"
DEVTOOLS = "http://127.0.0.1:9222"
DESKTOP = (1280, 1400)
LOOKUP_VIEW = (1040, 1000)
PHONE = (390, 844)
SCALE = 2
GIF_WIDTH = 1320
GIF_COLORS = 255
STRIP_WIDTH = 1760
PHONE_WIDTH = 380
STRIP_MARGIN = 48
FIELD = (0, 0, 0)
STRIP_FIELD = (52, 54, 58)
WS_GUID = "258EAFA5-E914-47DA-95CA-C5AB0DC85B11"

# Race timing in milliseconds, and the attack pinned once the race has finished.
RACE_START_MS = 1200
RACE_STEP_MS = 110
RACE_END_MS = 1800
RACE_FOCUS_MS = 3000
RACE_FOCUS = "Weighted out-degree"

# The lookup map is sticky 76px from the top, just under the site header; the crop starts 12px above it.
LOOKUP_TOP = 76
LOOKUP_HEIGHT = 900
LOOKUP_SCROLL_MS = 40
# Resting scroll offsets in CSS pixels, with the frames spent reaching each and how long it holds: the removal
# panel in full, then the strategy timing chart.
LOOKUP_STOPS = ((330, 18, 2800), (816, 24, 3600))


# WebSocket framing (RFC 6455), enough for a DevTools session.

def accept_key(key: str) -> str:
    """Sec-WebSocket-Accept value the server must return for a client ``key``."""
    return base64.b64encode(hashlib.sha1((key + WS_GUID).encode()).digest()).decode()


def encode_frame(payload: bytes, opcode: int = 0x1, mask: bytes | None = None) -> bytes:
    """A single final client frame carrying ``payload``, masked with ``mask`` (random when None)."""
    mask = os.urandom(4) if mask is None else mask
    header = bytes([0x80 | opcode])
    length = len(payload)
    if length < 126:
        header += bytes([0x80 | length])
    elif length < 1 << 16:
        header += bytes([0x80 | 126]) + struct.pack(">H", length)
    else:
        header += bytes([0x80 | 127]) + struct.pack(">Q", length)
    masked = bytes(b ^ mask[i % 4] for i, b in enumerate(payload))
    return header + mask + masked


def parse_frame(buffer: bytes) -> tuple[bool, int, bytes, int] | None:
    """Parse one frame from the start of ``buffer``.

    Returns (final, opcode, payload, bytes consumed), or None when the buffer holds no complete frame.
    """
    if len(buffer) < 2:
        return None
    final = bool(buffer[0] & 0x80)
    opcode = buffer[0] & 0x0F
    masked = bool(buffer[1] & 0x80)
    length = buffer[1] & 0x7F
    offset = 2
    if length == 126:
        if len(buffer) < 4:
            return None
        length = struct.unpack(">H", buffer[2:4])[0]
        offset = 4
    elif length == 127:
        if len(buffer) < 10:
            return None
        length = struct.unpack(">Q", buffer[2:10])[0]
        offset = 10
    mask = b""
    if masked:
        mask = buffer[offset : offset + 4]
        offset += 4
    if len(buffer) < offset + length:
        return None
    payload = buffer[offset : offset + length]
    if masked:
        payload = bytes(b ^ mask[i % 4] for i, b in enumerate(payload))
    return final, opcode, payload, offset + length


class DevTools:
    """A DevTools protocol connection to the browser endpoint, with flat per-tab sessions."""

    def __init__(self, ws_url: str, timeout: float = 60) -> None:
        parts = urllib.parse.urlparse(ws_url)
        self.sock = socket.create_connection((parts.hostname, parts.port or 80), timeout=timeout)
        key = base64.b64encode(os.urandom(16)).decode()
        request = (
            f"GET {parts.path} HTTP/1.1\r\nHost: {parts.hostname}:{parts.port}\r\nUpgrade: websocket\r\n"
            f"Connection: Upgrade\r\nSec-WebSocket-Key: {key}\r\nSec-WebSocket-Version: 13\r\n\r\n"
        )
        self.sock.sendall(request.encode())
        response = b""
        while b"\r\n\r\n" not in response:
            chunk = self.sock.recv(4096)
            if not chunk:
                raise ConnectionError("DevTools endpoint closed the handshake")
            response += chunk
        head, self.buffer = response.split(b"\r\n\r\n", 1)
        if accept_key(key).encode() not in head:
            raise ConnectionError("DevTools endpoint refused the WebSocket upgrade")
        self.next_id = 0

    def _receive(self) -> dict:
        message = b""
        while True:
            parsed = parse_frame(self.buffer)
            if parsed is None:
                chunk = self.sock.recv(1 << 20)
                if not chunk:
                    raise ConnectionError("DevTools connection closed")
                self.buffer += chunk
                continue
            final, opcode, payload, used = parsed
            self.buffer = self.buffer[used:]
            if opcode == 0x9:
                self.sock.sendall(encode_frame(payload, 0xA))
                continue
            if opcode == 0x8:
                raise ConnectionError("DevTools connection closed")
            message += payload
            if final:
                return json.loads(message)

    def call(self, method: str, params: dict | None = None, session: str | None = None) -> dict:
        """Send one command and return its result, skipping events that arrive meanwhile."""
        self.next_id += 1
        command = {"id": self.next_id, "method": method, "params": params or {}}
        if session:
            command["sessionId"] = session
        self.sock.sendall(encode_frame(json.dumps(command).encode()))
        while True:
            message = self._receive()
            if message.get("id") == self.next_id:
                if "error" in message:
                    raise RuntimeError(f"{method}: {message['error'].get('message')}")
                return message.get("result", {})

    def close(self) -> None:
        self.sock.close()


def browser_endpoint(devtools: str) -> str:
    """WebSocket URL of the running browser at the DevTools HTTP address ``devtools``."""
    try:
        with urllib.request.urlopen(f"{devtools}/json/version", timeout=5) as response:
            return json.load(response)["webSocketDebuggerUrl"]
    except OSError as error:
        raise SystemExit(
            f"No Chrome DevTools endpoint at {devtools} ({error}). Start Chrome with --remote-debugging-port=9222, "
            "build the site and serve it with `npx vite preview --port 4173` in web/, then try again."
        ) from error


class Tab:
    """One tab opened in the running browser, driven through a flat session."""

    def __init__(self, devtools: DevTools, width: int, height: int, scale: float = SCALE, mobile: bool = False) -> None:
        self.dt = devtools
        self.target = devtools.call("Target.createTarget", {"url": "about:blank"})["targetId"]
        self.session = devtools.call("Target.attachToTarget", {"targetId": self.target, "flatten": True})["sessionId"]
        self.call("Page.enable")
        self.resize(width, height, scale, mobile)

    def call(self, method: str, params: dict | None = None) -> dict:
        return self.dt.call(method, params, self.session)

    def resize(self, width: int, height: int, scale: float = SCALE, mobile: bool = False) -> None:
        self.width, self.height, self.scale = width, height, scale
        self.call("Emulation.setDeviceMetricsOverride",
                  {"width": width, "height": height, "deviceScaleFactor": scale, "mobile": mobile})
        self.call("Emulation.setTouchEmulationEnabled", {"enabled": mobile})

    def evaluate(self, expression: str):
        result = self.call("Runtime.evaluate", {"expression": expression, "returnByValue": True, "awaitPromise": True})
        if "exceptionDetails" in result:
            raise RuntimeError(f"Script failed: {expression[:80]}")
        return result["result"].get("value")

    def wait_for(self, expression: str, timeout: float = 30) -> None:
        deadline = time.monotonic() + timeout
        while not self.evaluate(f"Boolean({expression})"):
            if time.monotonic() > deadline:
                raise TimeoutError(f"Timed out waiting for {expression}")
            time.sleep(0.1)

    def open(self, url: str, ready: str) -> None:
        """Navigate to ``url`` and wait until ``ready`` evaluates truthy and fonts have loaded."""
        self.call("Page.navigate", {"url": url})
        self.wait_for("document.readyState === 'complete'")
        self.wait_for(ready)
        self.evaluate("document.fonts.ready.then(() => true)")
        time.sleep(0.8)

    def scroll_to(self, selector: str, offset: int) -> float:
        """Scroll so the element matching ``selector`` starts ``offset`` pixels below the viewport top."""
        top = self.evaluate(
            f"(() => {{ const el = document.querySelector({json.dumps(selector)});"
            f" const top = el.getBoundingClientRect().top + window.scrollY - {offset};"
            " window.scrollTo({top, behavior: 'instant'}); return top; })()"
        )
        time.sleep(0.5)
        return top

    def rect(self, selector: str) -> dict:
        """Viewport rectangle of the first element matching ``selector``."""
        return self.evaluate(
            f"(() => {{ const r = document.querySelector({json.dumps(selector)}).getBoundingClientRect();"
            " return {left: r.left, top: r.top, right: r.right, bottom: r.bottom}; })()"
        )

    def insert_text(self, text: str) -> None:
        self.call("Input.insertText", {"text": text})

    def press(self, key: str, code: int) -> None:
        for kind in ("keyDown", "keyUp"):
            self.call("Input.dispatchKeyEvent", {"type": kind, "key": key, "code": key, "windowsVirtualKeyCode": code})

    def save_shot(self, path: Path) -> None:
        """Save a screenshot of the whole viewport at the device scale."""
        data = self.call("Page.captureScreenshot", {"format": "png", "captureBeyondViewport": False})["data"]
        path.write_bytes(base64.b64decode(data))

    def close(self) -> None:
        self.dt.call("Target.closeTarget", {"targetId": self.target})


# Page scripts shared by every recorder. Each is a function expression called with one argument.

# A transparent layer over the page, so stray pointer or wheel input cannot hover, seek or scroll while frames are taken.
SHIELD_JS = """() => {
  if (document.getElementById('capture-shield')) return true;
  const shield = document.createElement('div');
  shield.id = 'capture-shield';
  shield.style.cssText = 'position:fixed;inset:0;z-index:2147483647;background:transparent;';
  shield.addEventListener('wheel', (e) => e.preventDefault(), {passive: false});
  document.body.appendChild(shield);
  return true;
}"""

# Moves the race scrubber with a key (Home, ArrowRight) and waits for the transitions and staggered maps to settle.
# While stepping mid-race the button is given the pause icon it shows during playback.
RACE_KEY_JS = """async ([key, playing]) => {
  const input = document.querySelector('#collapse-race .race-scrub input');
  document.activeElement && document.activeElement.blur();
  input.dispatchEvent(new KeyboardEvent('keydown', {key, bubbles: true, cancelable: true}));
  await new Promise((r) => setTimeout(r, 520));
  const paths = document.querySelectorAll('#collapse-race .race-play svg path');
  if (playing && paths.length === 1) paths[0].setAttribute('d', 'M3 2h3v10H3zM8 2h3v10H8z');
  await new Promise((r) => requestAnimationFrame(() => requestAnimationFrame(r)));
  return input.getAttribute('aria-valuetext');
}"""

RACE_PIN_JS = """async (name) => {
  const cell = [...document.querySelectorAll('#collapse-race .race-map')]
    .find((li) => li.querySelector('.race-map-name').textContent.trim() === name);
  cell.click();
  document.activeElement && document.activeElement.blur();
  await new Promise((r) => setTimeout(r, 700));
  return cell.classList.contains('is-focus');
}"""

HIDE_CARET_JS = """() => {
  const style = document.createElement('style');
  style.textContent = '#lookup-input { caret-color: transparent; }';
  document.head.appendChild(style);
  return true;
}"""

# Clicks the busiest-type button and freezes the transitions it starts, so they can be sampled at fixed times.
MEASURE_REMOVE_JS = """async () => {
  const toy = document.querySelector('#measure-toy');
  const frame = () => new Promise((r) => requestAnimationFrame(() => requestAnimationFrame(r)));
  const button = [...toy.querySelectorAll('button')].find((b) => /busiest/i.test(b.textContent));
  button.click();
  await frame();
  window.captureHeld = document.getAnimations().filter((a) => toy.contains(a.effect && a.effect.target));
  window.captureHeld.forEach((a) => { a.pause(); a.currentTime = 0; });
  await frame();
  return button.disabled;
}"""

HELD_AT_JS = """async (ms) => {
  (window.captureHeld || []).forEach((a) => { if (ms === null) a.finish(); else a.currentTime = ms; });
  await new Promise((r) => requestAnimationFrame(() => requestAnimationFrame(r)));
  if (ms === null) await new Promise((r) => setTimeout(r, 350));
  return true;
}"""


def call_js(function: str, argument=None) -> str:
    return f"({function})({json.dumps(argument)})"


def write_plan(folder: Path, plan: dict) -> None:
    (folder / "plan.json").write_text(json.dumps(plan, indent=1) + "\n", encoding="utf-8")


def band(rect: dict, x_pad: float, top_pad: float, bottom_pad: float) -> list[int]:
    """Viewport box around ``rect`` in CSS pixels, padded and rounded outward."""
    return [int(rect["left"] - x_pad), int(rect["top"] - top_pad), int(np.ceil(rect["right"] + x_pad)),
            int(np.ceil(rect["bottom"] + bottom_pad))]


def scroll_stops(start: int, end: int, frames: int, split: int = 24) -> list[int]:
    """Scroll offsets from ``start`` to ``end`` eased in and out over ``frames`` steps.

    Repeated offsets are dropped, and a midpoint is added across any jump wider than ``split`` pixels so the fastest
    part of the scroll stays smooth. The list ends at ``end`` and excludes ``start``.
    """
    stops, last = [], start
    for i in range(1, frames + 1):
        t = i / frames
        eased = 4 * t**3 if t < 0.5 else 1 - (2 - 2 * t) ** 3 / 2
        offset = math.floor(start + (end - start) * eased + 0.5)
        if offset == last:
            continue
        if abs(offset - last) > split:
            stops.append((last + offset) // 2)
        stops.append(offset)
        last = offset
    return stops


# Recorders. Each saves full-viewport screenshots into ``folder`` and writes the plan that assembles them.

def race_plan(steps: int, head: dict, maps: dict) -> dict:
    """Plan for the race: steps 0 to ``steps``, then one attack pinned, cropped from the figure head to the maps."""
    frames = [[f"f{step:02d}.png", RACE_START_MS if step == 0 else RACE_END_MS if step == steps else RACE_STEP_MS]
              for step in range(steps + 1)]
    frames.append(["focus.png", RACE_FOCUS_MS])
    box = band({**head, "bottom": maps["bottom"]}, 16, 16, 12)
    return {"output": "collapse-race.gif", "scale": SCALE, "bands": [box], "frames": frames}


def record_collapse(tab: Tab, folder: Path, site: str) -> None:
    """Every removal step of the race, reached with the scrubber's arrow key, then one attack pinned from its map."""
    tab.resize(*DESKTOP)
    tab.open(site + "#collapse", "document.querySelector('#collapse-race .race-scrub input')")
    tab.scroll_to("#collapse-race", 72)
    tab.evaluate(call_js(SHIELD_JS))
    tab.evaluate(call_js(RACE_KEY_JS, ["Home", False]))
    tab.save_shot(folder / "f00.png")
    step, total = 0, None
    while step != total:
        text = tab.evaluate(call_js(RACE_KEY_JS, ["ArrowRight", True]))
        step, total = (int(v) for v in re.match(r"Step (\d+) of (\d+)", text).groups())
        tab.save_shot(folder / f"f{step:02d}.png")
    tab.evaluate(call_js(RACE_PIN_JS, RACE_FOCUS))
    tab.save_shot(folder / "focus.png")
    plan = race_plan(step, tab.rect("#collapse-race .figure-head"), tab.rect("#collapse-race .race-maps"))
    write_plan(folder, plan)


def record_measure(tab: Tab, folder: Path, site: str, samples: Sequence[int] = (0, 90, 180)) -> None:
    """The small network losing its busiest type until no route is left, sampling each transition."""
    tab.resize(*DESKTOP)
    tab.open(site + "#measure", "document.querySelector('#measure-toy')")
    tab.scroll_to("#measure-toy", 72)
    tab.evaluate(call_js(SHIELD_JS))
    tab.save_shot(folder / "s0_final.png")
    frames = [["s0_final.png", 1800]]
    step, done = 0, False
    while not done:
        step += 1
        done = tab.evaluate(call_js(MEASURE_REMOVE_JS))
        for ms in samples:
            tab.evaluate(call_js(HELD_AT_JS, ms))
            name = f"s{step}_t{ms:03d}.png"
            tab.save_shot(folder / name)
            frames.append([name, 80])
        tab.evaluate(call_js(HELD_AT_JS, None))
        tab.save_shot(folder / f"s{step}_final.png")
        frames.append([f"s{step}_final.png", 3600 if done else 1400])
    figure, body = tab.rect("#measure-toy"), tab.rect("#measure-toy .figure-body")
    box = band({**figure, "bottom": body["bottom"]}, 0, -16, 16)
    write_plan(folder, {"output": "measure-routes.gif", "scale": SCALE, "bands": [box], "frames": frames})


def lookup_scenes(name: str) -> list[tuple[str, int, int | None]]:
    """(label, duration in ms, scroll offset or None) for each lookup frame, in order.

    Typing ``name`` letter by letter, highlighting and choosing it, then scrolling the profile down to its removal
    panel and its strategy timing chart.
    """
    scenes = [("start", 1200, None), ("focus", 400, None)]
    scenes += [(f"type{i + 1}", 600 if i == len(name) - 1 else 200, None) for i in range(len(name))]
    scenes += [("highlight", 800, None), ("profile", 2200, None)]
    offset = 0
    for stop, steps, hold in LOOKUP_STOPS:
        scenes += [(f"scroll{y:03d}", hold if y == stop else LOOKUP_SCROLL_MS, y)
                   for y in scroll_stops(offset, stop, steps)]
        offset = stop
    return scenes


def lookup_plan(name: str, panel: dict) -> dict:
    """Plan for the lookup: every scene in order, cropped to ``panel`` below the site header."""
    frames = [[f"l{i:02d}_{label}.png", ms] for i, (label, ms, _) in enumerate(lookup_scenes(name))]
    box = band({**panel, "top": LOOKUP_TOP, "bottom": LOOKUP_TOP + LOOKUP_HEIGHT - 12}, 16, 12, 0)
    return {"output": f"lookup-{name.lower()}.gif", "scale": SCALE, "bands": [box], "frames": frames}


def record_lookup(tab: Tab, folder: Path, site: str, name: str = "ALIN7") -> None:
    """Typing a cell type name, choosing it from the list and scrolling through its profile beside the map."""
    tab.resize(*LOOKUP_VIEW)
    tab.open(site + "#lookup", "document.querySelector('#lookup-input')")
    base = tab.scroll_to("#lookup .fc-lookup", LOOKUP_TOP)
    panel = tab.rect("#lookup .fc-lookup")
    tab.evaluate(call_js(SHIELD_JS))
    tab.evaluate(call_js(HIDE_CARET_JS))
    typed = iter(name)
    for i, (label, _, offset) in enumerate(lookup_scenes(name)):
        if label == "focus":
            tab.evaluate("document.querySelector('#lookup-input').focus({preventScroll: true}) || true")
        elif label.startswith("type"):
            tab.insert_text(next(typed))
        elif label == "highlight":
            tab.press("ArrowDown", 40)
        elif label == "profile":
            tab.press("Enter", 13)
            time.sleep(0.7)
            tab.evaluate("(document.activeElement && document.activeElement.blur()) || true")
        elif offset is not None:
            tab.evaluate(f"window.scrollTo({{top: {base + offset}, behavior: 'instant'}}) || true")
        time.sleep(0.3)
        tab.save_shot(folder / f"l{i:02d}_{label}.png")
    write_plan(folder, lookup_plan(name, panel))


PHONE_SCREENS = (
    ("hero", "#", None, 0),
    ("findings", "#findings", "#findings-title", 76),
    ("chart", "#thresholds", "#thresholds .figure", 72),
    ("lookup", "#lookup/ALIN7", "#lookup-title", 80),
)


def record_phones(tab: Tab, folder: Path, site: str) -> None:
    """Four screens at phone width: the opening, the key results, a findings chart and a cell type profile."""
    tab.resize(*PHONE, mobile=True)
    tab.open(site, "document.getElementById('findings')")
    shots = []
    for label, anchor, selector, offset in PHONE_SCREENS:
        tab.evaluate(f"(() => {{ location.hash = {json.dumps(anchor)}; return true; }})()")
        time.sleep(1.2)
        if selector:
            tab.scroll_to(selector, offset)
        else:
            tab.evaluate("window.scrollTo({top: 0, behavior: 'instant'}) || true")
        tab.evaluate("(document.activeElement && document.activeElement.blur()) || true")
        time.sleep(0.8)
        tab.save_shot(folder / f"{label}.png")
        shots.append(f"{label}.png")
    write_plan(folder, {"output": "site-phone-strip.png", "shots": shots})


RECORDERS = {
    "collapse": record_collapse,
    "measure": record_measure,
    "lookup": record_lookup,
    "phones": record_phones,
}


# Frame handling and assembly.

def fit_width(image: Image.Image, width: int) -> Image.Image:
    """Resize ``image`` to ``width`` keeping its aspect ratio."""
    if image.width == width:
        return image
    return image.resize((width, round(image.height * width / image.width)), Image.Resampling.LANCZOS)


def same_frame(a: Image.Image, b: Image.Image) -> bool:
    """Whether two frames are pixel-identical."""
    return a.size == b.size and ImageChops.difference(a, b).getbbox() is None


def collapse_frames(frames: Sequence[Image.Image], durations: Sequence[int]) -> tuple[list[Image.Image], list[int]]:
    """Merge runs of identical consecutive frames into one frame whose duration is their sum."""
    kept: list[Image.Image] = []
    times: list[int] = []
    for frame, duration in zip(frames, durations):
        if kept and same_frame(kept[-1], frame):
            times[-1] += duration
        else:
            kept.append(frame)
            times.append(duration)
    return kept, times


def stack_bands(image: Image.Image, bands: Sequence[Sequence[int]], scale: float) -> Image.Image:
    """Crop each (left, top, right, bottom) CSS-pixel box of a screenshot and stack the crops vertically."""
    crops = [image.crop(tuple(round(v * scale) for v in box)) for box in bands]
    out = Image.new("RGB", (max(c.width for c in crops), sum(c.height for c in crops)), FIELD)
    y = 0
    for crop in crops:
        out.paste(crop, (0, y))
        y += crop.height
    return out


def shared_palette(frames: Sequence[Image.Image], colors: int, samples: int = 8, reserve: int = 32,
                   tolerance: int = 12, min_pixels: int = 16) -> Image.Image:
    """One adaptive palette for a whole clip, cut from evenly spaced frames so static regions never shimmer.

    An octree over the sampled frames fills all but ``reserve`` entries. The rest go, one at a time, to the colour
    covering at least ``min_pixels`` pixels that the palette matches worst, while that error exceeds ``tolerance`` in
    any channel, so small saturated marks such as legend swatches keep their hue. Unused slots repeat the first entry.
    """
    picks = sorted({round(i * (len(frames) - 1) / max(samples - 1, 1)) for i in range(samples)})
    width, height = frames[0].size
    sheet = Image.new("RGB", (width, height * len(picks)))
    for row, index in enumerate(picks):
        sheet.paste(frames[index], (0, row * height))
    reserve = min(reserve, colors - 1)
    base = sheet.quantize(colors=colors - reserve, method=Image.Quantize.FASTOCTREE, dither=Image.Dither.NONE)
    entries = np.array(base.getpalette()[: (colors - reserve) * 3], dtype=np.int16).reshape(-1, 3)

    pixels = np.asarray(sheet, dtype=np.int32).reshape(-1, 3)
    codes, counts = np.unique((pixels[:, 0] << 16) | (pixels[:, 1] << 8) | pixels[:, 2], return_counts=True)
    codes = codes[counts >= min_pixels]
    common = np.stack([codes >> 16, (codes >> 8) & 255, codes & 255], axis=1).astype(np.int16)
    error = np.full(len(common), 255, dtype=np.int16)
    for entry in entries:
        np.minimum(error, np.abs(common - entry).max(axis=1), out=error)
    extra = []
    while len(extra) < reserve and len(common) and error.max() > tolerance:
        colour = common[error.argmax()]
        extra.append(colour)
        np.minimum(error, np.abs(common - colour).max(axis=1), out=error)

    table = np.concatenate([entries, np.array(extra, dtype=np.int16).reshape(-1, 3)])
    table = np.concatenate([table, np.repeat(table[:1], 256 - len(table), axis=0)])
    palette = Image.new("P", (1, 1))
    palette.putpalette(table.astype(np.uint8).ravel().tolist())
    return palette


def save_gif(path, frames: Sequence[Image.Image], durations: Sequence[int], colors: int = GIF_COLORS) -> None:
    """Write an endlessly looping GIF on one shared palette.

    Repeated frames are merged, and pixels unchanged from the previous frame are written as transparent so each
    frame stores only what moved. ``colors`` must leave at least one of the 256 palette slots free.
    """
    if not 1 <= colors < 256:
        raise ValueError("colors must be between 1 and 255")
    kept, times = collapse_frames(frames, durations)
    palette = shared_palette(kept, colors)
    rgb = palette.getpalette()[: colors * 3]
    rgb += rgb[:3] * (256 - colors)
    # Quantizing against a padded palette can land on a padding slot; map those back to the real entry.
    remap = np.arange(256, dtype=np.uint8)
    remap[colors:] = 0
    clear = colors
    previous = None
    images = []
    for frame in kept:
        index = remap[np.asarray(frame.quantize(palette=palette, dither=Image.Dither.NONE))]
        written = index.copy()
        if previous is not None:
            written[index == previous] = clear
        previous = index
        image = Image.fromarray(written, "P")
        image.putpalette(rgb)
        images.append(image)
    images[0].save(path, save_all=True, append_images=images[1:], duration=times, loop=0, disposal=1,
                   transparency=clear, optimize=False)


def strip_layout(count: int, width: int, phone_width: int, margin: int) -> list[int]:
    """Left edges of ``count`` phone screens of ``phone_width`` spread evenly across ``width`` inside ``margin``."""
    if count == 1:
        return [(width - phone_width) // 2]
    gap = (width - 2 * margin - count * phone_width) / (count - 1)
    if gap < 0:
        raise ValueError("phone screens do not fit the strip")
    return [round(margin + i * (phone_width + gap)) for i in range(count)]


def rounded(image: Image.Image, radius: int, ground: tuple[int, int, int] = FIELD) -> Image.Image:
    """``image`` with rounded corners over a plain ``ground`` colour."""
    mask = Image.new("L", image.size, 0)
    ImageDraw.Draw(mask).rounded_rectangle((0, 0, image.width - 1, image.height - 1), radius, fill=255)
    out = Image.new("RGB", image.size, ground)
    out.paste(image, (0, 0), mask)
    return out


def assemble_gif(folder: Path, plan: dict, out: Path, width: int = GIF_WIDTH) -> Path:
    frames, durations = [], []
    for name, ms in plan["frames"]:
        with Image.open(folder / name) as shot:
            frames.append(fit_width(stack_bands(shot.convert("RGB"), plan["bands"], plan["scale"]), width))
        durations.append(ms)
    path = out / plan["output"]
    save_gif(path, frames, durations)
    return path


def assemble_strip(folder: Path, plan: dict, out: Path) -> Path:
    shots = []
    for name in plan["shots"]:
        with Image.open(folder / name) as shot:
            shots.append(rounded(fit_width(shot.convert("RGB"), PHONE_WIDTH), 24, STRIP_FIELD))
    height = max(s.height for s in shots) + 2 * STRIP_MARGIN
    strip = Image.new("RGB", (STRIP_WIDTH, height), STRIP_FIELD)
    for x, shot in zip(strip_layout(len(shots), STRIP_WIDTH, PHONE_WIDTH, STRIP_MARGIN), shots):
        strip.paste(shot, (x, STRIP_MARGIN))
    path = out / plan["output"]
    strip.save(path, optimize=True)
    return path


def assemble(frames_dir: Path, out: Path, scenes: Sequence[str]) -> list[Path]:
    """Build each scene's output in ``out`` from its folder of frames and ``plan.json`` under ``frames_dir``."""
    written = []
    for scene in scenes:
        folder = frames_dir / scene
        plan = json.loads((folder / "plan.json").read_text(encoding="utf-8"))
        builder = assemble_strip if "shots" in plan else assemble_gif
        written.append(builder(folder, plan, out))
    return written


def record(devtools_url: str, site: str, frames_dir: Path, scenes: Sequence[str]) -> None:
    devtools = DevTools(browser_endpoint(devtools_url))
    tab = Tab(devtools, *DESKTOP)
    try:
        for scene in scenes:
            folder = frames_dir / scene
            folder.mkdir(parents=True, exist_ok=True)
            RECORDERS[scene](tab, folder, site)
            print(f"Recorded {scene}")
    finally:
        tab.close()
        devtools.close()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("step", nargs="?", choices=("all", "record", "assemble"), default="all")
    parser.add_argument("--devtools", default=DEVTOOLS, help="HTTP address of Chrome's remote debugging port")
    parser.add_argument("--site", default=SITE)
    parser.add_argument("--frames", type=Path, default=FRAMES_DIR, help="folder holding one subfolder of frames per scene")
    parser.add_argument("--only", nargs="*", choices=sorted(RECORDERS), help="handle only these scenes")
    args = parser.parse_args()
    site = args.site if args.site.endswith("/") else args.site + "/"
    scenes = args.only or list(RECORDERS)
    if args.step in ("all", "record"):
        record(args.devtools, site, args.frames, scenes)
    if args.step in ("all", "assemble"):
        OUT_DIR.mkdir(parents=True, exist_ok=True)
        for path in assemble(args.frames, OUT_DIR, scenes):
            print(f"Wrote {path.relative_to(OUT_DIR.parent.parent)}")


if __name__ == "__main__":
    main()
