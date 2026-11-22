"""A small QR code generator, so the PC window can show the phone link.

Byte mode, error correction L or M, versions 1-6: enough for the phone link
(about 90 characters, version 5 at L). No version-information block is needed
below version 7, which is why the range stops there.

Why it is written here: installing a QR package on the PC was refused, and the
link must not be sent to an online QR service because it carries a secret.
tests/test_pc_monitor_phone.py checks every module of its output, for every
mask, against an independent implementation already on this PC (the
qrcode-terminal package Expo installs under mobile/node_modules), across
versions 1-6 and both levels.

The construction follows ISO/IEC 18004 as laid out in Project Nayuki's QR Code
generator (MIT): function patterns, Reed-Solomon over GF(256) with 0x11D,
block interleaving, the zigzag placement, the eight masks and the BCH-coded
format bits.
"""

from __future__ import annotations

# Per version 1-6: (EC codewords per block, number of blocks), by level.
_EC = {
    "L": [None, (7, 1), (10, 1), (15, 1), (20, 1), (26, 1), (18, 2)],
    "M": [None, (10, 1), (16, 1), (26, 1), (18, 2), (24, 2), (16, 4)],
}
_FORMAT_BITS = {"L": 1, "M": 0}
MAX_VERSION = 6


def _raw_data_modules(ver: int) -> int:
    result = (16 * ver + 128) * ver + 64
    if ver >= 2:
        numalign = ver // 7 + 2
        result -= (25 * numalign - 10) * numalign - 55
        if ver >= 7:
            result -= 36
    return result


def _data_codewords(ver: int, ecl: str) -> int:
    per_block, blocks = _EC[ecl][ver]
    return _raw_data_modules(ver) // 8 - per_block * blocks


def _gf_mul(x: int, y: int) -> int:
    z = 0
    for i in reversed(range(8)):
        z = (z << 1) ^ ((z >> 7) * 0x11D)
        z ^= ((y >> i) & 1) * x
    return z


def _rs_divisor(degree: int) -> list[int]:
    result = [0] * (degree - 1) + [1]
    root = 1
    for _ in range(degree):
        for j in range(degree):
            result[j] = _gf_mul(result[j], root)
            if j + 1 < degree:
                result[j] ^= result[j + 1]
        root = _gf_mul(root, 0x02)
    return result


def _rs_remainder(data: list[int], divisor: list[int]) -> list[int]:
    result = [0] * len(divisor)
    for b in data:
        factor = b ^ result.pop(0)
        result.append(0)
        for i, coef in enumerate(divisor):
            result[i] ^= _gf_mul(coef, factor)
    return result


def _codewords(text: bytes, ver: int, ecl: str) -> list[int]:
    """The data bits, padded, split into blocks, error-corrected, interleaved."""
    capacity = _data_codewords(ver, ecl) * 8
    bits: list[int] = []

    def put(value: int, n: int) -> None:
        bits.extend((value >> i) & 1 for i in reversed(range(n)))

    put(0b0100, 4)              # byte mode
    put(len(text), 8)           # character count: 8 bits for versions 1-9
    for b in text:
        put(b, 8)
    put(0, min(4, capacity - len(bits)))
    put(0, (-len(bits)) % 8)
    pad = 0xEC
    while len(bits) < capacity:
        put(pad, 8)
        pad ^= 0xEC ^ 0x11
    data = [int("".join(map(str, bits[i:i + 8])), 2) for i in range(0, len(bits), 8)]

    per_block, num_blocks = _EC[ecl][ver]
    raw = _raw_data_modules(ver) // 8
    num_short = num_blocks - raw % num_blocks
    short_len = raw // num_blocks
    divisor = _rs_divisor(per_block)
    blocks, k = [], 0
    for i in range(num_blocks):
        dat = data[k:k + short_len - per_block + (0 if i < num_short else 1)]
        k += len(dat)
        ecc = _rs_remainder(dat, divisor)
        if i < num_short:
            dat = dat + [0]
        blocks.append(dat + ecc)
    out = []
    for i in range(len(blocks[0])):
        for j, blk in enumerate(blocks):
            if i != short_len - per_block or j >= num_short:
                out.append(blk[i])
    return out


def _mask_bit(mask: int, x: int, y: int) -> bool:
    return [
        (x + y) % 2 == 0,
        y % 2 == 0,
        x % 3 == 0,
        (x + y) % 3 == 0,
        (x // 3 + y // 2) % 2 == 0,
        x * y % 2 + x * y % 3 == 0,
        (x * y % 2 + x * y % 3) % 2 == 0,
        ((x + y) % 2 + x * y % 3) % 2 == 0,
    ][mask]


def _build(text: bytes, ver: int, ecl: str, mask: int) -> list[list[bool]]:
    size = ver * 4 + 17
    mods = [[False] * size for _ in range(size)]
    func = [[False] * size for _ in range(size)]

    def setf(x: int, y: int, dark: bool) -> None:
        mods[y][x] = dark
        func[y][x] = True

    for i in range(size):                                   # timing patterns
        setf(6, i, i % 2 == 0)
        setf(i, 6, i % 2 == 0)
    for cx, cy in ((3, 3), (size - 4, 3), (3, size - 4)):   # finder patterns + separators
        for dy in range(-4, 5):
            for dx in range(-4, 5):
                x, y = cx + dx, cy + dy
                if 0 <= x < size and 0 <= y < size:
                    setf(x, y, max(abs(dx), abs(dy)) not in (2, 4))
    if ver > 1:                                             # alignment patterns
        numalign = ver // 7 + 2
        step = (ver * 8 + numalign * 3 + 5) // (numalign * 4 - 4) * 2
        pos = list(reversed([size - 7 - i * step for i in range(numalign - 1)] + [6]))
        last = len(pos) - 1
        for i, px in enumerate(pos):
            for j, py in enumerate(pos):
                if (i, j) in ((0, 0), (0, last), (last, 0)):
                    continue
                for dy in range(-2, 3):
                    for dx in range(-2, 3):
                        setf(px + dx, py + dy, max(abs(dx), abs(dy)) != 1)

    def draw_format(m: int) -> None:
        data = _FORMAT_BITS[ecl] << 3 | m
        rem = data
        for _ in range(10):
            rem = (rem << 1) ^ ((rem >> 9) * 0x537)
        bits = (data << 10 | rem) ^ 0x5412
        bit = lambda i: (bits >> i) & 1 == 1  # noqa: E731
        for i in range(6):
            setf(8, i, bit(i))
        setf(8, 7, bit(6))
        setf(8, 8, bit(7))
        setf(7, 8, bit(8))
        for i in range(9, 15):
            setf(14 - i, 8, bit(i))
        for i in range(8):
            setf(size - 1 - i, 8, bit(i))
        for i in range(8, 15):
            setf(8, size - 15 + i, bit(i))
        setf(8, size - 8, True)                             # the dark module

    draw_format(0)                                          # reserve the format areas
    data = _codewords(text, ver, ecl)
    i, right = 0, size - 1
    while right >= 1:                                       # zigzag placement
        if right == 6:
            right = 5
        for vert in range(size):
            for j in range(2):
                x = right - j
                y = size - 1 - vert if (right + 1) & 2 == 0 else vert
                if not func[y][x] and i < len(data) * 8:
                    mods[y][x] = (data[i >> 3] >> (7 - (i & 7))) & 1 == 1
                    i += 1
        right -= 2
    for y in range(size):
        for x in range(size):
            if not func[y][x] and _mask_bit(mask, x, y):
                mods[y][x] = not mods[y][x]
    draw_format(mask)
    return mods


def _penalty(m: list[list[bool]]) -> int:
    """Long runs, 2x2 blocks and dark/light balance (ISO rules 1, 2 and 4).
    Any mask scans; this only prefers the cleaner-looking one."""
    n, score = len(m), 0
    for lines in (m, [list(col) for col in zip(*m)]):
        for line in lines:
            run = 1
            for a, b in zip(line, line[1:]):
                if a == b:
                    run += 1
                else:
                    score += run - 2 if run >= 5 else 0
                    run = 1
            score += run - 2 if run >= 5 else 0
    for y in range(n - 1):
        for x in range(n - 1):
            if m[y][x] == m[y][x + 1] == m[y + 1][x] == m[y + 1][x + 1]:
                score += 3
    dark = sum(sum(r) for r in m)
    score += (abs(dark * 20 - n * n * 10) + n * n - 1) // (n * n) * 10
    return score


def smallest_version(text: bytes, ecl: str) -> int:
    for ver in range(1, MAX_VERSION + 1):
        if 12 + len(text) * 8 <= _data_codewords(ver, ecl) * 8:
            return ver
    raise ValueError(f"{len(text)} bytes is too long for a version {MAX_VERSION} QR code at level {ecl}")


def encode(text: str, ecl: str = "L", mask: int | None = None,
           version: int | None = None) -> list[list[bool]]:
    """The module matrix (True = dark) for `text`, rows top to bottom."""
    data = text.encode("utf-8")
    ver = version or smallest_version(data, ecl)
    if mask is not None:
        return _build(data, ver, ecl, mask)
    return min((_build(data, ver, ecl, m) for m in range(8)), key=_penalty)


def svg(text: str, ecl: str = "L", scale: int = 6, border: int = 4) -> str:
    """The QR code as a standalone SVG, black on white with a quiet zone."""
    m = encode(text, ecl)
    n = len(m) + border * 2
    path = "".join(f"M{x + border},{y + border}h1v1h-1z"
                   for y, row in enumerate(m) for x, dark in enumerate(row) if dark)
    return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {n} {n}" width="{n * scale}" '
            f'height="{n * scale}" shape-rendering="crispEdges"><rect width="{n}" height="{n}" '
            f'fill="#fff"/><path d="{path}" fill="#000"/></svg>')
