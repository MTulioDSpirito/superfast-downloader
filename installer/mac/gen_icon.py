#!/usr/bin/env python3
"""gen_icon.py — gera o iconset (PNGs) do ícone do SuperFast DM. Stdlib only.

Desenha um quadrado arredondado com gradiente verde e uma seta de download
branca (mesma identidade visual da UI: --acc #2f9e5f / --acc2 #39c46f).

Uso:  python3 gen_icon.py <dir-destino-do-iconset>
Gera os 10 PNGs exigidos por um .iconset do macOS.
"""
import os
import sys
import zlib
import struct


def _png_data(size):
    """Retorna os bytes de um PNG RGBA do ícone no tamanho dado."""
    W = H = size
    top = (57, 196, 111)        # #39c46f
    bot = (47, 158, 95)         # #2f9e5f
    r_corner = W * 0.20
    x0, y0, x1, y1 = W * 0.04, W * 0.04, W * 0.96, W * 0.96
    cx = W / 2.0
    b = W * 0.34                 # topo do triângulo
    apex = W * 0.76              # ápice (baixo) do triângulo
    ta = W * 0.26                 # canto superior esquerdo
    tc = W * 0.74                 # canto superior direito

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
        rows.append(0)  # filtro de linha (None)
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

    ihdr = struct.pack(">IIBBBBB", W, H, 8, 6, 0, 0, 0)  # 8-bit RGBA
    return (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", ihdr)
            + chunk(b"IDAT", zlib.compress(bytes(rows), 9))
            + chunk(b"IEND", b""))


def main():
    out = sys.argv[1] if len(sys.argv) > 1 else "."
    os.makedirs(out, exist_ok=True)
    # os 10 arquivos exigidos por um .iconset do macOS
    targets = [
        (16, "icon_16x16.png"),
        (32, "icon_16x16@2x.png"),
        (32, "icon_32x32.png"),
        (64, "icon_32x32@2x.png"),
        (128, "icon_128x128.png"),
        (256, "icon_128x128@2x.png"),
        (256, "icon_256x256.png"),
        (512, "icon_256x256@2x.png"),
        (512, "icon_512x512.png"),
        (1024, "icon_512x512@2x.png"),
    ]
    cache = {}
    for size, name in targets:
        if size not in cache:
            cache[size] = _png_data(size)
            print("  renderizou %dpx" % size, flush=True)
        with open(os.path.join(out, name), "wb") as f:
            f.write(cache[size])
    print("iconset pronto em: %s (%d arquivos)" % (out, len(os.listdir(out))), flush=True)


if __name__ == "__main__":
    main()
