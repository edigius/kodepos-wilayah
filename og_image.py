#!/usr/bin/env python3
"""Generate og-image.png (1200x630) for Kode Pos & Wilayah."""
from PIL import Image, ImageDraw, ImageFont
import os

W, H = 1200, 630
OUT = os.path.expanduser("~/workspace/deploy/kodepos-wilayah/og-image.png")

img = Image.new("RGB", (W, H))
px = img.load()
# vertical gradient #1d4ed8 -> #3b82f6 -> #4f46e5
def lerp(a, b, t):
    return tuple(int(a[i] + (b[i] - a[i]) * t) for i in range(3))
c1, c2, c3 = (29, 78, 216), (59, 130, 246), (79, 70, 229)
for y in range(H):
    t = y / H
    c = lerp(c1, c2, t * 2) if t < 0.5 else lerp(c2, c3, (t - 0.5) * 2)
    for x in range(W):
        px[x, y] = c

d = ImageDraw.Draw(img, "RGBA")
# subtle pin circle decoration
d.ellipse([880, -120, 1300, 300], fill=(255, 255, 255, 22))
d.ellipse([980, -60, 1220, 180], fill=(255, 255, 255, 26))

fb = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
fr = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
f_brand = ImageFont.truetype(fb, 92)
f_tag = ImageFont.truetype(fr, 40)
f_stats = ImageFont.truetype(fb, 36)

d.text((80, 150), "Kode Pos", font=f_brand, fill="white")
d.text((80, 250), "& Wilayah", font=f_brand, fill="white")
d.text((80, 380), "Cari kode pos seluruh Indonesia", font=f_tag, fill=(219, 234, 254))
d.text((80, 500), "38 provinsi  ·  514 kabupaten/kota  ·  7.285 kecamatan  ·  83.762 desa",
       font=f_stats, fill="white")
img.save(OUT, optimize=True)
print("wrote", OUT, os.path.getsize(OUT), "bytes")
