"""畫 App 圖示（純幾何，免字型）：橘底圓角＋白色對話泡泡＋聲波。輸出 icons/*.png"""
import os
from PIL import Image, ImageDraw
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
def draw(size, maskable=False):
    S = 1024
    im = Image.new('RGBA', (S, S), (0, 0, 0, 0)); d = ImageDraw.Draw(im)
    orange, cream, teal, sun = (255, 107, 61), (255, 248, 239), (15, 163, 163), (255, 201, 60)
    if maskable: d.rectangle([0, 0, S, S], fill=orange); pad = 190
    else: d.rounded_rectangle([0, 0, S, S], radius=230, fill=orange); pad = 120
    # 對話泡泡
    x0, y0, x1, y1 = pad, pad + 40, S - pad, S - pad - 110
    d.rounded_rectangle([x0, y0, x1, y1], radius=(x1 - x0) // 4, fill=cream)
    d.polygon([(x0 + 150, y1 - 20), (x0 + 120, y1 + 120), (x0 + 300, y1 - 20)], fill=cream)
    # 聲波長條
    cx, cy = S // 2, (y0 + y1) // 2
    hs = [0.35, 0.7, 1.0, 0.7, 0.35]; bw = (x1 - x0) // 11; gap = bw // 1.3
    total = len(hs) * bw + (len(hs) - 1) * gap; sx = cx - total / 2
    H = (y1 - y0) * 0.62
    for i, h in enumerate(hs):
        bx = sx + i * (bw + gap); bh = H * h
        d.rounded_rectangle([bx, cy - bh / 2, bx + bw, cy + bh / 2], radius=bw // 2, fill=teal if i != 2 else orange)
    # 小太陽點綴
    r = 70; d.ellipse([x1 - r * 1.2, y0 - r * 0.8, x1 - r * 1.2 + 2 * r, y0 - r * 0.8 + 2 * r], fill=sun)
    return im.resize((size, size), Image.LANCZOS)
os.makedirs(os.path.join(ROOT, 'icons'), exist_ok=True)
draw(192).save(os.path.join(ROOT, 'icons', 'icon-192.png'))
draw(512).save(os.path.join(ROOT, 'icons', 'icon-512.png'))
draw(512, True).save(os.path.join(ROOT, 'icons', 'icon-maskable-512.png'))
print('icons ok')
