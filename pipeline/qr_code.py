"""Encode short byte strings as QR codes (ISO/IEC 18004, byte mode, versions 1 to 10)."""

import numpy as np

EC_LEVELS = ("L", "M", "Q", "H")
FORMAT_BITS = {"L": 1, "M": 0, "Q": 3, "H": 2}

# Per version and level: (EC codewords per block, [(block count, data codewords per block), ...]).
BLOCKS = {
    1: {"L": (7, [(1, 19)]), "M": (10, [(1, 16)]), "Q": (13, [(1, 13)]), "H": (17, [(1, 9)])},
    2: {"L": (10, [(1, 34)]), "M": (16, [(1, 28)]), "Q": (22, [(1, 22)]), "H": (28, [(1, 16)])},
    3: {"L": (15, [(1, 55)]), "M": (26, [(1, 44)]), "Q": (18, [(2, 17)]), "H": (22, [(2, 13)])},
    4: {"L": (20, [(1, 80)]), "M": (18, [(2, 32)]), "Q": (26, [(2, 24)]), "H": (16, [(4, 9)])},
    5: {"L": (26, [(1, 108)]), "M": (24, [(2, 43)]), "Q": (18, [(2, 15), (2, 16)]), "H": (22, [(2, 11), (2, 12)])},
    6: {"L": (18, [(2, 68)]), "M": (16, [(4, 27)]), "Q": (24, [(4, 19)]), "H": (28, [(4, 15)])},
    7: {"L": (20, [(2, 78)]), "M": (18, [(4, 31)]), "Q": (18, [(2, 14), (4, 15)]), "H": (26, [(4, 13), (1, 14)])},
    8: {"L": (24, [(2, 97)]), "M": (22, [(2, 38), (2, 39)]), "Q": (22, [(4, 18), (2, 19)]),
        "H": (26, [(4, 14), (2, 15)])},
    9: {"L": (30, [(2, 116)]), "M": (22, [(3, 36), (2, 37)]), "Q": (20, [(4, 16), (4, 17)]),
        "H": (24, [(4, 12), (4, 13)])},
    10: {"L": (18, [(2, 68), (2, 69)]), "M": (26, [(4, 43), (1, 44)]), "Q": (24, [(6, 19), (2, 20)]),
         "H": (28, [(6, 15), (2, 16)])},
}
ALIGNMENT = {1: [], 2: [6, 18], 3: [6, 22], 4: [6, 26], 5: [6, 30], 6: [6, 34], 7: [6, 22, 38], 8: [6, 24, 42],
             9: [6, 26, 46], 10: [6, 28, 50]}

_EXP = [0] * 512
_LOG = [0] * 256
_value = 1
for _i in range(255):
    _EXP[_i] = _value
    _LOG[_value] = _i
    _value <<= 1
    if _value & 0x100:
        _value ^= 0x11D
for _i in range(255, 512):
    _EXP[_i] = _EXP[_i - 255]


def gf_multiply(a: int, b: int) -> int:
    """Product in GF(256) with the QR primitive polynomial x^8 + x^4 + x^3 + x^2 + 1."""
    if a == 0 or b == 0:
        return 0
    return _EXP[_LOG[a] + _LOG[b]]


def reed_solomon_generator(degree: int) -> list[int]:
    """Coefficients of prod (x - 2^i) for i < degree, highest power first, leading 1 dropped."""
    poly = [1]
    for i in range(degree):
        nxt = [0] * (len(poly) + 1)
        for j, coef in enumerate(poly):
            nxt[j] ^= coef
            nxt[j + 1] ^= gf_multiply(coef, _EXP[i])
        poly = nxt
    return poly[1:]


def reed_solomon_remainder(data: list[int], degree: int) -> list[int]:
    """Error-correction codewords for one block."""
    generator = reed_solomon_generator(degree)
    remainder = [0] * degree
    for byte in data:
        factor = byte ^ remainder.pop(0)
        remainder.append(0)
        for i, coef in enumerate(generator):
            remainder[i] ^= gf_multiply(coef, factor)
    return remainder


def data_capacity(version: int, level: str) -> int:
    """Data codewords available at a version and error-correction level."""
    return sum(count * size for count, size in BLOCKS[version][level][1])


def choose_version(n_bytes: int, level: str) -> int:
    """Smallest version whose byte-mode capacity holds ``n_bytes``."""
    for version in BLOCKS:
        header_bits = 4 + (8 if version < 10 else 16)
        if header_bits + 8 * n_bytes <= 8 * data_capacity(version, level):
            return version
    raise ValueError(f"{n_bytes} bytes do not fit in version 10 at level {level}")


def data_codewords(payload: bytes, version: int, level: str) -> list[int]:
    """Mode indicator, length, payload, terminator and padding, as codewords."""
    capacity = data_capacity(version, level) * 8
    bits = [0, 1, 0, 0]
    count_bits = 8 if version < 10 else 16
    bits += [(len(payload) >> (count_bits - 1 - i)) & 1 for i in range(count_bits)]
    for byte in payload:
        bits += [(byte >> (7 - i)) & 1 for i in range(8)]
    bits += [0] * min(4, capacity - len(bits))
    bits += [0] * (-len(bits) % 8)
    codewords = [int("".join(map(str, bits[i:i + 8])), 2) for i in range(0, len(bits), 8)]
    pad = (0xEC, 0x11)
    while len(codewords) < capacity // 8:
        codewords.append(pad[(len(codewords) - len(bits) // 8) % 2])
    return codewords


def interleave(codewords: list[int], version: int, level: str) -> list[int]:
    """Split data into blocks, append error correction, and interleave as the standard requires."""
    ec_size, groups = BLOCKS[version][level]
    blocks, start = [], 0
    for count, size in groups:
        for _ in range(count):
            blocks.append(codewords[start:start + size])
            start += size
    ec_blocks = [reed_solomon_remainder(block, ec_size) for block in blocks]
    out = []
    for i in range(max(len(b) for b in blocks)):
        out += [b[i] for b in blocks if i < len(b)]
    for i in range(ec_size):
        out += [b[i] for b in ec_blocks]
    return out


def format_bits(level: str, mask: int) -> int:
    """15-bit format information: level and mask with BCH(15, 5) check bits, XOR 0x5412."""
    data = FORMAT_BITS[level] << 3 | mask
    rem = data
    for _ in range(10):
        rem = (rem << 1) ^ ((rem >> 9) * 0x537)
    return (data << 10 | rem) ^ 0x5412


def version_bits(version: int) -> int:
    """18-bit version information with BCH(18, 6) check bits."""
    rem = version
    for _ in range(12):
        rem = (rem << 1) ^ ((rem >> 11) * 0x1F25)
    return version << 12 | rem


def _mask(pattern: int, x: np.ndarray, y: np.ndarray) -> np.ndarray:
    return [
        (x + y) % 2 == 0,
        y % 2 == 0,
        x % 3 == 0,
        (x + y) % 3 == 0,
        (x // 3 + y // 2) % 2 == 0,
        x * y % 2 + x * y % 3 == 0,
        (x * y % 2 + x * y % 3) % 2 == 0,
        ((x + y) % 2 + x * y % 3) % 2 == 0,
    ][pattern]


class _Grid:
    def __init__(self, version: int):
        self.version = version
        self.size = 17 + 4 * version
        self.modules = np.zeros((self.size, self.size), dtype=bool)
        self.function = np.zeros((self.size, self.size), dtype=bool)

    def set(self, x: int, y: int, dark: bool) -> None:
        self.modules[y, x] = dark
        self.function[y, x] = True

    def draw_function_patterns(self) -> None:
        size = self.size
        for i in range(size):
            self.set(6, i, i % 2 == 0)
            self.set(i, 6, i % 2 == 0)
        for cx, cy in ((3, 3), (size - 4, 3), (3, size - 4)):
            for dy in range(-4, 5):
                for dx in range(-4, 5):
                    x, y = cx + dx, cy + dy
                    if 0 <= x < size and 0 <= y < size:
                        ring = max(abs(dx), abs(dy))
                        self.set(x, y, ring not in (2, 4))
        centers = ALIGNMENT[self.version]
        last = len(centers) - 1
        for i, cx in enumerate(centers):
            for j, cy in enumerate(centers):
                if (i == 0 and j == 0) or (i == 0 and j == last) or (i == last and j == 0):
                    continue
                for dy in range(-2, 3):
                    for dx in range(-2, 3):
                        self.set(cx + dx, cy + dy, max(abs(dx), abs(dy)) != 1)
        self.draw_format(0, "M")
        if self.version >= 7:
            bits = version_bits(self.version)
            for i in range(18):
                dark = bool((bits >> i) & 1)
                a, b = size - 11 + i % 3, i // 3
                self.set(a, b, dark)
                self.set(b, a, dark)

    def draw_format(self, mask: int, level: str) -> None:
        size = self.size
        bits = format_bits(level, mask)
        bit = [bool((bits >> i) & 1) for i in range(15)]
        for i in range(6):
            self.set(8, i, bit[i])
        self.set(8, 7, bit[6])
        self.set(8, 8, bit[7])
        self.set(7, 8, bit[8])
        for i in range(9, 15):
            self.set(14 - i, 8, bit[i])
        for i in range(8):
            self.set(size - 1 - i, 8, bit[i])
        for i in range(8, 15):
            self.set(8, size - 15 + i, bit[i])
        self.set(8, size - 8, True)

    def place_data(self, codewords: list[int]) -> None:
        size = self.size
        total = len(codewords) * 8
        i = 0
        right = size - 1
        while right >= 1:
            if right == 6:
                right = 5
            for vert in range(size):
                for j in range(2):
                    x = right - j
                    upward = ((right + 1) & 2) == 0
                    y = size - 1 - vert if upward else vert
                    if not self.function[y, x] and i < total:
                        self.modules[y, x] = bool((codewords[i >> 3] >> (7 - (i & 7))) & 1)
                        i += 1
            right -= 2


def penalty(modules: np.ndarray) -> int:
    """Mask penalty score from the four rules of the standard."""
    size = len(modules)
    score = 0
    for lines in (modules, modules.T):
        for line in lines:
            run, prev = 0, None
            for value in line:
                if value == prev:
                    run += 1
                else:
                    if run >= 5:
                        score += run - 2
                    run, prev = 1, value
            if run >= 5:
                score += run - 2
            text = "".join("1" if v else "0" for v in line)
            score += 40 * (text.count("10111010000") + text.count("00001011101"))
    blocks = modules[:-1, :-1] == modules[1:, :-1]
    blocks &= modules[:-1, :-1] == modules[:-1, 1:]
    blocks &= modules[:-1, :-1] == modules[1:, 1:]
    score += 3 * int(blocks.sum())
    dark = int(modules.sum())
    score += 10 * (abs(dark * 20 - size * size * 10) // (size * size))
    return score


def encode(text: str, level: str = "M", mask: int | None = None) -> np.ndarray:
    """Boolean module matrix (True is dark) for ``text`` in byte mode, without the quiet zone."""
    if level not in EC_LEVELS:
        raise ValueError(f"unknown error-correction level {level!r}")
    payload = text.encode("utf-8")
    version = choose_version(len(payload), level)
    codewords = interleave(data_codewords(payload, version, level), version, level)
    grid = _Grid(version)
    grid.draw_function_patterns()
    grid.place_data(codewords)
    y, x = np.indices((grid.size, grid.size))
    best, best_score = None, None
    for candidate in range(8) if mask is None else [mask]:
        modules = grid.modules ^ (_mask(candidate, x, y) & ~grid.function)
        trial = _Grid(version)
        trial.modules, trial.function = modules.copy(), grid.function.copy()
        trial.draw_format(candidate, level)
        score = penalty(trial.modules)
        if best_score is None or score < best_score:
            best, best_score = trial.modules, score
    return best
