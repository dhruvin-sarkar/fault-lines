"""Record README animations and a phone-width strip of the site from an already-running Chrome.

Chrome must have been started with ``--remote-debugging-port``; this module connects to it over the
DevTools protocol, opens one tab of its own, and closes that tab when it is done.
"""

import argparse
import base64
import hashlib
import io
import json
import os
import socket
import struct
import time
import urllib.parse
import urllib.request
from collections.abc import Callable, Sequence
from dataclasses import dataclass

from PIL import Image, ImageChops, ImageDraw

from pipeline.common import ASSETS

OUT_DIR = ASSETS / "readme"
SITE = "http://localhost:5173/fault-lines/"
DEVTOOLS = "http://127.0.0.1:9222"
GIF_WIDTH = 880
STRIP_WIDTH = 1760
FIELD = (0, 0, 0)
WS_GUID = "258EAFA5-E914-47DA-95CA-C5AB0DC85B11"


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
            f"No Chrome DevTools endpoint at {devtools} ({error}). Start Chrome with "
            "--remote-debugging-port=9222 and run the site with `npm run dev` in web/, then try again."
        ) from error


class Tab:
    """One tab opened in the running browser, driven through a flat session."""

    def __init__(self, devtools: DevTools, width: int, height: int, scale: float = 1, mobile: bool = False) -> None:
        self.dt = devtools
        self.target = devtools.call("Target.createTarget", {"url": "about:blank"})["targetId"]
        self.session = devtools.call("Target.attachToTarget", {"targetId": self.target, "flatten": True})["sessionId"]
        self.call("Page.enable")
        self.resize(width, height, scale, mobile)

    def call(self, method: str, params: dict | None = None) -> dict:
        return self.dt.call(method, params, self.session)

    def resize(self, width: int, height: int, scale: float = 1, mobile: bool = False) -> None:
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
        time.sleep(0.6)

    def scroll_to(self, selector: str, offset: int = 72) -> None:
        self.evaluate(
            f"(() => {{ const el = document.querySelector({json.dumps(selector)});"
            f" window.scrollTo(0, el.getBoundingClientRect().top + window.scrollY - {offset}); return true; }})()"
        )
        time.sleep(0.5)

    def rect(self, selector: str) -> dict:
        """Viewport rectangle of the first element matching ``selector``."""
        return self.evaluate(
            f"(() => {{ const r = document.querySelector({json.dumps(selector)}).getBoundingClientRect();"
            " return {x: r.left, y: r.top, width: r.width, height: r.height}; })()"
        )

    def click(self, expression: str) -> None:
        """Click the element returned by the JavaScript ``expression``."""
        self.evaluate(f"(() => {{ ({expression}).click(); return true; }})()")

    def type_text(self, selector: str, text: str, delay: float, on_key: Callable[[], None] | None = None) -> None:
        self.evaluate(f"(() => {{ document.querySelector({json.dumps(selector)}).focus(); return true; }})()")
        for ch in text:
            self.call("Input.insertText", {"text": ch})
            time.sleep(delay)
            if on_key:
                on_key()

    def press(self, key: str, code: int) -> None:
        for kind in ("keyDown", "keyUp"):
            self.call("Input.dispatchKeyEvent", {"type": kind, "key": key, "code": key, "windowsVirtualKeyCode": code})

    def shot(self, clip: dict | None = None) -> Image.Image:
        """Screenshot of the viewport, or of ``clip`` in viewport coordinates, as an RGB image."""
        params: dict = {"format": "png", "captureBeyondViewport": False}
        if clip:
            params["clip"] = {**clip, "scale": 1}
        data = self.call("Page.captureScreenshot", params)["data"]
        return Image.open(io.BytesIO(base64.b64decode(data))).convert("RGB")

    def close(self) -> None:
        self.dt.call("Target.closeTarget", {"targetId": self.target})


# Frame handling.

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


def save_gif(path, frames: Sequence[Image.Image], durations: Sequence[int], colors: int = 160) -> None:
    """Write an endlessly looping GIF, collapsing repeated frames and quantizing each to ``colors``."""
    kept, times = collapse_frames(frames, durations)
    palette_frames = [f.quantize(colors=colors, method=Image.Quantize.MEDIANCUT, dither=Image.Dither.NONE) for f in kept]
    palette_frames[0].save(path, save_all=True, append_images=palette_frames[1:], duration=times, loop=0,
                           disposal=1, optimize=False)


def strip_layout(count: int, width: int, phone_width: int, margin: int) -> list[int]:
    """Left edges of ``count`` phone screens of ``phone_width`` spread evenly across ``width`` inside ``margin``."""
    if count == 1:
        return [(width - phone_width) // 2]
    gap = (width - 2 * margin - count * phone_width) / (count - 1)
    if gap < 0:
        raise ValueError("phone screens do not fit the strip")
    return [round(margin + i * (phone_width + gap)) for i in range(count)]


def rounded(image: Image.Image, radius: int) -> Image.Image:
    """``image`` with rounded corners over the black field."""
    mask = Image.new("L", image.size, 0)
    ImageDraw.Draw(mask).rounded_rectangle((0, 0, image.width - 1, image.height - 1), radius, fill=255)
    ground = Image.new("RGB", image.size, FIELD)
    ground.paste(image, (0, 0), mask)
    return ground


@dataclass
class Recorder:
    """Collects frames from a clip of the tab, each with its display duration."""

    tab: Tab
    selector: str
    frames: list
    durations: list

    def grab(self, duration: int) -> None:
        r = self.tab.rect(self.selector)
        top = max(r["y"], 0)
        clip = {"x": r["x"], "y": top, "width": r["width"], "height": min(r["height"], self.tab.height - top)}
        self.frames.append(fit_width(self.tab.shot(clip), GIF_WIDTH))
        self.durations.append(duration)


# Scenes.

def collapse_race(tab: Tab, out, site: str) -> None:
    """The race between the six removal orders, played from the first batch to the last."""
    tab.open(site + "#collapse", "document.querySelector('#collapse-race .race-play')")
    tab.scroll_to("#collapse-race")
    rec = Recorder(tab, "#collapse-race", [], [])
    rec.grab(1200)
    tab.click("document.querySelector('#collapse-race .race-play')")
    for _ in range(90):
        time.sleep(0.12)
        rec.grab(120)
        if tab.evaluate("/replay/i.test(document.querySelector('#collapse-race .race-play').textContent)"):
            break
    rec.grab(2400)
    save_gif(out / "collapse-race.gif", rec.frames, rec.durations)


def measure_routes(tab: Tab, out, site: str) -> None:
    """The small network in the measure section losing its busiest types one at a time."""
    tab.open(site + "#measure", "document.querySelector('#measure-toy')")
    tab.scroll_to("#measure-toy")
    rec = Recorder(tab, "#measure-toy", [], [])
    rec.grab(1600)
    button = "[...document.querySelectorAll('#measure-toy button')].find(b => /busiest/i.test(b.textContent))"
    for _ in range(8):
        if tab.evaluate(f"({button}).disabled"):
            break
        tab.click(button)
        time.sleep(0.5)
        rec.grab(1100)
    rec.grab(2400)
    save_gif(out / "measure-routes.gif", rec.frames, rec.durations)


def lookup_type(tab: Tab, out, site: str, name: str = "ALIN7") -> None:
    """Looking up one cell type by name and opening its profile."""
    tab.open(site + "#lookup", "document.querySelector('#lookup-input')")
    tab.scroll_to("#lookup")
    rec = Recorder(tab, "#lookup", [], [])
    rec.grab(1000)
    tab.type_text("#lookup-input", name, 0.18, on_key=lambda: rec.grab(180))
    time.sleep(0.4)
    rec.grab(700)
    tab.click("document.querySelector('#lookup-listbox [role=option]')")
    time.sleep(1.2)
    rec.grab(3200)
    save_gif(out / f"lookup-{name.lower()}.gif", rec.frames, rec.durations)


def phone_strip(tab: Tab, out, site: str, anchors: Sequence[str] = ("main", "findings", "methods")) -> None:
    """Three screens of the site at phone width, side by side on the black field."""
    tab.resize(390, 844, scale=2, mobile=True)
    phone_width, margin = 500, 64
    shots = []
    for anchor in anchors:
        tab.open(site + f"#{anchor}", f"document.getElementById({json.dumps(anchor)})")
        if anchor != "main":
            tab.scroll_to(f"#{anchor}", offset=0)
        else:
            tab.evaluate("window.scrollTo(0, 0) || true")
            time.sleep(0.5)
        shots.append(rounded(fit_width(tab.shot(), phone_width), 28))
    height = max(s.height for s in shots) + 2 * margin
    strip = Image.new("RGB", (STRIP_WIDTH, height), FIELD)
    for x, shot in zip(strip_layout(len(shots), STRIP_WIDTH, phone_width, margin), shots):
        strip.paste(shot, (x, margin))
    strip.save(out / "site-phone-strip.png", optimize=True)


SCENES = {
    "collapse": collapse_race,
    "measure": measure_routes,
    "lookup": lookup_type,
    "phones": phone_strip,
}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--devtools", default=DEVTOOLS, help="HTTP address of Chrome's remote debugging port")
    parser.add_argument("--site", default=SITE)
    parser.add_argument("--only", nargs="*", choices=sorted(SCENES), help="record only these scenes")
    args = parser.parse_args()
    site = args.site if args.site.endswith("/") else args.site + "/"
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    devtools = DevTools(browser_endpoint(args.devtools))
    tab = Tab(devtools, 1280, 900)
    try:
        for name in args.only or SCENES:
            if name != "phones":
                tab.resize(1280, 900)
            SCENES[name](tab, OUT_DIR, site)
            print(f"Recorded {name}")
    finally:
        tab.close()
        devtools.close()


if __name__ == "__main__":
    main()
