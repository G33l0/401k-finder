#!/usr/bin/env python3
"""Generate the application mark."""

from __future__ import annotations

import argparse
import math
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

try:
    from PIL import Image, ImageDraw
except ImportError:  # pragma: no cover - the script is the only consumer
    raise SystemExit("Pillow is required: pip install pillow") from None

OUTPUT_DIR = REPO_ROOT / "app" / "ui" / "resources"

BADGE = (11, 58, 74, 255)  # #0B3A4A
TRACE = (242, 247, 248, 255)  # #F2F7F8
ACCENT = (245, 165, 36, 255)  # #F5A524

SUPERSAMPLE = 8

Point = tuple[float, float]


BADGE_RADIUS = 0.20


def _clearance(centre: Point, radius: float) -> float:
    """How much room a disc has inside the badge. Negative means it pokes out."""

    x, y = centre
    edges = min(x, y, 1 - x, 1 - y) - radius

    cx = BADGE_RADIUS if x < BADGE_RADIUS else 1 - BADGE_RADIUS
    cy = BADGE_RADIUS if y < BADGE_RADIUS else 1 - BADGE_RADIUS
    if abs(x - 0.5) > 0.5 - BADGE_RADIUS and abs(y - 0.5) > 0.5 - BADGE_RADIUS:
        return min(edges, BADGE_RADIUS - radius - math.hypot(x - cx, y - cy))

    return edges


class Mark:
    """One variant of the mark, in normalized 0..1 coordinates."""

    def __init__(
        self,
        points: list[Point],
        stroke: float,
        origin: float,
        terminal: float,
        margin: float,
    ):
        self._raw = (points, stroke, origin, terminal)
        self.points, self.stroke, self.origin, self.terminal = self._fit(margin)

    def _place(self, scale: float) -> tuple[list[Point], float, float, float]:
        """Scale about the origin, then centre the painted extent in the badge."""

        points, stroke, origin, terminal = self._raw
        stroke, origin, terminal = stroke * scale, origin * scale, terminal * scale
        scaled = [(x * scale, y * scale) for x, y in points]

        xs = [x for x, _ in scaled]
        ys = [y for _, y in scaled]
        half = stroke / 2

        left = min(xs[0] - origin, min(xs) - half, xs[-1] - terminal)
        right = max(xs[0] + origin, max(xs) + half, xs[-1] + terminal)
        top = min(ys[0] - origin, min(ys) - half, ys[-1] - terminal)
        bottom = max(ys[0] + origin, max(ys) + half, ys[-1] + terminal)

        dx = 0.5 - (left + right) / 2
        dy = 0.5 - (top + bottom) / 2

        return [(x + dx, y + dy) for x, y in scaled], stroke, origin, terminal

    def _fit(self, margin: float) -> tuple[list[Point], float, float, float]:
        """The largest the mark can be and still keep ``margin`` on every side."""

        def shortfall(scale: float) -> float:
            points, stroke, origin, terminal = self._place(scale)
            return min(
                _clearance(points[0], origin),
                _clearance(points[-1], terminal),
                min(_clearance(point, stroke / 2) for point in points),
            ) - margin

        low, high = 0.1, 2.0
        for _ in range(40):
            middle = (low + high) / 2
            if shortfall(middle) >= 0:
                low = middle
            else:
                high = middle

        return self._place(low)


DETAILED = Mark(
    points=[
        (0.20, 0.80),
        (0.38, 0.80),
        (0.38, 0.62),
        (0.56, 0.62),
        (0.56, 0.44),
        (0.74, 0.44),
        (0.74, 0.26),
    ],
    stroke=0.075,
    origin=0.048,
    terminal=0.098,
    margin=0.060,
)

SIMPLE = Mark(
    points=[
        (0.24, 0.76),
        (0.48, 0.76),
        (0.48, 0.50),
        (0.72, 0.50),
        (0.72, 0.26),
    ],
    stroke=0.105,
    origin=0.062,
    terminal=0.125,
    margin=0.045,
)


def variant_for(size: int) -> Mark:
    return DETAILED if size >= 48 else SIMPLE


def render(size: int, mark: Mark | None = None) -> Image.Image:
    """Render the mark at one pixel size."""

    if mark is None:
        mark = variant_for(size)

    canvas = size * SUPERSAMPLE
    image = Image.new("RGBA", (canvas, canvas), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)

    draw.rounded_rectangle(
        [(0, 0), (canvas - 1, canvas - 1)], radius=canvas * BADGE_RADIUS, fill=BADGE
    )

    points = [(x * canvas, y * canvas) for x, y in mark.points]
    stroke = canvas * mark.stroke

    draw.line(points, fill=TRACE, width=int(stroke))

    for x, y in points[1:-1]:
        draw.ellipse(
            [(x - stroke / 2, y - stroke / 2), (x + stroke / 2, y + stroke / 2)],
            fill=TRACE,
        )

    ox, oy = points[0]
    radius = canvas * mark.origin
    draw.ellipse([(ox - radius, oy - radius), (ox + radius, oy + radius)], fill=TRACE)
    inner = radius - stroke * 0.45
    if inner > 0:
        draw.ellipse([(ox - inner, oy - inner), (ox + inner, oy + inner)], fill=BADGE)

    ex, ey = points[-1]
    radius = canvas * mark.terminal
    draw.ellipse([(ex - radius, ey - radius), (ex + radius, ey + radius)], fill=ACCENT)

    return image.resize((size, size), Image.LANCZOS)


def _hex(colour: tuple[int, int, int, int]) -> str:
    return "#{:02X}{:02X}{:02X}".format(*colour[:3])


def build_svg(box: int = 512) -> str:
    """Emit the display variant as a vector file."""

    mark = DETAILED
    path = " ".join(
        f"{'M' if index == 0 else 'L'}{x * box:.1f} {y * box:.1f}"
        for index, (x, y) in enumerate(mark.points)
    )
    start = mark.points[0]
    end = mark.points[-1]

    ring = mark.origin - mark.stroke * 0.225

    return f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {box} {box}" \
width="{box}" height="{box}" role="img" aria-labelledby="title">
  <title id="title">401K Finder Pro</title>
  <desc>A stepped trace climbing from a hollow origin node to a solid terminal node.</desc>
  <rect width="{box}" height="{box}" rx="{box * BADGE_RADIUS:.1f}" fill="{_hex(BADGE)}"/>
  <path d="{path}" fill="none" stroke="{_hex(TRACE)}" stroke-width="{mark.stroke * box:.1f}"
        stroke-linecap="round" stroke-linejoin="round"/>
  <circle cx="{start[0] * box:.1f}" cy="{start[1] * box:.1f}" r="{ring * box:.1f}"
          fill="none" stroke="{_hex(TRACE)}" stroke-width="{mark.stroke * box * 0.45:.1f}"/>
  <circle cx="{end[0] * box:.1f}" cy="{end[1] * box:.1f}" r="{mark.terminal * box:.1f}"
          fill="{_hex(ACCENT)}"/>
</svg>
"""


ICO_SIZES = (16, 32, 48, 64, 128, 256)
PREVIEW_SIZES = (256, 128, 64, 48, 32, 16)


def _contact_row(ground: tuple[int, int, int, int]) -> Image.Image:
    """One row of every size on a single background, baseline-aligned."""

    gap = 24
    width = gap + sum(size + gap for size in PREVIEW_SIZES)
    height = max(PREVIEW_SIZES) + gap * 2

    row = Image.new("RGBA", (width, height), ground)
    x = gap
    for size in PREVIEW_SIZES:
        tile = render(size)
        row.paste(tile, (x, height - gap - size), tile)
        x += size + gap

    return row


def write_preview(path: Path) -> None:
    light = _contact_row((255, 255, 255, 255))
    dark = _contact_row((24, 26, 30, 255))

    sheet = Image.new("RGBA", (light.width, light.height + dark.height), (255, 255, 255, 255))
    sheet.paste(light, (0, 0))
    sheet.paste(dark, (0, light.height))
    sheet.save(path)


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate the application mark.")
    parser.add_argument("--output", type=Path, default=OUTPUT_DIR)
    parser.add_argument(
        "--preview",
        action="store_true",
        help="Also write a contact sheet of every size, for eyeballing.",
    )
    args = parser.parse_args()

    args.output.mkdir(parents=True, exist_ok=True)

    (args.output / "logo.svg").write_text(build_svg(), encoding="utf-8")
    print("  logo.svg   vector original")

    master = render(512)
    master.save(args.output / "logo.png")
    master.save(args.output / "app.png")
    print("  logo.png   512x512")
    print("  app.png    512x512")

    frames = [render(size) for size in ICO_SIZES]
    frames[-1].save(
        args.output / "app.ico",
        format="ICO",
        sizes=[(size, size) for size in ICO_SIZES],
        append_images=frames[:-1],
    )
    print(f"  app.ico    {', '.join(f'{s}x{s}' for s in ICO_SIZES)}")

    if args.preview:
        destination = args.output.parent / "logo_preview.png"
        write_preview(destination)
        print(f"  {destination.name}  contact sheet (not shipped)")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
