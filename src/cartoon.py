"""Procedurally drawn cartoon frames for nursery-rhyme videos.

Replaces stock photography, which reads as adult/documentary and is wrong for
a children's channel. Everything here is flat vector-style shapes with thick
outlines and chunky rounded forms - the "Claymorphism" direction the design
database recommends for children's apps (soft 3D, toy-like, thick borders,
rounded, no muted colours).

Deterministic per seed, so a given rhyme always renders the same frames.
"""
import math
import random
from pathlib import Path
from typing import List, Tuple

from PIL import Image, ImageDraw, ImageFilter, ImageFont

W, H = 1080, 1920
OUTLINE = 10          # thick borders are core to the style
RADIUS = 64           # chunky rounded corners

# Bright, saturated kids palette. The design DB's colour row returned a dark
# video-editor scheme (it keyed on "video", not "kids"), so it is not used.
INK = (45, 42, 69)
CREAM = (255, 246, 229)
WHITE = (255, 255, 255)
SUN = (255, 217, 61)
SUN_DEEP = (255, 182, 39)
CORAL = (255, 107, 157)
MINT = (107, 203, 119)
GRASS = (86, 180, 96)
SKY_TOP = (127, 216, 255)
SKY_BOT = (206, 243, 255)
NIGHT_TOP = (58, 47, 122)
NIGHT_BOT = (123, 104, 205)
PURPLE = (179, 136, 235)
ORANGE = (255, 149, 92)

CONFETTI = [CORAL, SUN, MINT, PURPLE, ORANGE, (108, 197, 255)]

FONT_TITLE = "/usr/share/fonts/opentype/comic-neue/ComicNeue-Bold.otf"
FONT_BODY = "/usr/share/fonts/truetype/quicksand/Quicksand-Bold.ttf"
FONT_FALLBACK = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"


def _font(path: str, size: int):
    for candidate in (path, FONT_FALLBACK):
        try:
            return ImageFont.truetype(candidate, size)
        except OSError:
            continue
    return ImageFont.load_default()


def _vgradient(top: Tuple[int, int, int], bottom: Tuple[int, int, int]) -> Image.Image:
    """Vertical gradient - the base of every frame, so nothing is a flat wash."""
    grad = Image.new("RGB", (1, H))
    px = grad.load()
    for y in range(H):
        t = y / (H - 1)
        px[0, y] = tuple(round(top[i] + (bottom[i] - top[i]) * t) for i in range(3))
    return grad.resize((W, H), Image.Resampling.BILINEAR)


def _blob(draw, box, fill, outline=INK, width=OUTLINE):
    draw.ellipse(box, fill=fill, outline=outline, width=width)


def _sun(draw, cx, cy, r, rays=12, fill=SUN):
    for i in range(rays):
        a = (2 * math.pi / rays) * i
        x1, y1 = cx + math.cos(a) * r * 1.18, cy + math.sin(a) * r * 1.18
        x2, y2 = cx + math.cos(a) * r * 1.62, cy + math.sin(a) * r * 1.62
        draw.line([x1, y1, x2, y2], fill=INK, width=OUTLINE + 6)
        draw.line([x1, y1, x2, y2], fill=fill, width=OUTLINE)
    _blob(draw, [cx - r, cy - r, cx + r, cy + r], fill)


def _moon(draw, cx, cy, r):
    _blob(draw, [cx - r, cy - r, cx + r, cy + r], (255, 248, 214))
    for dx, dy, cr in ((-0.35, -0.2, 0.16), (0.25, 0.1, 0.12), (-0.05, 0.42, 0.09)):
        draw.ellipse(
            [cx + dx * r - cr * r, cy + dy * r - cr * r,
             cx + dx * r + cr * r, cy + dy * r + cr * r],
            fill=(238, 226, 188),
        )


def _cloud(draw, cx, cy, s):
    parts = [(-1.0, 0.1, 0.62), (0.0, -0.30, 0.82), (1.0, 0.08, 0.66), (0.1, 0.30, 0.70)]
    for dx, dy, rr in parts:
        r = rr * s
        draw.ellipse([cx + dx * s - r, cy + dy * s - r, cx + dx * s + r, cy + dy * s + r],
                     fill=INK)
    for dx, dy, rr in parts:
        r = rr * s - OUTLINE
        draw.ellipse([cx + dx * s - r, cy + dy * s - r, cx + dx * s + r, cy + dy * s + r],
                     fill=WHITE)


def _star(draw, cx, cy, r, fill=SUN, outline=True):
    pts = []
    for i in range(10):
        a = -math.pi / 2 + i * math.pi / 5
        rad = r if i % 2 == 0 else r * 0.45
        pts.append((cx + math.cos(a) * rad, cy + math.sin(a) * rad))
    draw.polygon(pts, fill=fill, outline=INK if outline else None)
    if outline:
        draw.line(pts + [pts[0]], fill=INK, width=max(3, OUTLINE // 2), joint="curve")


def _bird(draw, cx, cy, s):
    for side in (-1, 1):
        draw.arc([cx + side * s - s, cy - s * 0.7, cx + side * s + s, cy + s * 0.7],
                 start=200 if side < 0 else 340, end=340 if side < 0 else 480,
                 fill=INK, width=9)


def _butterfly(draw, cx, cy, s, color):
    def wing(x_inner, x_outer, y0, y1):
        # PIL requires x0<=x1; the left wing's outer edge is the smaller x.
        draw.ellipse([min(x_inner, x_outer), y0, max(x_inner, x_outer), y1],
                     fill=color, outline=INK, width=6)

    for side in (-1, 1):
        wing(cx + side * s * 0.1, cx + side * s * 1.1, cy - s * 0.8, cy + s * 0.2)
        wing(cx + side * s * 0.1, cx + side * s * 0.9, cy - s * 0.1, cy + s * 0.75)
    draw.line([cx, cy - s * 0.6, cx, cy + s * 0.6], fill=INK, width=8)


DAY_SKIES = [
    ((127, 216, 255), (214, 245, 214)),
    ((255, 214, 236), (255, 244, 206)),
    ((168, 226, 255), (255, 236, 205)),
    ((186, 240, 255), (214, 250, 226)),
]


def _day_sky(rng):
    """Vary the sky per frame so repeated themes don't render identically."""
    return rng.choice(DAY_SKIES)


def _hills(draw, base_y, colors):
    for i, c in enumerate(colors):
        off = i * 150
        draw.ellipse([-420 + off * 0.5, base_y + off, W * 0.75 + off, base_y + 1500],
                     fill=c, outline=INK, width=OUTLINE)
        draw.ellipse([W * 0.35 - off, base_y + 90 + off, W + 460 - off * 0.4, base_y + 1560],
                     fill=c, outline=INK, width=OUTLINE)


def _confetti(draw, rng, n=34, y_range=(0, H)):
    for _ in range(n):
        x = rng.randint(40, W - 40)
        y = rng.randint(*y_range)
        s = rng.randint(14, 30)
        c = rng.choice(CONFETTI)
        kind = rng.choice(("dot", "star", "bar"))
        if kind == "dot":
            draw.ellipse([x - s, y - s, x + s, y + s], fill=c, outline=INK, width=5)
        elif kind == "star":
            _star(draw, x, y, s * 1.25, fill=c)
        else:
            draw.rounded_rectangle([x - s, y - s // 2, x + s, y + s // 2],
                                   radius=s // 2, fill=c, outline=INK, width=5)


def _shadowed(base: Image.Image, shape_fn) -> Image.Image:
    """Claymorphism double shadow: a soft dark drop under the shape."""
    shadow = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    shape_fn(ImageDraw.Draw(shadow), True)
    shadow = shadow.filter(ImageFilter.GaussianBlur(26))
    base.paste(Image.alpha_composite(base.convert("RGBA"), shadow).convert("RGB"), (0, 0))
    shape_fn(ImageDraw.Draw(base), False)
    return base


def _wrap(draw, text, font, max_w) -> List[str]:
    lines, cur = [], ""
    for word in text.split():
        cand = f"{cur} {word}".strip()
        if cur and draw.textbbox((0, 0), cand, font=font)[2] > max_w:
            lines.append(cur)
            cur = word
        else:
            cur = cand
    if cur:
        lines.append(cur)
    return lines


def _fit(draw, text, max_w, max_lines=3):
    for size in range(120, 52, -4):
        f = _font(FONT_TITLE, size)
        lines = _wrap(draw, text, f, max_w)
        widest = max(draw.textbbox((0, 0), l, font=f)[2] for l in lines)
        if len(lines) <= max_lines and widest <= max_w:
            return f, lines
    return f, lines


def title_card(title: str, out_path: str, subtitle: str = "Nursery Rhyme", seed: int = 0) -> str:
    """Colourful title frame: gradient sky, sun, clouds, confetti, clay card."""
    rng = random.Random(seed)
    img = _vgradient(SKY_TOP, (255, 236, 210))
    d = ImageDraw.Draw(img)

    _sun(d, 175, 235, 105)
    _cloud(d, 860, 300, 95)
    _cloud(d, 300, 560, 70)
    _confetti(d, rng, 26, (60, 780))
    _hills(d, H - 560, [MINT, GRASS])
    _confetti(d, rng, 12, (H - 420, H - 120))

    card = [72, 690, W - 72, 1290]

    def draw_card(dd, is_shadow):
        if is_shadow:
            dd.rounded_rectangle([card[0] + 14, card[1] + 26, card[2] + 14, card[3] + 26],
                                 radius=RADIUS, fill=(0, 0, 0, 120))
        else:
            dd.rounded_rectangle(card, radius=RADIUS, fill=CREAM, outline=INK, width=OUTLINE + 2)

    img = _shadowed(img, draw_card)
    d = ImageDraw.Draw(img)

    font, lines = _fit(d, title, (card[2] - card[0]) - 110)
    lh = int(font.size * 1.22)
    y = (card[1] + card[3]) // 2 - (lh * len(lines)) // 2 - 34
    for line in lines:
        w = d.textbbox((0, 0), line, font=font)[2]
        d.text(((W - w) // 2 + 5, y + 6), line, font=font, fill=(0, 0, 0, 60))
        d.text(((W - w) // 2, y), line, font=font, fill=INK)
        y += lh

    sf = _font(FONT_BODY, 46)
    sw = d.textbbox((0, 0), subtitle, font=sf)[2]
    chip = [(W - sw) // 2 - 42, y + 18, (W + sw) // 2 + 42, y + 108]
    d.rounded_rectangle(chip, radius=45, fill=CORAL, outline=INK, width=7)
    d.text(((W - sw) // 2, y + 40), subtitle, font=sf, fill=WHITE)

    Path(out_path).parent.mkdir(parents=True, exist_ok=True)
    img.save(out_path)
    return out_path


def _sheep(draw, cx, cy, s):
    for dx, dy, rr in ((-0.6, 0, 0.5), (0.6, 0, 0.5), (0, -0.35, 0.6), (0, 0.3, 0.62)):
        r = rr * s
        draw.ellipse([cx + dx * s - r, cy + dy * s - r, cx + dx * s + r, cy + dy * s + r],
                     fill=WHITE, outline=INK, width=7)
    hx, hy, hr = cx + s * 0.72, cy - s * 0.34, s * 0.36
    draw.ellipse([hx - hr, hy - hr, hx + hr, hy + hr], fill=(60, 56, 84), outline=INK, width=7)
    draw.ellipse([hx + hr * 0.05, hy - hr * 0.3, hx + hr * 0.35, hy], fill=WHITE)
    for lx in (-0.45, 0.15):
        draw.line([cx + lx * s, cy + s * 0.75, cx + lx * s, cy + s * 1.15], fill=INK, width=12)


def _flower(draw, cx, cy, s, color):
    for i in range(6):
        a = i * math.pi / 3
        px, py = cx + math.cos(a) * s * 0.85, cy + math.sin(a) * s * 0.85
        draw.ellipse([px - s * 0.55, py - s * 0.55, px + s * 0.55, py + s * 0.55],
                     fill=color, outline=INK, width=6)
    draw.ellipse([cx - s * 0.45, cy - s * 0.45, cx + s * 0.45, cy + s * 0.45],
                 fill=SUN, outline=INK, width=6)


def scene(theme: str, out_path: str, seed: int = 0) -> str:
    """One themed cartoon background frame."""
    rng = random.Random(seed)
    t = (theme or "").lower()
    night = any(k in t for k in ("night", "bed", "sleep", "star", "moon", "twinkle", "dream"))

    if night:
        img = _vgradient(NIGHT_TOP, NIGHT_BOT)
        d = ImageDraw.Draw(img)
        for _ in range(46):
            _star(d, rng.randint(50, W - 50), rng.randint(60, 1150),
                  rng.randint(12, 30), fill=(255, 246, 200), outline=False)
        _moon(d, 800, 330, 130)
        _cloud(d, 260, 470, 78)
        _hills(d, H - 520, [(96, 78, 168), (72, 58, 138)])
        for i in range(3):
            _sheep(d, 210 + i * 320, H - 330 + rng.randint(-40, 40), 92)
        return _save(img, out_path)

    if any(k in t for k in ("sea", "ocean", "water", "rain", "boat")):
        img = _vgradient(SKY_TOP, (150, 226, 255))
        d = ImageDraw.Draw(img)
        _sun(d, 860, 260, 96)
        _cloud(d, 280, 350, 88)
        for i, c in enumerate([(86, 178, 232), (58, 148, 210), (38, 118, 182)]):
            d.ellipse([-300, H - 620 + i * 190, W + 300, H + 500], fill=c,
                      outline=INK, width=OUTLINE)
        for bx, by in ((300, 780), (450, 700), (600, 820)):
            _bird(d, bx, by, 34)
        _confetti(d, rng, 14, (120, 700))
        return _save(img, out_path)

    if any(k in t for k in ("garden", "flower", "spring", "forest", "tree", "season")):
        img = _vgradient(*_day_sky(rng))
        d = ImageDraw.Draw(img)
        sun_x = rng.choice([180, 870])
        _sun(d, sun_x, rng.randint(225, 300), 100)
        _cloud(d, 1050 - sun_x, rng.randint(310, 390), 84)
        for bx, by in ((640, 700), (780, 620)):
            _bird(d, bx, by, 32)
        for i, (bx, by) in enumerate(((250, 880), (760, 960), (470, 1080))):
            _butterfly(d, bx, by, 46, [CORAL, PURPLE, ORANGE][i])
        _hills(d, H - 640, [MINT, GRASS])
        for i in range(5):
            _flower(d, 130 + i * 210, H - 300 + rng.randint(-70, 70), 60,
                    rng.choice([CORAL, PURPLE, SUN, ORANGE]))
        return _save(img, out_path)

    if any(k in t for k in ("farm", "animal", "sheep", "lamb", "barn")):
        img = _vgradient(*_day_sky(rng))
        d = ImageDraw.Draw(img)
        sun_x = rng.choice([175, 880])
        _sun(d, sun_x, rng.randint(220, 300), 100)
        _cloud(d, 1055 - sun_x, rng.randint(300, 380), 86)
        _cloud(d, rng.randint(260, 420), rng.randint(500, 580), 62)
        for bx, by in ((330, 720), (470, 640), (620, 760)):
            _bird(d, bx, by, 34)
        _hills(d, H - 620, [MINT, GRASS])
        for i in range(3):
            _sheep(d, 205 + i * 330, H - 340 + rng.randint(-40, 40), 96)
        return _save(img, out_path)

    # default: high-energy playful
    img = _vgradient((255, 205, 225), (255, 240, 200))
    d = ImageDraw.Draw(img)
    _sun(d, 850, 270, 104, fill=SUN_DEEP)
    _cloud(d, 270, 360, 88)
    _confetti(d, rng, 40, (80, H - 640))
    _hills(d, H - 560, [PURPLE, CORAL])
    return _save(img, out_path)


def _save(img, out_path):
    Path(out_path).parent.mkdir(parents=True, exist_ok=True)
    img.save(out_path)
    return out_path
