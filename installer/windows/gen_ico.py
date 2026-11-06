#!/usr/bin/env python3
"""gen_ico.py — gera superfastdm.ico (multi-tamanho) p/ o instalador Windows. Stdlib only.

Renderiza o mesmo ícone do app (quadrado verde em gradiente + seta branca) em
16/32/64/256 px e monta o .ico com entradas PNG (suportadas pelo Windows 7+).

Uso:  python3 gen_ico.py <saida.ico>
"""
import sys
import zlib
import struct


def _png_data(size):
    W = H = size
    top = (57, 196, 111)
    bot = (47, 158, 95)
    r_corner = W * 0.20
    x0, y0, x1, y1 = W * 0.04, W * 0.04, W * 0.96, W * 0.96
    cx = W / 2.0
    b = W * 0.34
    apex = W * 0.76
    ta = W * 0.26
    tc = W * 0.74

    def in_rounded(x, y):
        if x < x0 or x > x1 or y < y0 or y > y1:
            return False
        if x < x0 + r_corner and y < y0 + r_corner:
            return (x - (x0 + r_corner)) ** 2 + (y - (y0 + r_corner)) ** 2 <= r_corner ** 2
        if x > x1 - r_corner and y < y0 + r_corner:
            return (x - (x1 - r_corner)) ** 2 + (y - (y0 + r_corner)) ** 2 <= r_corner ** 2
        if x < x0 + r_corner and y > y1 - r_corner:
            return (x - (x0 + r_corner)) ** 2 + (y - (y1 - r_corner)) ** 2 <= r_corner ** 2
        if x > x1 - r_corner and y > y1 - r_corner:
            return (x - (x1 - r_corner)) ** 2 + (y - (y1 - r_corner)) ** 2 <= r_corner ** 2
        return True

    def in_tri(x, y):
        if y < b or y > apex:
            return False
        t = (y - b) / (apex - b)
        return (ta + (cx - ta) * t) <= x <= (tc + (cx - tc) * t)

    rows = bytearray()
    for y in range(H):
        rows.append(0)
        fy = y / max(1, H - 1)
        green = bytes((
            int(round(top[0] + (bot[0] - top[0]) * fy)),
            int(round(top[1] + (bot[1] - top[1]) * fy)),
            int(round(top[2] + (bot[2] - top[2]) * fy)),
        ))
        for x in range(W):
            if in_tri(x, y):
                rows += b"\xff\xff\xff\xff"
            elif in_rounded(x, y):
                rows += green + b"\xff"
            else:
                rows += b"\x00\x00\x00\x00"

    def chunk(typ, data):
        c = typ + data
        return struct.pack(">I", len(data)) + c + struct.pack(">I", zlib.crc32(c) & 0xffffffff)

    ihdr = struct.pack(">IIBBBBB", W, H, 8, 6, 0, 0, 0)
    return (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", ihdr)
            + chunk(b"IDAT", zlib.compress(bytes(rows), 9))
            + chunk(b"IEND", b""))


def main():
    out = sys.argv[1] if len(sys.argv) > 1 else "superfastdm.ico"
    sizes = [16, 32, 64, 256]
    datas = {s: _png_data(s) for s in sizes}
    n = len(sizes)
    offset = 6 + 16 * n
    entries = b""
    blob = b""
    for s in sizes:
        data = datas[s]
        w = s if s < 256 else 0
        entries += struct.pack("<BBBBHHII", w, w, 0, 0, 1, 32, len(data), offset)
        blob += data
        offset += len(data)
    with open(out, "wb") as f:
        f.write(struct.pack("<HHH", 0, 1, n))
        f.write(entries)
        f.write(blob)
    print("ico gerado: %s (%d imagens: %s)" % (out, n, ", ".join(map(str, sizes))))


if __name__ == "__main__":
    main()
